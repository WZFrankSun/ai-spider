import unittest

from fastapi.testclient import TestClient

from app.monitoring.api.routes import MonitoringContainer, create_monitoring_app


class ProductEntryTests(unittest.TestCase):
    def test_cross_store_duplicates_and_unsupported_scan(self):
        container = MonitoringContainer.demo()
        container.mode = "real"
        with TestClient(create_monitoring_app(container)) as client:
            payload = {
                "platform": "amazon", "country": "IT", "store_code": "H1-A1",
                "sku": "SKU-ENTRY", "name": "Test product", "added_by": "Frank",
                "url": "https://www.amazon.it/dp/B07Q3DYMRD?th=1",
            }
            first = client.post("/api/products", json=payload)
            self.assertEqual(first.status_code, 201)
            self.assertEqual(first.json()["asin"], "B07Q3DYMRD")
            self.assertEqual(first.json()["postal_code"], "00174")
            self.assertEqual(first.json()["target_postal_code"], "00174")
            self.assertIsNone(first.json()["scan_unavailable_reason"])
            for country, domain, postal, supported in (
                ("DE", "de", "10115", True),
                ("GB", "co.uk", "SW1A 1AA", True),
                ("ES", "es", "28001", True),
            ):
                response = client.post("/api/products", json={
                    **payload, "country": country,
                    "url": f"https://www.amazon.{domain}/dp/B07Q3DYMRD",
                })
                self.assertEqual(response.status_code, 201)
                row = response.json()
                self.assertEqual(row["target_postal_code"], postal)
                self.assertEqual(row["can_scan"], supported)
                self.assertEqual(bool(row["scan_unavailable_reason"]), not supported)
                if not supported:
                    self.assertIn("ES", row["scan_unavailable_reason"])
            self.assertEqual(client.post("/api/products", json=payload).status_code, 409)
            second = client.post("/api/products", json={**payload, "store_code": "H4-A1"})
            self.assertEqual(second.status_code, 201)
            self.assertNotEqual(first.json()["id"], second.json()["id"])
            no_country = client.post("/api/products", json={key: value for key, value in payload.items() if key != "country"})
            self.assertEqual(no_country.status_code, 422)
            self.assertIn("postal_code is required", no_country.json()["detail"][0]["msg"])
            wrong_site = client.post("/api/products", json={**payload, "country": "FR"})
            self.assertEqual(wrong_site.status_code, 422)
            disabled = client.post("/api/products", json={
                **payload, "platform": "temu", "url": "https://www.temu.com/goods.html?goods_id=123"
            })
            self.assertEqual(disabled.status_code, 201)
            self.assertFalse(disabled.json()["can_scan"])
            result = client.post(f'/api/products/{disabled.json()["id"]}/scan')
            self.assertEqual(result.status_code, 409)
            self.assertEqual(client.get("/api/scans").json(), [])
