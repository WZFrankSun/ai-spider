import unittest

from app.monitoring.application.retry_policy import scan_with_retry
from app.monitoring.domain.models import Product, ProductScanStatus, ScanObservation


def product():
    return Product(
        id="DE-001",
        country="DE",
        platform="amazon",
        sku="SKU-001",
        url="https://example.test/product",
        page_type="product_detail",
        roi_profile_id="default",
    )


class SequenceScanner:
    def __init__(self, observations):
        self.observations = list(observations)
        self.calls = 0

    async def scan(self, target):
        self.calls += 1
        return self.observations[min(self.calls - 1, len(self.observations) - 1)]


def observation(status):
    return ScanObservation(status=status)


class ScanRetryTests(unittest.IsolatedAsyncioTestCase):
    async def test_first_success_is_not_retried(self):
        scanner = SequenceScanner([observation(ProductScanStatus.HEALTHY)])

        result = await scan_with_retry(scanner, product(), attempts=3)

        self.assertEqual(result.status, ProductScanStatus.HEALTHY)
        self.assertEqual(scanner.calls, 1)

    async def test_technical_failure_retries_and_can_recover(self):
        scanner = SequenceScanner(
            [observation(ProductScanStatus.TECHNICAL_FAILURE), observation(ProductScanStatus.HEALTHY)]
        )

        result = await scan_with_retry(scanner, product(), attempts=3)

        self.assertEqual(result.status, ProductScanStatus.HEALTHY)
        self.assertEqual(scanner.calls, 2)

    async def test_three_failures_return_technical_failure(self):
        scanner = SequenceScanner(
            [observation(ProductScanStatus.TECHNICAL_FAILURE)] * 4
        )

        result = await scan_with_retry(scanner, product(), attempts=3)

        self.assertEqual(result.status, ProductScanStatus.TECHNICAL_FAILURE)
        self.assertEqual(scanner.calls, 3)

    async def test_missing_ready_selector_is_not_retried(self):
        failure = ScanObservation(
            status=ProductScanStatus.TECHNICAL_FAILURE,
            error_code="READY_SELECTOR_MISSING",
        )
        scanner = SequenceScanner([failure])

        result = await scan_with_retry(scanner, product(), attempts=3)

        self.assertIs(result, failure)
        self.assertEqual(scanner.calls, 1)

    async def test_inventory_risk_is_not_retried(self):
        scanner = SequenceScanner(
            [observation(ProductScanStatus.INVENTORY_RISK), observation(ProductScanStatus.HEALTHY)]
        )

        result = await scan_with_retry(scanner, product(), attempts=3)

        self.assertEqual(result.status, ProductScanStatus.INVENTORY_RISK)
        self.assertEqual(scanner.calls, 1)


if __name__ == "__main__":
    unittest.main()
