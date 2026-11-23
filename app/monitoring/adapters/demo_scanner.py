from __future__ import annotations

from app.monitoring.domain.models import Product, ProductScanStatus, ScanObservation


class DemoScanner:
    def __init__(self, products: list[Product], outcomes: dict[str, ProductScanStatus] | None = None):
        self._products = {product.id: product for product in products}
        self._outcomes = dict(outcomes or {})
        self._next_results: dict[str, ProductScanStatus] = {}

    async def scan(self, product: Product) -> ScanObservation:
        status = self._next_results.pop(product.id, None)
        if status is None:
            status = self._outcomes.get(product.id)
        if status is None:
            status = (
                ProductScanStatus.INVENTORY_RISK
                if product.id in {"DE-001", "IT-001"}
                else ProductScanStatus.HEALTHY
            )
        if status == ProductScanStatus.HEALTHY:
            return ScanObservation(
                status=status,
                ocr_text="Add to cart",
                matched_phrase="Add to cart",
                confidence=0.98,
            )
        if status == ProductScanStatus.INVENTORY_RISK:
            return ScanObservation(status=status, confidence=0.91)
        return ScanObservation(
            status=ProductScanStatus.TECHNICAL_FAILURE,
            error_code="DEMO_FAILURE",
            error_message="simulated technical failure",
        )

    def set_outcome(self, product_id: str, status: ProductScanStatus) -> None:
        self._outcomes[product_id] = status

    def set_next_result(self, product_id: str, status: ProductScanStatus) -> None:
        if status not in {
            ProductScanStatus.HEALTHY,
            ProductScanStatus.INVENTORY_RISK,
            ProductScanStatus.TECHNICAL_FAILURE,
        }:
            raise ValueError(f"invalid demo result: {status.value}")
        self._next_results[product_id] = status

    def clear_next_result(self, product_id: str) -> None:
        self._next_results.pop(product_id, None)
