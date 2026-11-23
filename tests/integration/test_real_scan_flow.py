import io
import tempfile
import unittest
from datetime import datetime, timezone

from PIL import Image
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from app.monitoring.adapters.artifact_store_local import LocalArtifactStore
from app.monitoring.adapters.memory_repositories import (
    MemoryAlertRepository,
    MemoryProductRepository,
    MemoryScanRepository,
)
from app.monitoring.adapters.playwright_scanner import PlaywrightScanner
from app.monitoring.adapters.roi import RoiProfile
from app.monitoring.application.ports import ImageRegion, OcrResult
from app.monitoring.application.phrase_matching import match_add_to_cart
from app.monitoring.application.scan_product import ScanProduct
from app.monitoring.domain.models import Product, ProductScanStatus, ScanObservation


def screenshot_bytes():
    image = Image.new("RGB", (100, 80), "white")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
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


class FakeLocator:
    async def count(self):
        return 1

    async def is_visible(self):
        return True

    async def is_enabled(self):
        return True

    async def click(self, *, trial, timeout):
        assert trial is True

    async def screenshot(self, **kwargs):
        return screenshot_bytes()

    async def bounding_box(self):
        return {"x": 10, "y": 10, "width": 60, "height": 40}


class FakePage:
    def __init__(self, *, goto_error=None):
        self.goto_error = goto_error

    async def goto(self, url, **kwargs):
        if self.goto_error:
            raise self.goto_error

    async def wait_for_selector(self, selector, **kwargs):
        return None

    async def screenshot(self, **kwargs):
        return screenshot_bytes()

    def locator(self, selector):
        return FakeLocator()


class FakeSession:
    page = None
    session_id = "integration-session"

    def __init__(self, page):
        self.page = page


class FakeBrowserManager:
    def __init__(self, page):
        self.page = page

    async def start(self):
        return None

    async def create_session(self, **kwargs):
        return FakeSession(self.page)

    async def close_session(self, session_id):
        return None


class FakeProfile:
    browser = {"viewport": {"width": 100, "height": 80}, "locale": "de-DE"}

    def resolve_ready_selectors(self, url):
        return ["#productTitle"]


class FakeRegistry:
    @classmethod
    def load(cls, name):
        return FakeProfile()


class FakeOcr:
    def __init__(self, text):
        self.text = text

    async def recognize(self, image: ImageRegion) -> OcrResult:
        return OcrResult(text=self.text, confidence=0.95, language="eng+deu+ita")


class FakeRoiLoader:
    def load(self, profile_id):
        return RoiProfile.from_mapping(
            {"id": profile_id, "selector": "#buy-box", "region": {"left": 0, "top": 0, "right": 1, "bottom": 1}}
        )


class RealScanFlowTests(unittest.IsolatedAsyncioTestCase):
    async def test_fake_page_and_ocr_complete_healthy_flow_with_evidence(self):
        async def observation_factory(current_product, page, roi_bytes):
            ocr = await FakeOcr("In den Warenkorb").recognize(ImageRegion(roi_bytes))
            match = match_add_to_cart(ocr.text, ["In den Warenkorb"])
            now = datetime.now(timezone.utc)
            return ScanObservation(
                status=ProductScanStatus.HEALTHY if match.matched else ProductScanStatus.INVENTORY_RISK,
                ocr_text=ocr.text,
                matched_phrase=match.matched_phrase,
                confidence=ocr.confidence,
                started_at=now,
                finished_at=now,
            )

        with tempfile.TemporaryDirectory() as directory:
            scanner = PlaywrightScanner(
                browser_manager=FakeBrowserManager(FakePage()),
                platform_registry=FakeRegistry,
                observation_factory=observation_factory,
                artifact_store=LocalArtifactStore(directory),
                roi_profile_loader=FakeRoiLoader(),
            )
            products = MemoryProductRepository([product()])
            scans = MemoryScanRepository()
            alerts = MemoryAlertRepository()
            use_case = ScanProduct(products, scans, alerts, scanner)

            result = await use_case.execute("DE-001")

            self.assertEqual(result.product.status, ProductScanStatus.HEALTHY)
            self.assertEqual(result.observation.matched_phrase, "In den Warenkorb")
            self.assertIsNotNone(result.observation.full_screenshot_path)
            self.assertIsNotNone(result.observation.roi_screenshot_path)
            self.assertEqual(await alerts.list_all(), [])

    async def test_page_failure_stays_technical_and_does_not_create_inventory_alert(self):
        scanner = PlaywrightScanner(
            browser_manager=FakeBrowserManager(
                FakePage(goto_error=PlaywrightTimeoutError("timed out"))
            ),
            platform_registry=FakeRegistry,
        )
        products = MemoryProductRepository([product()])
        scans = MemoryScanRepository()
        alerts = MemoryAlertRepository()
        use_case = ScanProduct(products, scans, alerts, scanner)

        result = await use_case.execute("DE-001")

        self.assertEqual(result.product.status, ProductScanStatus.TECHNICAL_FAILURE)
        self.assertEqual(result.observation.error_code, "NAVIGATION_TIMEOUT")
        self.assertEqual(await alerts.list_all(), [])


if __name__ == "__main__":
    unittest.main()
