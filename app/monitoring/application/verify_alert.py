from __future__ import annotations

from asyncio import CancelledError

from app.monitoring.application.ports import (
    AlertRepository,
    ProductRepository,
    ScanRepository,
    Scanner,
)
from app.monitoring.application.scan_product import ScanCoordinator, _make_scan
from app.monitoring.domain.models import AlertStatus, ProductScanStatus
from app.monitoring.domain.policies import can_resolve_alert


class VerifyAlert:
    def __init__(
        self,
        product_repository: ProductRepository,
        scan_repository: ScanRepository,
        alert_repository: AlertRepository,
        scanner: Scanner,
        coordinator: ScanCoordinator | None = None,
    ):
        self.products = product_repository
        self.scans = scan_repository
        self.alerts = alert_repository
        self.scanner = scanner
        self.coordinator = coordinator or ScanCoordinator()

    async def execute(self, alert_id: str):
        alert = await self.alerts.get(alert_id)
        if alert is None:
            raise KeyError(f"unknown alert: {alert_id}")
        self.coordinator.acquire(alert.product_id)
        try:
            product = await self.products.get(alert.product_id)
            if product is None:
                raise KeyError(f"unknown product: {alert.product_id}")
            alert.status = AlertStatus.PENDING_VERIFICATION
            await self.alerts.save(alert)
            product.status = ProductScanStatus.SCANNING
            try:
                await self.products.save(product)
                observation = await self.scanner.scan(product)
                product.status = observation.status
                await self.scans.add(_make_scan(product, observation))
                if can_resolve_alert(alert, observation):
                    alert.status = AlertStatus.RESOLVED
                elif observation.status == ProductScanStatus.INVENTORY_RISK:
                    alert.status = AlertStatus.REOPENED
                    alert.failure_count += 1
                else:
                    alert.status = AlertStatus.PENDING_VERIFICATION
                await self.products.save(product)
                await self.alerts.save(alert)
                return alert
            except (Exception, CancelledError):
                product.status = ProductScanStatus.TECHNICAL_FAILURE
                await self.products.save(product)
                alert.status = AlertStatus.PENDING_VERIFICATION
                await self.alerts.save(alert)
                raise
        finally:
            self.coordinator.release(alert.product_id)
