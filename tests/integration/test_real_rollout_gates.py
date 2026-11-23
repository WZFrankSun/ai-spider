import json
import tempfile
import unittest
from pathlib import Path

from app.monitoring.adapters.product_catalog import JsonProductCatalogLoader
from app.monitoring.adapters.crawler_screenshot import JsonScreenshotManifestSource
from app.monitoring.runtime_config import MonitoringRuntimeConfig, validate_real_prerequisites


class RealRolloutGateTests(unittest.TestCase):
    def test_example_manifest_maps_to_example_catalog(self):
        catalog = JsonProductCatalogLoader().load("config/products.real.example.json")
        ids = {product.id for product in catalog}
        payload = json.loads(Path("config/screenshots.manifest.example.json").read_text(encoding="utf-8"))
        self.assertTrue({item["product_id"] for item in payload["screenshots"]} <= ids)

    def test_real_gate_rejects_missing_screenshot_root(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = MonitoringRuntimeConfig(
                mode="real",
                catalog_path=root / "products.json",
                screenshot_manifest_path=root / "manifest.json",
                screenshot_root=root / "missing-root",
                roi_profiles_path=root / "roi.json",
                phrase_sets_path=root / "phrases.json",
                database_url="sqlite+aiosqlite:///test.db",
                tesseract_cmd=str(root / "tesseract.exe"),
            )
            errors = validate_real_prerequisites(config)
        self.assertTrue(any("screenshot root" in error for error in errors))

    def test_demo_gate_remains_available_without_tesseract(self):
        self.assertEqual(validate_real_prerequisites(MonitoringRuntimeConfig(mode="demo")), [])


if __name__ == "__main__":
    unittest.main()
