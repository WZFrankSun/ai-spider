from __future__ import annotations

from app.monitoring.domain.models import Alert, AlertStatus, AlertType, Product, Scan


class MemoryProductRepository:
    def __init__(self, products: list[Product]):
        self._products = {product.id: product for product in products}

    async def get(self, product_id: str) -> Product | None:
        return self._products.get(product_id)

    async def list_enabled(self) -> list[Product]:
        return [product for product in self._products.values() if product.enabled]

    async def save(self, product: Product) -> None:
        self._products[product.id] = product


class MemoryScanRepository:
    def __init__(self):
        self._scans: list[Scan] = []

    async def add(self, scan: Scan) -> None:
        self._scans.append(scan)

    async def latest_for(self, product_id: str) -> Scan | None:
        matches = [scan for scan in self._scans if scan.product_id == product_id]
        return matches[-1] if matches else None

    async def list_all(self) -> list[Scan]:
        return list(self._scans)


class MemoryAlertRepository:
    def __init__(self):
        self._alerts: dict[str, Alert] = {}
        self.transitions: list[dict] = []

    async def find_active_inventory_alert(self, product_id: str) -> Alert | None:
        for alert in self._alerts.values():
            if (
                alert.product_id == product_id
                and alert.type == AlertType.PRODUCT_ADD_TO_CART_MISSING
                and alert.status != AlertStatus.RESOLVED
            ):
                return alert
        return None

    async def save(self, alert: Alert) -> None:
        self._alerts[alert.id] = alert

    async def get(self, alert_id: str) -> Alert | None:
        return self._alerts.get(alert_id)

    async def record_transition(self, alert, *, from_status, reason, operator):
        self.transitions.append({"alert_id": alert.id, "from_status": from_status, "to_status": alert.status.value, "reason": reason, "operator": operator})

    async def list_all(self) -> list[Alert]:
        return list(self._alerts.values())
