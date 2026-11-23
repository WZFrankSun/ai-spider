import asyncio
import unittest

from fastapi.testclient import TestClient

from app.monitoring.api.routes import MonitoringContainer, create_monitoring_app
from app.monitoring.domain.models import ProductScanStatus


class MonitoringApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(create_monitoring_app())

    def test_health_returns_demo_mode(self):
        response = self.client.get("/api/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok", "mode": "demo"})

    def test_products_start_not_scanned_and_include_both_countries(self):
        response = self.client.get("/api/products")

        self.assertEqual(response.status_code, 200)
        products = response.json()
        self.assertEqual(len(products), 20)
        self.assertEqual({product["country"] for product in products}, {"DE", "IT"})
        self.assertTrue(all(product["status"] == "not_scanned" for product in products))

    def test_demo_result_switch_changes_next_scan(self):
        configured = self.client.post(
            "/api/products/DE-001/demo-result",
            json={"result": "healthy"},
        )
        scan = self.client.post("/api/products/DE-001/scan")

        self.assertEqual(configured.status_code, 200)
        self.assertEqual(configured.json()["next_result"], "healthy")
        self.assertEqual(scan.status_code, 200)
        self.assertEqual(scan.json()["status"], "healthy")

    def test_scan_creates_one_alert_and_repeated_scan_deduplicates(self):
        first = self.client.post("/api/products/DE-001/scan")
        second = self.client.post("/api/products/DE-001/scan")
        alerts = self.client.get("/api/alerts").json()

        self.assertEqual(first.json()["status"], "inventory_risk")
        self.assertEqual(second.json()["status"], "inventory_risk")
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["failure_count"], 2)

    def test_technical_failure_does_not_close_inventory_alert(self):
        self.client.post("/api/products/DE-001/scan")
        self.client.post(
            "/api/products/DE-001/demo-result",
            json={"result": "technical_failure"},
        )

        response = self.client.post("/api/alerts/alert-DE-001/verify")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "pending_verification")

    def test_unknown_product_and_alert_return_404(self):
        product_response = self.client.post("/api/products/unknown/scan")
        alert_response = self.client.post("/api/alerts/unknown/verify")

        self.assertEqual(product_response.status_code, 404)
        self.assertEqual(alert_response.status_code, 404)

    def test_stale_scanning_status_allows_retry(self):
        container = MonitoringContainer.demo()
        client = TestClient(create_monitoring_app(container))
        product = asyncio.run(container.products.get("DE-001"))
        product.status = ProductScanStatus.SCANNING
        asyncio.run(container.products.save(product))

        products = client.get("/api/products").json()
        status = next(row["status"] for row in products if row["id"] == product.id)
        self.assertEqual(status, "technical_failure")
        self.assertEqual(client.post("/api/products/DE-001/scan").status_code, 200)

    def test_verify_returns_409_when_product_is_scanning(self):
        container = MonitoringContainer.demo()
        client = TestClient(create_monitoring_app(container))
        scan = client.post("/api/products/DE-001/scan")
        self.assertEqual(scan.status_code, 200)

        container.scan_product.coordinator.acquire("DE-001")

        response = client.post("/api/alerts/alert-DE-001/verify")

        self.assertEqual(response.status_code, 409)

    def test_demo_entry_exposes_monitoring_demo_result_endpoint(self):
        from app.monitoring.api.routes import create_demo_app

        client = TestClient(create_demo_app())
        response = client.post(
            "/api/products/DE-001/demo-result",
            json={"result": "healthy"},
        )

        self.assertEqual(response.status_code, 200)


if __name__ == "__main__":
    unittest.main()
