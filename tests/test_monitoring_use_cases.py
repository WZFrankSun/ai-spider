import asyncio
import unittest

from app.monitoring.adapters.demo_scanner import DemoScanner
from app.monitoring.adapters.memory_repositories import (
    MemoryAlertRepository,
    MemoryProductRepository,
    MemoryScanRepository,
)
from app.monitoring.application.scan_product import ScanCoordinator, ScanInProgressError, ScanProduct
from app.monitoring.application.verify_alert import VerifyAlert
from app.monitoring.domain.models import (
    Alert,
    AlertStatus,
    AlertType,
    Product,
    ProductScanStatus,
    ScanObservation,
)


def demo_products():
    return [
        Product(
            id="DE-001",
            country="DE",
            platform="amazon",
            sku="DE-SKU-001",
            url="https://demo.local/de/product-001",
            page_type="product_detail",
            roi_profile_id="default",
        ),
        Product(
            id="DE-002",
            country="DE",
            platform="shopify",
            sku="DE-SKU-002",
            url="https://demo.local/de/product-002",
            page_type="product_detail",
            roi_profile_id="default",
        ),
    ]


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


class MonitoringUseCaseTests(unittest.IsolatedAsyncioTestCase):
    def build(self, outcomes=None):
        products = demo_products()
        product_repo = MemoryProductRepository(products)
        scan_repo = MemoryScanRepository()
        alert_repo = MemoryAlertRepository()
        scanner = DemoScanner(products, outcomes=outcomes)
        coordinator = ScanCoordinator()
        scan_product = ScanProduct(product_repo, scan_repo, alert_repo, scanner, coordinator)
        verify_alert = VerifyAlert(product_repo, scan_repo, alert_repo, scanner, coordinator)
        return product_repo, scan_repo, alert_repo, scanner, scan_product, verify_alert

    async def test_demo_scanner_returns_default_health_and_inventory_results(self):
        _, _, _, scanner, _, _ = self.build()

        risk = await scanner.scan((await self.build()[0].get("DE-001")))
        healthy = await scanner.scan((await self.build()[0].get("DE-002")))

        self.assertEqual(risk.status, ProductScanStatus.INVENTORY_RISK)
        self.assertEqual(healthy.status, ProductScanStatus.HEALTHY)

    async def test_first_inventory_risk_scan_creates_one_alert(self):
        _, _, alert_repo, _, scan_product, _ = self.build()

        result = await scan_product.execute("DE-001")

        self.assertEqual(result.observation.status, ProductScanStatus.INVENTORY_RISK)
        alerts = await alert_repo.list_all()
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].failure_count, 1)

    async def test_repeated_inventory_risk_updates_same_alert(self):
        _, _, alert_repo, _, scan_product, _ = self.build()

        await scan_product.execute("DE-001")
        await scan_product.execute("DE-001")

        alerts = await alert_repo.list_all()
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].failure_count, 2)

    async def test_technical_failure_does_not_create_inventory_alert(self):
        _, _, alert_repo, _, scan_product, _ = self.build(
            {"DE-002": ProductScanStatus.TECHNICAL_FAILURE}
        )

        result = await scan_product.execute("DE-002")

        self.assertEqual(result.observation.status, ProductScanStatus.TECHNICAL_FAILURE)
        self.assertEqual(await alert_repo.list_all(), [])

    async def test_healthy_verification_resolves_alert(self):
        _, _, alert_repo, scanner, scan_product, verify_alert = self.build()
        await scan_product.execute("DE-001")
        scanner.set_outcome("DE-001", ProductScanStatus.HEALTHY)

        alert = await verify_alert.execute("alert-DE-001")

        self.assertEqual(alert.status.value, "resolved")

    async def test_technical_failure_verification_keeps_alert_pending(self):
        _, _, alert_repo, scanner, scan_product, verify_alert = self.build()
        await scan_product.execute("DE-001")
        scanner.set_outcome("DE-001", ProductScanStatus.TECHNICAL_FAILURE)

        alert = await verify_alert.execute("alert-DE-001")

        self.assertEqual(alert.status.value, "pending_verification")
        self.assertEqual((await alert_repo.get("alert-DE-001")).status.value, "pending_verification")

    async def test_verification_is_rejected_while_scan_is_running(self):
        products = demo_products()
        product_repo = MemoryProductRepository(products)
        scan_repo = MemoryScanRepository()
        alert_repo = MemoryAlertRepository()
        scanner = BlockingScanner()
        coordinator = ScanCoordinator()
        scan_product = ScanProduct(product_repo, scan_repo, alert_repo, scanner, coordinator)
        verify_alert = VerifyAlert(product_repo, scan_repo, alert_repo, scanner, coordinator)

        await alert_repo.save(
            Alert(
                id="alert-DE-001",
                type=AlertType.PRODUCT_ADD_TO_CART_MISSING,
                status=AlertStatus.OPEN,
                product_id="DE-001",
            )
        )
        running = asyncio.create_task(scan_product.execute("DE-001"))
        await scanner.started.wait()

        with self.assertRaises(ScanInProgressError):
            await verify_alert.execute("alert-DE-001")

        scanner.release.set()
        await running

    async def test_inventory_risk_verification_reopens_alert(self):
        _, _, alert_repo, scanner, scan_product, verify_alert = self.build()
        await scan_product.execute("DE-001")
        scanner.set_outcome("DE-001", ProductScanStatus.INVENTORY_RISK)

        alert = await verify_alert.execute("alert-DE-001")

        self.assertEqual(alert.status.value, "reopened")

    async def test_unknown_product_is_rejected(self):
        _, _, _, _, scan_product, _ = self.build()

        with self.assertRaises(KeyError):
            await scan_product.execute("unknown")


if __name__ == "__main__":
    unittest.main()
