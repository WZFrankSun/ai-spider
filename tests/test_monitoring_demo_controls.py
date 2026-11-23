import asyncio
import unittest

from app.monitoring.adapters.demo_scanner import DemoScanner
from app.monitoring.adapters.memory_repositories import (
    MemoryAlertRepository,
    MemoryProductRepository,
    MemoryScanRepository,
)
from app.monitoring.application.scan_product import ScanInProgressError, ScanProduct
from app.monitoring.domain.models import Product, ProductScanStatus, ScanObservation


def product(product_id="DE-001"):
    return Product(
        id=product_id,
        country="DE",
        platform="amazon",
        sku=f"{product_id}-SKU",
        url=f"https://demo.local/{product_id}",
        page_type="product_detail",
        roi_profile_id="default",
    )


def use_case(products, scanner):
    return ScanProduct(
        MemoryProductRepository(products),
        MemoryScanRepository(),
        MemoryAlertRepository(),
        scanner,
    )


class BlockingScanner:
    def __init__(self):
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def scan(self, current_product):
        self.started.set()
        await self.release.wait()
        return ScanObservation(
            status=ProductScanStatus.HEALTHY,
            ocr_text="Add to cart",
            matched_phrase="Add to cart",
            confidence=0.99,
        )


class FailingScanner:
    async def scan(self, current_product):
        raise RuntimeError("scanner failed")


class DemoControlTests(unittest.IsolatedAsyncioTestCase):
    async def test_next_result_applies_once(self):
        current_product = product()
        scanner = DemoScanner([current_product])
        scanner.set_next_result(current_product.id, ProductScanStatus.HEALTHY)

        first = await scanner.scan(current_product)
        second = await scanner.scan(current_product)

        self.assertEqual(first.status, ProductScanStatus.HEALTHY)
        self.assertEqual(second.status, ProductScanStatus.INVENTORY_RISK)

    async def test_new_scanners_have_isolated_demo_overrides(self):
        current_product = product()
        first_scanner = DemoScanner([current_product])
        second_scanner = DemoScanner([current_product])
        first_scanner.set_next_result(current_product.id, ProductScanStatus.HEALTHY)

        self.assertEqual((await first_scanner.scan(current_product)).status, ProductScanStatus.HEALTHY)
        self.assertEqual((await second_scanner.scan(current_product)).status, ProductScanStatus.INVENTORY_RISK)

    async def test_next_result_rejects_intermediate_statuses(self):
        current_product = product()
        scanner = DemoScanner([current_product])

        with self.assertRaises(ValueError):
            scanner.set_next_result(current_product.id, ProductScanStatus.SCANNING)

    async def test_second_scan_is_rejected_while_first_scan_is_running(self):
        current_product = product()
        scanner = BlockingScanner()
        scan_product = use_case([current_product], scanner)

        first_task = asyncio.create_task(scan_product.execute(current_product.id))
        await scanner.started.wait()

        with self.assertRaises(ScanInProgressError):
            await scan_product.execute(current_product.id)

        scanner.release.set()
        await first_task

    async def test_cancelled_scan_clears_transient_status_and_releases_product(self):
        current_product = product()
        scanner = BlockingScanner()
        scan_product = use_case([current_product], scanner)
        task = asyncio.create_task(scan_product.execute(current_product.id))
        await scanner.started.wait()

        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task

        self.assertEqual(current_product.status, ProductScanStatus.TECHNICAL_FAILURE)
        self.assertFalse(scan_product.coordinator.is_active(current_product.id))

    async def test_completed_scan_clears_scanning_after_scanner_error(self):
        current_product = product()
        scan_product = use_case([current_product], FailingScanner())

        with self.assertRaisesRegex(RuntimeError, "scanner failed"):
            await scan_product.execute(current_product.id)

        self.assertEqual(current_product.status, ProductScanStatus.TECHNICAL_FAILURE)


if __name__ == "__main__":
    unittest.main()
