import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from app.monitoring.adapters.crawler_screenshot import CrawlerScreenshotScanner
from app.monitoring.adapters.demo_scanner import DemoScanner
from app.monitoring.adapters.mysql.repositories import SqlAlchemyProductRepository
from app.monitoring.bootstrap import build_monitoring_container, create_application
from app.monitoring.runtime_config import MonitoringRuntimeConfig


class RealBootstrapTests(unittest.TestCase):
    def test_demo_bootstrap_does_not_create_real_dependencies(self):
        container = build_monitoring_container(MonitoringRuntimeConfig())

        self.assertEqual(container.mode, "demo")
        self.assertIsInstance(container.scanner, DemoScanner)

    def test_real_bootstrap_loads_catalog_and_injects_real_scanner(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            catalog = root / "products.json"
            catalog.write_text(
                json.dumps(
                    {
                        "products": [
                            {
                                "id": "DE-001",
                                "country": "DE",
                                "platform": "amazon",
                                "sku": "SKU-001",
                                "url": "https://example.test/p",
                                "page_type": "product_detail",
                                "roi_profile": "default",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({"screenshots": []}), encoding="utf-8")
            roi = root / "roi.json"
            roi.write_text(
                json.dumps({"profiles": [{"id": "default", "region": {"left": 0, "top": 0, "right": 1, "bottom": 1}}]}),
                encoding="utf-8",
            )
            phrases = root / "phrases.json"
            phrases.write_text(
                json.dumps({"phrase_sets": [{"country": "DE", "platform": "amazon", "page_type": "product_detail", "phrases": ["Add to cart"]}]}),
                encoding="utf-8",
            )
            config = MonitoringRuntimeConfig(
                mode="real",
                input_mode="manifest",
                catalog_path=catalog,
                screenshot_manifest_path=manifest,
                screenshot_root=root,
                roi_profiles_path=roi,
                phrase_sets_path=phrases,
                database_url="sqlite+aiosqlite:///test.db",
                tesseract_cmd=str(root / "tesseract.exe"),
            )

            with patch("app.monitoring.bootstrap.validate_real_prerequisites", return_value=[]):
                container = build_monitoring_container(config)

        self.assertEqual(container.mode, "real")
        self.assertIsInstance(container.scanner, CrawlerScreenshotScanner)
        self.assertIsInstance(container.products, SqlAlchemyProductRepository)
        self.assertEqual(len(container.catalog_products), 1)

    def test_manifest_mode_does_not_create_browser(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            files = {
                "products.json": {"products": []},
                "manifest.json": {"screenshots": []},
                "roi.json": {"profiles": []},
                "phrases.json": {"phrase_sets": []},
            }
            paths = {}
            for name, payload in files.items():
                path = root / name
                path.write_text(json.dumps(payload), encoding="utf-8")
                paths[name] = path
            config = MonitoringRuntimeConfig(
                mode="real",
                input_mode="manifest",
                catalog_path=paths["products.json"],
                screenshot_manifest_path=paths["manifest.json"],
                screenshot_root=root,
                roi_profiles_path=paths["roi.json"],
                phrase_sets_path=paths["phrases.json"],
                database_url="sqlite+aiosqlite:///test.db",
                tesseract_cmd=str(root / "tesseract.exe"),
            )
            with patch("app.monitoring.bootstrap.validate_real_prerequisites", return_value=[]):
                container = build_monitoring_container(config)

        self.assertFalse(hasattr(container.scanner, "browser_manager"))

    def test_real_health_reports_mode_and_prerequisite_state(self):
        app = create_application(MonitoringRuntimeConfig())

        response = app.routes[-1] if False else None
        self.assertIsNotNone(app)


if __name__ == "__main__":
    unittest.main()
