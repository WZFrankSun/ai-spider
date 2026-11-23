import json
import tempfile
import unittest
from pathlib import Path

from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from app.monitoring.application.ports import OcrResult
from app.monitoring.application.real_observation import RealObservationFactory
from app.monitoring.domain.models import Product, ProductScanStatus


class FakeOcr:
    def __init__(self, text): self.text = text
    async def recognize(self, image): return OcrResult(text=self.text, confidence=0.93)


class FakeLocator:
    def __init__(self, count=1, visible=True, enabled=True): self._count=count; self._visible=visible; self._enabled=enabled
    async def count(self): return self._count
    async def is_visible(self): return self._visible
    async def is_enabled(self): return self._enabled

    async def click(self, *, trial, timeout):
        assert trial is True
        if self.blocked:
            raise PlaywrightTimeoutError("button is covered")

    blocked = False


class FakePage:
    def __init__(self, *, count=1, visible=True, enabled=True): self.locator_value=FakeLocator(count, visible, enabled)
    def locator(self, selector):
        self.selector=selector
        return self.locator_value


def product():
    return Product("DE-amazon-001", "DE", "amazon", "TEMP-ASIN", "https://example.test", "product_detail", "default")


class CrossValidationTests(unittest.IsolatedAsyncioTestCase):
    def factory(self, text):
        path=Path(tempfile.mkdtemp())/"phrases.json"
        path.write_text(json.dumps({"phrase_sets":[{"country":"DE","platform":"amazon","page_type":"product_detail","phrases":["In den Einkaufswagen","In den Warenkorb","Add to basket","Add to cart"]}]}), encoding="utf-8")
        return RealObservationFactory(FakeOcr(text), path)

    async def test_english_add_to_basket_is_healthy(self):
        result=await self.factory("Add to basket")(product(), FakePage(), b"roi")
        self.assertEqual(result.status, ProductScanStatus.HEALTHY)
        self.assertEqual(result.matched_phrase, "Add to basket")

    async def test_usable_button_without_ocr_match_is_healthy(self):
        result=await self.factory("Buy now")(product(), FakePage(), b"roi")
        self.assertEqual(result.status, ProductScanStatus.HEALTHY)
        self.assertEqual(result.error_code, "DOM_OCR_MISMATCH")

    async def test_multiple_button_candidates_can_include_one_usable_offer(self):
        page = FakePage(count=2)
        covered = FakeLocator()
        covered.blocked = True
        usable = FakeLocator()
        page.locator_value.nth = [covered, usable].__getitem__

        result = await self.factory("Add to basket")(product(), page, b"roi")

        self.assertEqual(result.status, ProductScanStatus.HEALTHY)

    async def test_roi_uses_the_same_actionable_candidate(self):
        from unittest.mock import AsyncMock
        from app.monitoring.adapters.playwright_scanner import PlaywrightScanner

        page = FakePage(count=2)
        covered = FakeLocator()
        covered.blocked = True
        covered.screenshot = AsyncMock(return_value=b"covered")
        usable = FakeLocator()
        usable.screenshot = AsyncMock(return_value=b"usable")
        page.locator_value.nth = [covered, usable].__getitem__

        roi = await PlaywrightScanner()._crop_product_roi(product(), page, b"full", None)

        self.assertEqual(roi, b"usable")
        covered.screenshot.assert_not_called()

    async def test_covered_button_is_technical_failure(self):
        page = FakePage()
        page.locator_value.blocked = True
        result = await self.factory("Add to basket")(product(), page, b"roi")
        self.assertEqual(result.status, ProductScanStatus.TECHNICAL_FAILURE)
        self.assertEqual(result.error_code, "DOM_BUTTON_UNVERIFIED")

    async def test_confirmed_absence_takes_priority_over_ocr_cart_text(self):
        for page in (FakePage(count=0), FakePage(enabled=False)):
            result = await self.factory("Add to basket")(product(), page, b"roi")
            self.assertEqual(result.status, ProductScanStatus.INVENTORY_RISK)

    async def test_ocr_error_is_diagnostic_when_button_is_usable(self):
        from unittest.mock import AsyncMock

        factory = self.factory("")
        factory.ocr.recognize = AsyncMock(side_effect=RuntimeError("OCR error"))
        result = await factory(product(), FakePage(), b"roi")
        self.assertEqual(result.status, ProductScanStatus.HEALTHY)
        self.assertEqual(result.error_code, "OCR_FAILED")

    async def test_confirmed_absence_takes_priority_over_ocr_failure(self):
        from unittest.mock import AsyncMock

        factory = self.factory("")
        factory.ocr.recognize = AsyncMock(side_effect=RuntimeError("OCR error"))
        result = await factory(product(), FakePage(count=0), b"roi")
        self.assertEqual(result.status, ProductScanStatus.INVENTORY_RISK)
        self.assertEqual(result.error_code, "OCR_FAILED")

    async def test_ocr_only_requires_unavailability_without_cart_text(self):
        path = Path(__file__).resolve().parents[1] / "config" / "phrase_sets.json"
        for country, unavailable, cart in (
            ("DE", "DERZEIT\nNICHT VERFÜGBAR", "In den Einkaufswagen"),
            ("IT", "Attualmente non disponibile", "Aggiungi al carrello"),
            ("FR", "Actuellement indisponible", "Ajouter au panier"),
            ("DE", "Temporarily out of stock", "Add to basket"),
        ):
            item = product()
            item.country = country
            with self.subTest(country=country, text=unavailable):
                result = await RealObservationFactory(FakeOcr(unavailable), path)(item, None, b"roi")
                self.assertEqual(result.status, ProductScanStatus.INVENTORY_RISK)
                self.assertIsNone(result.matched_phrase)
                mixed = await RealObservationFactory(FakeOcr(f"{unavailable} {cart}"), path)(item, None, b"roi")
                self.assertEqual(mixed.status, ProductScanStatus.TECHNICAL_FAILURE)

    async def test_missing_dom_and_missing_ocr_is_inventory_risk(self):
        result=await self.factory("Buy now")(product(), FakePage(count=0), b"roi")
        self.assertEqual(result.status, ProductScanStatus.INVENTORY_RISK)


if __name__ == "__main__": unittest.main()
