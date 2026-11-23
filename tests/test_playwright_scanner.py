import unittest
from datetime import datetime

from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from app.monitoring.adapters.playwright_scanner import (
    PlaywrightScanner,
    ScanErrorCode,
)
from app.monitoring.application.ports import ArtifactRef
from app.monitoring.adapters.ocr_tesseract import OcrError
from app.monitoring.domain.models import Product, ProductScanStatus, ScanObservation


def product() -> Product:
    return Product(
        id="DE-001",
        country="DE",
        platform="amazon",
        sku="SKU-001",
        url="https://example.test/product",
        page_type="product_detail",
        roi_profile_id="default",
    )


class FakePage:
    def __init__(self, *, goto_error=None, selector_error=None, screenshot_error=None):
        self.goto_error = goto_error
        self.selector_error = selector_error
        self.screenshot_error = screenshot_error
        self.goto_calls = []
        self.waited_selectors = []
        self.screenshot_calls = 0

    async def goto(self, url, **kwargs):
        self.goto_calls.append((url, kwargs))
        if self.goto_error:
            raise self.goto_error

    async def wait_for_selector(self, selector, **kwargs):
        self.waited_selectors.append((selector, kwargs))
        if self.selector_error:
            raise self.selector_error

    async def screenshot(self, **kwargs):
        self.screenshot_calls += 1
        if self.screenshot_error:
            raise self.screenshot_error
        return b"fake-png"

    async def title(self):
        return "Example product"


class FakeSession:
    def __init__(self, page):
        self.page = page
        self.session_id = "session-1"


class FakeBrowserManager:
    def __init__(self, page, *, start_error=None):
        self.page = page
        self.start_error = start_error
        self.started = False
        self.created = []
        self.closed = []

    async def start(self):
        if self.start_error:
            raise self.start_error
        self.started = True

    async def create_session(self, **kwargs):
        self.created.append(kwargs)
        return FakeSession(self.page)

    async def close_session(self, session_id):
        self.closed.append(session_id)


class RecordingArtifactStore:
    def __init__(self):
        self.saved = []

    async def save(self, content, metadata):
        self.saved.append((content, metadata))
        return ArtifactRef(
            artifact_id=f"{metadata.artifact_type}-1.png",
            path=f"/tmp/{metadata.artifact_type}-1.png",
        )

    async def delete(self, artifact_id):
        return None


class FakeRoiProfileLoader:
    def load(self, profile_id):
        return {"profile_id": profile_id}


class FakeRoiCropper:
    async def crop(self, screenshot, profile, page=None):
        return b"fake-roi"


class FakeProfile:
    browser = {"viewport": {"width": 1200, "height": 800}, "locale": "de-DE"}

    def resolve_ready_selectors(self, url):
        return ["#productTitle"]


class FakeRegistry:
    @classmethod
    def load(cls, name):
        return FakeProfile()


def healthy_observation(current_product, page, screenshot):
    return ScanObservation(
        status=ProductScanStatus.HEALTHY,
        ocr_text="Add to cart",
        matched_phrase="Add to cart",
        confidence=0.99,
    )


class PlaywrightScannerTests(unittest.IsolatedAsyncioTestCase):
    def build(self, page, *, observation_factory=healthy_observation, start_error=None):
        manager = FakeBrowserManager(page, start_error=start_error)
        scanner = PlaywrightScanner(
            browser_manager=manager,
            platform_registry=FakeRegistry,
            observation_factory=observation_factory,
            timeout_ms=1234,
        )
        return scanner, manager

    async def test_successful_page_scan_returns_observation_and_closes_session(self):
        scanner, manager = self.build(FakePage())

        observation = await scanner.scan(product())

        self.assertEqual(observation.status, ProductScanStatus.HEALTHY)
        self.assertEqual(observation.matched_phrase, "Add to cart")
        self.assertIsInstance(observation.started_at, datetime)
        self.assertIsInstance(observation.finished_at, datetime)
        self.assertLessEqual(observation.started_at, observation.finished_at)
        self.assertTrue(manager.started)
        self.assertEqual(manager.created[0]["locale"], "de-DE")
        self.assertEqual(manager.closed, ["session-1"])

    async def test_continues_shopping_before_validating_the_product_page(self):
        from unittest.mock import AsyncMock, Mock

        page = FakePage()
        button = Mock()
        button.count = AsyncMock(return_value=1)
        button.is_visible = AsyncMock(return_value=True)
        button.click = AsyncMock()
        selector = 'button:text-is("Weiter shoppen")'
        page.locator = Mock(return_value=Mock(first=button))
        original_wait = page.wait_for_selector

        async def wait_for_selector(*args, **kwargs):
            button.click.assert_awaited_once()
            await original_wait(*args, **kwargs)

        page.wait_for_selector = wait_for_selector
        scanner, _ = self.build(page)
        profile = FakeProfile()
        profile.location = {"continue_selectors": [selector]}
        scanner.platform_registry = Mock()
        scanner.platform_registry.load.return_value = profile

        observation = await scanner.scan(product())

        self.assertEqual(observation.status, ProductScanStatus.HEALTHY)
        page.locator.assert_called_once_with(selector)

    def test_amazon_continue_selectors_cover_italian_alternate_label(self):
        from app.platforms.registry import PlatformRegistry

        selectors = PlatformRegistry.load("amazon").location["continue_selectors"]
        self.assertIn('button:text-is("Continua con gli acquisti")', selectors)
        self.assertIn('input[type="submit"][value="Continua con gli acquisti"]', selectors)

    async def test_rejects_cookies_on_market_homepage_and_reopens_product(self):
        from unittest.mock import AsyncMock, Mock

        current_product = product()
        current_product.url = "https://www.amazon.de/dp/B07Q3DYMRD"
        page = FakePage()
        page.url = "https://www.amazon.de/"
        reject = Mock(
            click=AsyncMock(),
            wait_for=AsyncMock(side_effect=[None, None, PlaywrightTimeoutError("already dismissed")]),
        )
        page.locator = Mock(return_value=Mock(first=reject))
        scanner, _ = self.build(page)
        profile = FakeProfile()
        profile.cookies = {"reject": "#sp-cc-rejectall-link"}
        scanner.platform_registry = Mock()
        scanner.platform_registry.load.return_value = profile

        result = await scanner.scan(current_product)

        self.assertEqual(result.status, ProductScanStatus.HEALTHY)
        page.locator.assert_called_with("#sp-cc-rejectall-link")
        reject.click.assert_awaited_once()
        self.assertEqual([url for url, _ in page.goto_calls], [current_product.url] * 2)

    async def test_reopens_product_once_after_interrupted_homepage_navigation(self):
        from unittest.mock import AsyncMock
        from playwright.async_api import Error

        url = "https://www.amazon.de/dp/B07Q3DYMRD"
        page = FakePage()
        page.url = "https://www.amazon.de/"
        page.goto = AsyncMock(side_effect=[Error("interrupted by another navigation"), None])
        page.wait_for_load_state = AsyncMock()
        scanner, _ = self.build(page)

        await scanner._reopen_product(page, url)

        self.assertEqual(page.goto.await_count, 2)
        page.wait_for_load_state.assert_awaited_once()

    async def test_rechecks_cookies_after_product_page_loads(self):
        from unittest.mock import AsyncMock, Mock

        page = FakePage()
        page.url = "https://example.test/product"
        reject = Mock(
            wait_for=AsyncMock(side_effect=[PlaywrightTimeoutError("not ready"), None, None]),
            click=AsyncMock(),
        )
        page.locator = Mock(return_value=Mock(first=reject))
        scanner, _ = self.build(page)
        profile = FakeProfile()
        profile.cookies = {"reject": "#sp-cc-rejectall-link"}
        scanner.platform_registry = Mock()
        scanner.platform_registry.load.return_value = profile

        result = await scanner.scan(product())

        self.assertEqual(result.status, ProductScanStatus.HEALTHY)
        reject.click.assert_awaited_once()
        self.assertEqual(reject.wait_for.await_count, 3)

    async def test_continue_shopping_failure_preserves_diagnostic_screenshot(self):
        from unittest.mock import AsyncMock, Mock

        page = FakePage()
        button = Mock(
            count=AsyncMock(return_value=1),
            is_visible=AsyncMock(return_value=True),
            click=AsyncMock(side_effect=PlaywrightTimeoutError("click timed out")),
        )
        page.locator = Mock(return_value=Mock(first=button))
        scanner, _ = self.build(page)
        scanner.artifact_store = RecordingArtifactStore()
        profile = FakeProfile()
        profile.location = {"continue_selectors": ['button:text-is("Weiter shoppen")']}
        scanner.platform_registry = Mock()
        scanner.platform_registry.load.return_value = profile

        observation = await scanner.scan(product())

        self.assertEqual(observation.status, ProductScanStatus.TECHNICAL_FAILURE)
        self.assertEqual(observation.error_code, ScanErrorCode.READY_SELECTOR_FAILED)
        self.assertEqual(observation.full_screenshot_path, "/tmp/full-1.png")
        self.assertEqual(page.waited_selectors, [])

    async def test_navigation_timeout_maps_to_technical_failure(self):
        scanner, manager = self.build(FakePage(goto_error=PlaywrightTimeoutError("timed out")))

        observation = await scanner.scan(product())

        self.assertEqual(observation.status, ProductScanStatus.TECHNICAL_FAILURE)
        self.assertEqual(observation.error_code, ScanErrorCode.NAVIGATION_TIMEOUT)
        self.assertIsNotNone(observation.started_at)
        self.assertIsNotNone(observation.finished_at)
        self.assertEqual(manager.closed, ["session-1"])

    async def test_missing_ready_selector_maps_to_technical_failure(self):
        page = FakePage(selector_error=PlaywrightTimeoutError("selector missing"))
        scanner, _ = self.build(page)
        scanner.timeout_ms = 120_000
        scanner.artifact_store = RecordingArtifactStore()

        observation = await scanner.scan(product())

        self.assertEqual(observation.status, ProductScanStatus.TECHNICAL_FAILURE)
        self.assertEqual(observation.error_code, ScanErrorCode.READY_SELECTOR_MISSING)
        self.assertEqual(page.waited_selectors[0][1]["timeout"], 10_000)
        self.assertEqual(observation.full_screenshot_path, "/tmp/full-1.png")
        self.assertEqual(page.screenshot_calls, 1)

    async def test_screenshot_failure_maps_to_technical_failure(self):
        scanner, _ = self.build(FakePage(screenshot_error=OSError("disk full")))

        observation = await scanner.scan(product())

        self.assertEqual(observation.status, ProductScanStatus.TECHNICAL_FAILURE)
        self.assertEqual(observation.error_code, ScanErrorCode.SCREENSHOT_FAILED)

    async def test_page_success_without_result_factory_is_not_reported_as_healthy(self):
        scanner, _ = self.build(FakePage(), observation_factory=None)

        observation = await scanner.scan(product())

        self.assertEqual(observation.status, ProductScanStatus.TECHNICAL_FAILURE)
        self.assertEqual(observation.error_code, ScanErrorCode.OCR_NOT_CONFIGURED)

    async def test_observation_factory_preserves_ocr_error_code(self):
        def factory(current_product, page, screenshot):
            raise OcrError("OCR_TIMEOUT", "timed out")

        scanner, _ = self.build(FakePage(), observation_factory=factory)

        observation = await scanner.scan(product())

        self.assertEqual(observation.status, ProductScanStatus.TECHNICAL_FAILURE)
        self.assertEqual(observation.error_code, "OCR_TIMEOUT")

    async def test_full_and_roi_artifacts_are_saved_and_roi_is_sent_to_factory(self):
        page = FakePage()
        scanner, manager = self.build(FakePage())
        artifact_store = RecordingArtifactStore()
        received = []

        def factory(current_product, current_page, image):
            received.append(image)
            return healthy_observation(current_product, current_page, image)

        scanner = PlaywrightScanner(
            browser_manager=manager,
            platform_registry=FakeRegistry,
            observation_factory=factory,
            artifact_store=artifact_store,
            roi_profile_loader=FakeRoiProfileLoader(),
            roi_cropper=FakeRoiCropper(),
        )

        observation = await scanner.scan(product())

        self.assertEqual(observation.status, ProductScanStatus.HEALTHY)
        self.assertEqual(received, [b"fake-roi"])
        self.assertEqual([item[1].artifact_type for item in artifact_store.saved], ["full", "roi"])
        self.assertEqual(observation.full_screenshot_path, "/tmp/full-1.png")
        self.assertEqual(observation.roi_screenshot_path, "/tmp/roi-1.png")
        self.assertEqual(manager.closed, ["session-1"])


if __name__ == "__main__":
    unittest.main()
