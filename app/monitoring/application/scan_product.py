from __future__ import annotations

from asyncio import CancelledError
from dataclasses import dataclass
from datetime import datetime, timezone
from time import time_ns

from app.monitoring.application.ports import (
    AlertRepository,
    ProductRepository,
    ScanRepository,
    Scanner,
)
from app.monitoring.application.retry_policy import scan_with_retry
from app.monitoring.domain.models import (
    Alert,
    AlertStatus,
    AlertType,
    Product,
    ProductScanStatus,
    Scan,
    ScanObservation,
)


class ScanInProgressError(RuntimeError):
    def __init__(self, product_id: str):
        super().__init__(f"scan already in progress: {product_id}")
        self.product_id = product_id


class ScanCoordinator:
    def __init__(self):
        self._active: set[str] = set()

    def acquire(self, product_id: str) -> None:
        if product_id in self._active:
            raise ScanInProgressError(product_id)
        self._active.add(product_id)

    def is_active(self, product_id: str) -> bool:
        return product_id in self._active

    def release(self, product_id: str) -> None:
        self._active.discard(product_id)


@dataclass
class ScanSummary:
    product: Product
    scan: Scan
    observation: ScanObservation
    alert: Alert | None = None


class ScanProduct:
    def __init__(
        self,
        product_repository: ProductRepository,
        scan_repository: ScanRepository,
        alert_repository: AlertRepository,
        scanner: Scanner,
        coordinator: ScanCoordinator | None = None,
        retry_attempts: int = 3,
        retry_backoff_seconds: float = 0.0,
    ):
        self.products = product_repository
        self.scans = scan_repository
        self.alerts = alert_repository
        self.scanner = scanner
        self.coordinator = coordinator or ScanCoordinator()
        self.retry_attempts = retry_attempts
        self.retry_backoff_seconds = retry_backoff_seconds

    async def execute(self, product_id: str) -> ScanSummary:
        self.coordinator.acquire(product_id)
        try:
            product = await self.products.get(product_id)
            if product is None:
                raise KeyError(f"unknown product: {product_id}")
            if not product.enabled:
                raise ValueError(f"product disabled: {product_id}")

            product.status = ProductScanStatus.SCANNING
            try:
                await self.products.save(product)
                started_at = datetime.now(timezone.utc)
                observation = await scan_with_retry(
                    self.scanner,
                    product,
                    attempts=self.retry_attempts,
                    backoff_seconds=self.retry_backoff_seconds,
                )
                observation.started_at = started_at
                product.status = observation.status
                scan = _make_scan(product, observation)
                await self.scans.add(scan)
                alert = await self._apply_alert_policy(product, observation)
                await self.products.save(product)
                return ScanSummary(product=product, scan=scan, observation=observation, alert=alert)
            except (Exception, CancelledError):
                product.status = ProductScanStatus.TECHNICAL_FAILURE
                await self.products.save(product)
                raise
        finally:
            self.coordinator.release(product_id)

    async def _apply_alert_policy(
        self,
        product: Product,
        observation: ScanObservation,
    ) -> Alert | None:
        if observation.status != ProductScanStatus.INVENTORY_RISK:
            return None

        alert = await self.alerts.find_active_inventory_alert(product.id)
        if alert is None:
            alert = Alert(
                id=f"alert-{product.id}",
                type=AlertType.PRODUCT_ADD_TO_CART_MISSING,
                status=AlertStatus.OPEN,
                product_id=product.id,
            )
        else:
            alert.failure_count += 1
            if alert.status == AlertStatus.PENDING_VERIFICATION:
                alert.status = AlertStatus.REOPENED
        await self.alerts.save(alert)
        return alert


def _make_scan(product: Product, observation: ScanObservation) -> Scan:
    now = datetime.now(timezone.utc)
    started_at = observation.started_at or now
    finished_at = observation.finished_at or now
    return Scan(
        id=f"scan-{product.id}-{time_ns()}",
        product_id=product.id,
        status=observation.status,
        observation=observation,
        started_at=started_at,
        finished_at=finished_at,
    )
