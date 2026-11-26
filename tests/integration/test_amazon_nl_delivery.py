import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock

from app.browser.browser_manager import BrowserManager
from app.monitoring.adapters.artifact_store_local import LocalArtifactStore
from app.monitoring.adapters.ocr_tesseract import TesseractOcrAdapter
from app.monitoring.adapters.playwright_scanner import PlaywrightScanner, ScanErrorCode
from app.monitoring.adapters.roi import JsonRoiProfileLoader
from app.monitoring.application.real_observation import RealObservationFactory
from app.monitoring.domain.models import Product, ProductScanStatus
from app.monitoring.runtime_config import load_monitoring_config


PAGE = """<html lang="nl"><body style="margin:0">
<header><span id="glow-ingress-block">Bezorging naar Duitsland</span>
<button id="nav-global-location-popover-link" onclick="box.hidden=false">Locatie</button></header>
<div id="box" role="dialog" hidden>
  <input id="GLUXZipUpdateInput">
  <div id="GLUXZipUpdate"><button class="a-button-input" onclick="done.hidden=false">Toepassen</button></div>
  <button id="done" hidden onclick="applyPostal()">Gereed</button>
</div>
<main id="product" style="margin:220px 40px 30px">
  <h1 id="productTitle">Testproduct</h1>
  <div id="rightCol"><button id="add-to-cart-button"
    style="width:300px;height:64px;background:#ffd814;border:0;font:26px Arial"
    onclick="throw new Error('Unexpected actual cart click')">In winkelwagen</button></div>
</main>
<script>
function applyPostal() {
  box.hidden = true;
  product.hidden = true;
  setTimeout(() => {
    document.getElementById('glow-ingress-block').textContent =
      'Bezorging aan ' + document.getElementById('GLUXZipUpdateInput').value;
    product.hidden = false;
  }, 350);
}
</script></body></html>"""


class NetherlandsDeliveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_nl_default_postal_readback_and_healthy_evidence(self):
        await self.check_delivery(readback_matches=True)

    async def test_nl_mismatched_readback_blocks_evidence_and_keeps_diagnostic(self):
        await self.check_delivery(readback_matches=False)

    async def check_delivery(self, *, readback_matches):
        config = load_monitoring_config()
        if readback_matches and (not config.tesseract_cmd or not Path(config.tesseract_cmd).is_file()):
            self.skipTest("Project Tesseract executable unavailable")
        observed = {}
        html = PAGE if readback_matches else PAGE.replace(
            "document.getElementById('GLUXZipUpdateInput').value", "'9999'"
        )
        if readback_matches:
            observation_factory = RealObservationFactory(
                TesseractOcrAdapter(lang=config.tesseract_languages, tesseract_cmd=config.tesseract_cmd),
                config.phrase_sets_path,
            )
        else:
            observation_factory = AsyncMock()

        class FixtureBrowser(BrowserManager):
            async def create_session(self, **kwargs):
                session = await super().create_session(**kwargs)

                async def serve(route):
                    await route.fulfill(content_type="text/html; charset=utf-8", body=html)

                await session.page.route("https://www.amazon.nl/dp/**", serve)
                observed["page"] = session.page
                return session

            async def close_session(self, session_id):
                page = observed["page"]
                observed["postal"] = await page.locator("#glow-ingress-block").inner_text()
                observed["input"] = await page.locator("#GLUXZipUpdateInput").input_value()
                await super().close_session(session_id)

        browser = FixtureBrowser()
        try:
            with tempfile.TemporaryDirectory() as folder:
                scanner = PlaywrightScanner(
                    browser_manager=browser,
                    observation_factory=observation_factory,
                    roi_profile_loader=JsonRoiProfileLoader(config.roi_profiles_path),
                    artifact_store=LocalArtifactStore(folder),
                    delivery_diagnostic_root=Path(folder) / "delivery",
                )
                item = Product(
                    "NL-fixture", "NL", "amazon", "nl-test",
                    "https://www.amazon.nl/dp/B07Q3DYMRD", "product_detail",
                    "amazon_product_detail_nl_buy_box",
                )
                result = await scanner.scan(item)
                self.assertEqual(observed["input"], "1012")
                if not readback_matches:
                    self.assertEqual(observed["postal"], "Bezorging aan 9999")
                    self.assertEqual(result.status, ProductScanStatus.TECHNICAL_FAILURE)
                    self.assertEqual(result.error_code, ScanErrorCode.DELIVERY_REGION_UNVERIFIED)
                    self.assertIsNone(result.roi_screenshot_path)
                    observation_factory.assert_not_called()
                    self.assertTrue(
                        (Path(folder) / "delivery/NL/amazon/NL-fixture/delivery_failed.png").is_file()
                    )
                    return

                self.assertEqual(result.status, ProductScanStatus.HEALTHY, result.error_message)
                self.assertEqual(result.matched_phrase, "In winkelwagen")
                self.assertEqual(observed["postal"], "Bezorging aan 1012")
                self.assertTrue(Path(result.full_screenshot_path).is_file())
                self.assertTrue(Path(result.roi_screenshot_path).is_file())
        finally:
            await browser.close()
