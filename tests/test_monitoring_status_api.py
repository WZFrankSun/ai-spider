import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from app.monitoring.api.routes import MonitoringContainer, create_monitoring_app
from app.monitoring.runtime_config import MonitoringRuntimeConfig


class MonitoringStatusApiTests(unittest.TestCase):
    def test_demo_status_is_ready_without_tesseract(self):
        client = TestClient(create_monitoring_app(MonitoringContainer.demo()))
        payload = client.get("/api/monitoring/status").json()
        self.assertEqual(payload["mode"], "demo")
        self.assertTrue(payload["preflight"]["ready"])

    def test_real_status_lists_missing_tesseract_and_files(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            config = MonitoringRuntimeConfig(
                mode="real",
                catalog_path=root / "missing-products.json",
                screenshot_manifest_path=root / "missing-manifest.json",
                roi_profiles_path=root / "missing-roi.json",
                phrase_sets_path=root / "missing-phrases.json",
            )
            container = MonitoringContainer.demo()
            container.mode = "real"
            client = TestClient(create_monitoring_app(container, monitoring_config=config))
            payload = client.get("/api/monitoring/status").json()

        self.assertFalse(payload["preflight"]["ready"])
        self.assertTrue(any("Tesseract" in item for item in payload["preflight"]["missing"]))

    def test_status_does_not_include_database_credentials(self):
        config = MonitoringRuntimeConfig(mode="real", database_url="mysql://user:secret@host/db")
        container = MonitoringContainer.demo()
        container.mode = "real"
        client = TestClient(create_monitoring_app(container, monitoring_config=config))
        text = client.get("/api/monitoring/status").text
        self.assertNotIn("secret", text)
        self.assertNotIn("mysql://", text)


if __name__ == "__main__":
    unittest.main()
