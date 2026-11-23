import unittest

from app.monitoring.domain.models import (
    Alert,
    AlertStatus,
    AlertType,
    Product,
    ProductScanStatus,
    ScanObservation,
)
from app.monitoring.domain.policies import can_resolve_alert


class MonitoringDomainTests(unittest.TestCase):
    def setUp(self):
        self.product = Product(
            id="DE-001",
            country="DE",
            platform="amazon",
            sku="DE-SKU-001",
            url="https://demo.local/de/product-001",
            page_type="product_detail",
            roi_profile_id="default",
            enabled=True,
        )

    def test_new_product_starts_not_scanned(self):
        self.assertEqual(self.product.status, ProductScanStatus.NOT_SCANNED)

    def test_healthy_observation_produces_healthy_status(self):
        observation = ScanObservation(
            status=ProductScanStatus.HEALTHY,
            ocr_text="Add to cart",
            matched_phrase="Add to cart",
            confidence=0.98,
        )

        self.assertEqual(observation.status, ProductScanStatus.HEALTHY)
        self.assertEqual(observation.matched_phrase, "Add to cart")

    def test_missing_phrase_is_inventory_risk(self):
        observation = ScanObservation(
            status=ProductScanStatus.INVENTORY_RISK,
            ocr_text="",
            matched_phrase=None,
            confidence=0.91,
        )

        self.assertEqual(observation.status, ProductScanStatus.INVENTORY_RISK)
        self.assertIsNone(observation.matched_phrase)

    def test_technical_failure_cannot_resolve_inventory_alert(self):
        alert = Alert(
            id="alert-DE-001",
            type=AlertType.PRODUCT_ADD_TO_CART_MISSING,
            status=AlertStatus.PENDING_VERIFICATION,
            product_id=self.product.id,
        )
        observation = ScanObservation(
            status=ProductScanStatus.TECHNICAL_FAILURE,
            error_code="PAGE_TIMEOUT",
            error_message="page did not load",
        )

        self.assertFalse(can_resolve_alert(alert, observation))
        self.assertEqual(alert.status, AlertStatus.PENDING_VERIFICATION)

    def test_only_healthy_observation_can_resolve_inventory_alert(self):
        alert = Alert(
            id="alert-DE-001",
            type=AlertType.PRODUCT_ADD_TO_CART_MISSING,
            status=AlertStatus.PENDING_VERIFICATION,
            product_id=self.product.id,
        )
        observation = ScanObservation(
            status=ProductScanStatus.HEALTHY,
            ocr_text="Add to cart",
            matched_phrase="Add to cart",
            confidence=0.99,
        )

        self.assertTrue(can_resolve_alert(alert, observation))

    def test_alert_apply_observation_does_not_resolve_without_pending_matched_health(self):
        alert = Alert(
            id="alert-DE-001",
            type=AlertType.PRODUCT_ADD_TO_CART_MISSING,
            status=AlertStatus.OPEN,
            product_id=self.product.id,
        )
        observation = ScanObservation(
            status=ProductScanStatus.HEALTHY,
            ocr_text="",
            matched_phrase=None,
        )

        alert.apply_observation(observation)

        self.assertEqual(alert.status, AlertStatus.OPEN)


if __name__ == "__main__":
    unittest.main()
