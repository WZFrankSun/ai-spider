from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.monitoring.application.ports import ProductRepository
from app.monitoring.application.scan_product import ScanProduct
from app.monitoring.domain.models import Product, ProductScanStatus


@dataclass
class ScanBatchSummary:
    started_at: datetime
    finished_at: datetime
    total: int
    healthy: int = 0
    inventory_risk: int = 0
    technical_failure: int = 0
    failed_product_ids: list[str] = field(default_factory=list)


class HourlyScanRunner:
    def __init__(
        self,
        products: ProductRepository,
        scan_product: ScanProduct,
        *,
        max_concurrency: int = 3,
        per_product_timeout_seconds: float = 120.0,
    ):
        if max_concurrency < 1:
            raise ValueError("max_concurrency must be at least 1")
        if per_product_timeout_seconds <= 0:
            raise ValueError("per_product_timeout_seconds must be positive")
        self.products = products
        self.scan_product = scan_product
        self.max_concurrency = max_concurrency
        self.per_product_timeout_seconds = per_product_timeout_seconds

    async def run_once(self) -> ScanBatchSummary:
        started_at = datetime.now(timezone.utc)
        enabled_products = await self.products.list_enabled()
        semaphore = asyncio.Semaphore(self.max_concurrency)

        async def run_one(product: Product):
            async with semaphore:
                try:
                    result = await asyncio.wait_for(
                        self.scan_product.execute(product.id),
                        timeout=self.per_product_timeout_seconds,
                    )
                    return product.id, result.observation.status, None
                except asyncio.TimeoutError:
                    await self._mark_technical_failure(product)
                    return product.id, ProductScanStatus.TECHNICAL_FAILURE, "SCAN_TIMEOUT"
                except Exception as exc:
                    await self._mark_technical_failure(product)
                    return product.id, ProductScanStatus.TECHNICAL_FAILURE, str(exc)

        results = await asyncio.gather(*(run_one(product) for product in enabled_products))
        summary = ScanBatchSummary(
            started_at=started_at,
            finished_at=datetime.now(timezone.utc),
            total=len(enabled_products),
        )
        for product_id, status, error in results:
            if status == ProductScanStatus.HEALTHY:
                summary.healthy += 1
            elif status == ProductScanStatus.INVENTORY_RISK:
                summary.inventory_risk += 1
            else:
                summary.technical_failure += 1
                summary.failed_product_ids.append(product_id)
        return summary

    async def _mark_technical_failure(self, product: Product) -> None:
        product.status = ProductScanStatus.TECHNICAL_FAILURE
        await self.products.save(product)
