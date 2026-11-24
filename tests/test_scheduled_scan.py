import asyncio
import unittest
from types import SimpleNamespace

from app.monitoring.adapters.memory_repositories import MemoryProductRepository
from app.monitoring.application.scheduled_scan import HourlyScanRunner
from app.monitoring.domain.models import Product, ProductScanStatus, ScanObservation


def product(product_id, enabled=True):
    return Product(
        id=product_id,
        country="DE",
        platform="amazon",
        sku=f"{product_id}-SKU",
        url="https://example.test/product",
        page_type="product_detail",
        roi_profile_id="default",
        enabled=enabled,
    )


class FakeScanProduct:
    def __init__(self, outcomes=None, delay=0.01):
        self.outcomes = outcomes or {}
        self.delay = delay
        self.active = 0
        self.max_active = 0
        self.calls = []

    async def execute(self, product_id):
        self.calls.append(product_id)
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        try:
            await asyncio.sleep(self.delay)
            status = self.outcomes.get(product_id, ProductScanStatus.HEALTHY)
            return SimpleNamespace(observation=ScanObservation(status=status))
        finally:
            self.active -= 1


class ScheduledScanTests(unittest.IsolatedAsyncioTestCase):
    async def test_run_once_scans_enabled_products_with_limited_concurrency(self):
        products = [product(f"DE-{index}") for index in range(5)] + [product("DE-disabled", False)]
        repository = MemoryProductRepository(products)
        scan_product = FakeScanProduct()
        runner = HourlyScanRunner(repository, scan_product, max_concurrency=3)

        summary = await runner.run_once()

        self.assertEqual(len(scan_product.calls), 5)
        self.assertLessEqual(scan_product.max_active, 3)
        self.assertEqual(summary.total, 5)
        self.assertEqual(summary.healthy, 5)
        self.assertEqual(summary.inventory_risk, 0)
        self.assertEqual(summary.technical_failure, 0)

    async def test_live_scheduler_skips_unsupported_products(self):
        supported = product("supported")
        other_market = product("other-market")
        other_market.country = "US"
        other_platform = product("other-platform")
        other_platform.platform = "temu"
        repository = MemoryProductRepository([supported, other_market, other_platform])
        scan_product = FakeScanProduct()

        result = await HourlyScanRunner(repository, scan_product, live_only=True).run_once()

        self.assertEqual(scan_product.calls, [supported.id])
        self.assertEqual(result.total, 1)
        self.assertEqual(other_market.status, ProductScanStatus.NOT_SCANNED)

    async def test_run_once_reports_inventory_and_technical_results(self):
        products = [product("DE-001"), product("DE-002"), product("DE-003")]
        repository = MemoryProductRepository(products)
        scan_product = FakeScanProduct(
            outcomes={
                "DE-001": ProductScanStatus.INVENTORY_RISK,
                "DE-002": ProductScanStatus.TECHNICAL_FAILURE,
            }
        )
        runner = HourlyScanRunner(repository, scan_product, max_concurrency=2)

        summary = await runner.run_once()

        self.assertEqual(summary.inventory_risk, 1)
        self.assertEqual(summary.technical_failure, 1)
        self.assertEqual(summary.healthy, 1)

    async def test_timeout_marks_product_as_technical_failure(self):
        current_product = product("DE-timeout")
        repository = MemoryProductRepository([current_product])
        scan_product = FakeScanProduct(delay=0.1)
        runner = HourlyScanRunner(
            repository,
            scan_product,
            max_concurrency=1,
            per_product_timeout_seconds=0.01,
        )

        summary = await runner.run_once()

        loaded = await repository.get(current_product.id)
        self.assertEqual(summary.technical_failure, 1)
        self.assertEqual(loaded.status, ProductScanStatus.TECHNICAL_FAILURE)


if __name__ == "__main__":
    unittest.main()
