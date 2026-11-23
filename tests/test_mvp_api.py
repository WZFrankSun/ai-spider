import unittest

from fastapi.testclient import TestClient

from app.mvp.api import create_app


class MvpApiTests(unittest.TestCase):
    def test_health_and_product_listing(self):
        client = TestClient(create_app())

        self.assertEqual(client.get("/api/health").json(), {"status": "ok", "mode": "demo"})
        response = client.get("/api/products")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 20)


    def test_scan_alert_and_verification_flow(self):
        client = TestClient(create_app())

        scan = client.post("/api/products/DE-001/scan")
        self.assertEqual(scan.status_code, 200)
        self.assertEqual(scan.json()["status"], "inventory_risk")

        alerts = client.get("/api/alerts").json()
        self.assertEqual(len(alerts), 1)

        verify = client.post("/api/alerts/alert-DE-001/verify")
        self.assertEqual(verify.status_code, 200)
        self.assertEqual(verify.json()["status"], "resolved")


    def test_unknown_product_returns_not_found(self):
        client = TestClient(create_app())

        response = client.post("/api/products/unknown/scan")

        self.assertEqual(response.status_code, 404)
