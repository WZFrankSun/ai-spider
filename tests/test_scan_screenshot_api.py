import io
import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient
from PIL import Image

from app.monitoring.adapters.memory_repositories import MemoryAlertRepository, MemoryProductRepository, MemoryScanRepository
from app.monitoring.api.routes import MonitoringContainer, create_monitoring_app
from app.monitoring.domain.models import Product, ProductScanStatus, Scan, ScanObservation


class ScreenshotApiTests(unittest.TestCase):
    def test_scan_history_returns_relative_screenshot_urls(self):
        with TemporaryDirectory(dir="output/artifacts") as directory:
            root = Path(directory); full = root / "full.png"; roi = root / "roi.png"
            Image.new("RGB", (4, 4), "white").save(full); Image.new("RGB", (2, 2), "white").save(roi)
            now = datetime.now(timezone.utc)
            product = Product("DE-001", "DE", "amazon", "SKU", "https://example.test", "product_detail", "default")
            scan = Scan("scan-001", product.id, ProductScanStatus.HEALTHY, ScanObservation(ProductScanStatus.HEALTHY, ocr_text="Add to basket", matched_phrase="Add to basket", full_screenshot_path=str(full), roi_screenshot_path=str(roi), started_at=now, finished_at=now), now, now)
            products=MemoryProductRepository([product]); scans=MemoryScanRepository(); alerts=MemoryAlertRepository()
            import asyncio
            asyncio.run(scans.add(scan))
            container=MonitoringContainer.from_dependencies(products, object(), scans=scans, alerts=alerts, mode="real")
            client=TestClient(create_monitoring_app(container))
            payload=client.get("/api/scans").json()[0]
            self.assertEqual(payload["screenshots"]["full_url"], "/api/scans/scan-001/screenshots/full")
            self.assertEqual(client.get(payload["screenshots"]["full_url"]).headers["content-type"], "image/png")

    def test_screenshot_path_traversal_is_rejected(self):
        product=Product("DE-001", "DE", "amazon", "SKU", "https://example.test", "product_detail", "default")
        now=datetime.now(timezone.utc)
        scan=Scan("scan-evil", product.id, ProductScanStatus.HEALTHY, ScanObservation(ProductScanStatus.HEALTHY, full_screenshot_path=str(Path("output/artifacts") / ".." / ".env"), started_at=now, finished_at=now), now, now)
        products=MemoryProductRepository([product]); scans=MemoryScanRepository(); alerts=MemoryAlertRepository()
        import asyncio
        asyncio.run(scans.add(scan))
        client=TestClient(create_monitoring_app(MonitoringContainer.from_dependencies(products, object(), scans=scans, alerts=alerts, mode="real")))
        self.assertEqual(client.get("/api/scans/scan-evil/screenshots/full").status_code, 404)


if __name__ == "__main__": unittest.main()
