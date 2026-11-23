import unittest
from datetime import datetime, timezone

from app.monitoring.application.ports import Scanner, ScanTarget
from app.monitoring.domain.models import Product, ProductScanStatus, ScanObservation


class ScannerContractTests(unittest.IsolatedAsyncioTestCase):
    async def test_scanner_accepts_scan_target_and_returns_observation_with_timestamps(self):
        class FakeScanner:
            async def scan(self, target: ScanTarget) -> ScanObservation:
                now = datetime.now(timezone.utc)
                return ScanObservation(
                    status=ProductScanStatus.HEALTHY,
                    matched_phrase="Add to cart",
                    started_at=now,
                    finished_at=now,
                )

        target = Product(
            id="DE-001",
            country="DE",
            platform="amazon",
            sku="SKU-001",
            url="https://example.test/product",
            page_type="product_detail",
            roi_profile_id="default",
        )
        observation = await FakeScanner().scan(target)

        self.assertIsInstance(observation, ScanObservation)
        self.assertEqual(observation.status, ProductScanStatus.HEALTHY)
        self.assertIsNotNone(observation.started_at)
        self.assertIsNotNone(observation.finished_at)


if __name__ == "__main__":
    unittest.main()
