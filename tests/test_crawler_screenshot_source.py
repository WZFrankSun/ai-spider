import io
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

from app.monitoring.adapters.crawler_screenshot import (
    CrawlerScreenshotScanner,
    JsonScreenshotManifestSource,
    ScreenshotManifestError,
)
from app.monitoring.adapters.roi import JsonRoiProfileLoader
from app.monitoring.domain.models import Product, ProductScanStatus, ScanObservation


def png_bytes():
    buffer = io.BytesIO()
    Image.new("RGB", (100, 80), "white").save(buffer, format="PNG")
    return buffer.getvalue()


def product():
    return Product(
        id="DE-001",
        country="DE",
        platform="amazon",
        sku="SKU-001",
        url="https://example.test/product",
        page_type="product_detail",
        roi_profile_id="default",
    )


class CrawlerScreenshotSourceTests(unittest.IsolatedAsyncioTestCase):
    def test_manifest_source_loads_screenshot_for_product(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            image = root / "de-001.png"
            image.write_bytes(png_bytes())
            manifest = root / "manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "screenshots": [
                            {
                                "product_id": "DE-001",
                                "path": "de-001.png",
                                "captured_at": "2026-11-20T00:00:00Z",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            source = JsonScreenshotManifestSource(manifest, root)
            content, record = source.load("DE-001")

        self.assertEqual(content, png_bytes())
        self.assertEqual(record.product_id, "DE-001")
        self.assertEqual(record.captured_at, datetime(2026, 11, 20, tzinfo=timezone.utc))

    def test_manifest_source_rejects_path_outside_root(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "screenshots"
            root.mkdir()
            manifest = Path(directory) / "manifest.json"
            manifest.write_text(
                json.dumps(
                    {"screenshots": [{"product_id": "DE-001", "path": "../secret.png"}]}
                ),
                encoding="utf-8",
            )

            with self.assertRaises(ScreenshotManifestError):
                JsonScreenshotManifestSource(manifest, root)

    def test_manifest_source_accepts_existing_crawler_screenshot_path_field(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            image = root / "crawl.png"
            image.write_bytes(png_bytes())
            manifest = root / "crawl-results.json"
            manifest.write_text(
                json.dumps({"screenshots": [{"id": "DE-001", "screenshot_path": "crawl.png"}]}),
                encoding="utf-8",
            )

            content, record = JsonScreenshotManifestSource(manifest, root).load("DE-001")

        self.assertEqual(content, png_bytes())
        self.assertEqual(record.path, str(image.resolve()))

    async def _scan(self, root: Path, manifest: Path, *, image_exists: bool = True):
        if image_exists:
            (root / "de-001.png").write_bytes(png_bytes())
        roi_file = root / "roi.json"
        roi_file.write_text(
            json.dumps(
                {
                    "profiles": [
                        {
                            "id": "default",
                            "region": {"left": 0, "top": 0, "right": 0.5, "bottom": 1},
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        manifest.write_text(
            json.dumps(
                {
                    "screenshots": [
                        {"product_id": "DE-001", "path": "de-001.png"}
                    ]
                }
            ),
            encoding="utf-8",
        )
        received = []

        async def factory(current_product, page, roi):
            received.append(roi)
            return ScanObservation(status=ProductScanStatus.HEALTHY, ocr_text="Add to cart")

        scanner = CrawlerScreenshotScanner(
            source=JsonScreenshotManifestSource(manifest, root),
            roi_profile_loader=JsonRoiProfileLoader(roi_file),
            observation_factory=factory,
        )
        return await scanner.scan(product()), received

    async def test_crawler_screenshot_scanner_maps_missing_file_to_technical_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / "manifest.json"
            observation, _ = await self._scan(root, manifest, image_exists=False)

        self.assertEqual(observation.status, ProductScanStatus.TECHNICAL_FAILURE)
        self.assertEqual(observation.error_code, "SCREENSHOT_NOT_FOUND")

    async def test_crawler_screenshot_scanner_passes_roi_bytes_to_ocr(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            observation, received = await self._scan(root, root / "manifest.json")

        self.assertEqual(observation.status, ProductScanStatus.HEALTHY)
        self.assertEqual(len(received), 1)
        self.assertLess(len(received[0]), len(png_bytes()))


if __name__ == "__main__":
    unittest.main()
