import unittest
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.monitoring.adapters.memory_repositories import (
    MemoryAlertRepository,
    MemoryProductRepository,
    MemoryScanRepository,
)
from app.monitoring.api.routes import MonitoringContainer, create_monitoring_app
from app.monitoring.domain.models import Product, ProductScanStatus, ScanObservation


class RealModeScanner:
    async def scan(self, product):
        now = datetime.now(timezone.utc)
        return ScanObservation(
            status=ProductScanStatus.HEALTHY,
            ocr_text="Add to cart",
            matched_phrase="Add to cart",
            confidence=0.97,
            started_at=now,
            finished_at=now,
            full_screenshot_path="output/DE/amazon/SKU-001/full.png",
            roi_screenshot_path="output/DE/amazon/SKU-001/roi.png",
        )


def real_container():
    products = MemoryProductRepository(
        [
            Product(
                id="DE-001",
                country="DE",
                platform="amazon",
                sku="SKU-001",
                url="https://example.test/product",
                page_type="product_detail",
                roi_profile_id="default",
            )
        ]
    )
    scans = MemoryScanRepository()
    alerts = MemoryAlertRepository()
    scanner = RealModeScanner()
    return MonitoringContainer.from_dependencies(
        products,
        scanner,
        scans=scans,
        alerts=alerts,
        mode="real",
    )


class RealScanApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(create_monitoring_app(real_container()))

    def test_health_reports_real_mode(self):
        response = self.client.get("/api/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["mode"], "real")

    def test_real_scan_returns_ocr_and_evidence_references(self):
        response = self.client.post("/api/products/DE-001/scan")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "healthy")
        self.assertEqual(payload["scan"]["matched_phrase"], "Add to cart")
        self.assertEqual(
            payload["scan"]["full_screenshot_path"],
            "output/DE/amazon/SKU-001/full.png",
        )
        self.assertEqual(
            payload["scan"]["roi_screenshot_path"],
            "output/DE/amazon/SKU-001/roi.png",
        )

    def test_demo_result_endpoint_is_not_available_in_real_mode(self):
        response = self.client.post(
            "/api/products/DE-001/demo-result",
            json={"result": "inventory_risk"},
        )

        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
