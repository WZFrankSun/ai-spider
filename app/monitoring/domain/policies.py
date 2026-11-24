from app.monitoring.config.markets import LIVE_AMAZON_COUNTRIES
from .models import Alert, AlertStatus, AlertType, ProductScanStatus, ScanObservation


def can_resolve_alert(alert: Alert, observation: ScanObservation) -> bool:
    return (
        alert.type == AlertType.PRODUCT_ADD_TO_CART_MISSING
        and alert.status == AlertStatus.PENDING_VERIFICATION
        and observation.status == ProductScanStatus.HEALTHY
        and bool(observation.matched_phrase)
    )


def supports_live_scan(product) -> bool:
    return product.platform == "amazon" and product.country in LIVE_AMAZON_COUNTRIES
