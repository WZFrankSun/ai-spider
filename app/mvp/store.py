from __future__ import annotations

from datetime import timedelta

from .models import AlertEvent, AlertStatus, AlertType, DemoProduct, ScanResult, utc_now


class DemoStore:
    """In-memory state used by the local MVP demonstration."""

    def __init__(self) -> None:
        self._products = {product.id: product for product in _demo_products()}
        self._scans: list[ScanResult] = []
        self._alerts: dict[str, AlertEvent] = {}

    def list_products(self) -> list[DemoProduct]:
        return list(self._products.values())

    def list_scans(self) -> list[ScanResult]:
        return list(reversed(self._scans))

    def list_alerts(self) -> list[AlertEvent]:
        return list(reversed(self._alerts.values()))

    def scan_product(self, product_id: str) -> ScanResult:
        product = self._get_product(product_id)
        started_at = utc_now()
        is_healthy = product.demo_status == "healthy"
        result = ScanResult(
            scan_id=f"scan-{product.id}-{len(self._scans) + 1}",
            product_id=product.id,
            country=product.country,
            platform=product.platform,
            sku=product.sku,
            started_at=started_at,
            finished_at=started_at + timedelta(seconds=2),
            status="healthy" if is_healthy else "inventory_risk",
            ocr_text="Add to cart" if is_healthy else "",
            matched_phrase="Add to cart" if is_healthy else None,
            ocr_confidence=0.98 if is_healthy else 0.91,
        )
        self._scans.append(result)
        if is_healthy:
            self._resolve_open_alert(product.id)
        else:
            self._upsert_inventory_alert(product, result)
        return result

    def verify_alert(self, alert_id: str) -> AlertEvent:
        alert = self._alerts.get(alert_id)
        if alert is None:
            raise KeyError(f"unknown alert: {alert_id}")

        product = self._get_product(alert.product_id)
        product.demo_status = "healthy"
        alert.status = AlertStatus.PENDING_VERIFICATION
        self.scan_product(product.id)
        return self._alerts[alert_id]

    def _get_product(self, product_id: str) -> DemoProduct:
        try:
            return self._products[product_id]
        except KeyError as error:
            raise KeyError(f"unknown product: {product_id}") from error

    def _upsert_inventory_alert(self, product: DemoProduct, result: ScanResult) -> None:
        alert_id = f"alert-{product.id}"
        existing = self._alerts.get(alert_id)
        if existing and existing.status not in {AlertStatus.RESOLVED}:
            existing.status = AlertStatus.REOPENED if existing.status == AlertStatus.PENDING_VERIFICATION else existing.status
            existing.last_seen_at = result.finished_at
            existing.failure_count += 1
            existing.ocr_text = result.ocr_text
            return

        self._alerts[alert_id] = AlertEvent(
            id=alert_id,
            type=AlertType.PRODUCT_ADD_TO_CART_MISSING,
            status=AlertStatus.OPEN,
            product_id=product.id,
            country=product.country,
            platform=product.platform,
            sku=product.sku,
            url=product.url,
            first_seen_at=result.started_at,
            last_seen_at=result.finished_at,
            full_screenshot_path=f"demo://screenshots/{product.id}/full.png",
            roi_screenshot_path=f"demo://screenshots/{product.id}/roi.png",
            ocr_text=result.ocr_text,
        )

    def _resolve_open_alert(self, product_id: str) -> None:
        alert = self._alerts.get(f"alert-{product_id}")
        if alert and alert.status != AlertStatus.RESOLVED:
            alert.status = AlertStatus.RESOLVED


def _demo_products() -> list[DemoProduct]:
    products: list[DemoProduct] = []
    for country, prefix in (("DE", "Germany"), ("IT", "Italy")):
        for index in range(1, 11):
            product_id = f"{country}-{index:03d}"
            products.append(
                DemoProduct(
                    id=product_id,
                    country=country,
                    platform="amazon" if index % 2 else "shopify",
                    sku=f"{country}-SKU-{index:03d}",
                    name=f"{prefix} home product {index}",
                    url=f"https://demo.local/{country.lower()}/product-{index:03d}",
                    roi_profile="product_detail_default",
                    demo_status="inventory_risk" if index == 1 else "healthy",
                )
            )
    return products
