import asyncio
import json
import tempfile
import unittest
from pathlib import Path

from app.monitoring.adapters.ocr_tesseract import OcrError
from app.monitoring.application.ports import ImageRegion, OcrResult
from app.monitoring.application.real_observation import RealObservationFactory
from app.monitoring.domain.models import Product, ProductScanStatus


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


class FakeOcr:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error

    async def recognize(self, image: ImageRegion) -> OcrResult:
        if self.error:
            raise self.error
        return self.result


class RealObservationTests(unittest.IsolatedAsyncioTestCase):
    async def test_ocr_only_returns_phrase_without_healthy_status(self):
        with tempfile.TemporaryDirectory() as directory:
            phrase_file = Path(directory) / "phrases.json"
            phrase_file.write_text(
                json.dumps(
                    {
                        "phrase_sets": [
                            {
                                "country": "DE",
                                "platform": "amazon",
                                "page_type": "product_detail",
                                "phrases": ["In den Warenkorb"],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            factory = RealObservationFactory(
                FakeOcr(OcrResult(text="In den Warenkorb", confidence=0.91)),
                phrase_file,
            )

            observation = await factory(product(), None, b"roi")

        self.assertEqual(observation.status, ProductScanStatus.TECHNICAL_FAILURE)
        self.assertEqual(observation.matched_phrase, "In den Warenkorb")
        self.assertEqual(observation.confidence, 0.91)

    async def test_ocr_without_availability_evidence_is_technical_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            phrase_file = Path(directory) / "phrases.json"
            phrase_file.write_text(
                json.dumps(
                    {
                        "phrase_sets": [
                            {
                                "country": "DE",
                                "platform": "amazon",
                                "page_type": "product_detail",
                                "phrases": ["In den Warenkorb"],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            factory = RealObservationFactory(FakeOcr(OcrResult(text="Nur ansehen")), phrase_file)

            observation = await factory(product(), None, b"roi")

        self.assertEqual(observation.status, ProductScanStatus.TECHNICAL_FAILURE)
        self.assertEqual(observation.error_code, "OCR_AVAILABILITY_UNVERIFIED")
        self.assertIsNone(observation.matched_phrase)

    async def test_ocr_timeout_returns_technical_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            phrase_file = Path(directory) / "phrases.json"
            phrase_file.write_text(
                json.dumps(
                    {
                        "phrase_sets": [
                            {
                                "country": "DE",
                                "platform": "amazon",
                                "page_type": "product_detail",
                                "phrases": ["Add to cart"],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            factory = RealObservationFactory(
                FakeOcr(error=OcrError("OCR_TIMEOUT", "timed out")), phrase_file
            )

            observation = await factory(product(), None, b"roi")

        self.assertEqual(observation.status, ProductScanStatus.TECHNICAL_FAILURE)
        self.assertEqual(observation.error_code, "OCR_TIMEOUT")

    async def test_cookie_summary_never_contains_raw_value(self):
        with tempfile.TemporaryDirectory() as directory:
            phrase_file = Path(directory) / "phrases.json"
            phrase_file.write_text(
                json.dumps(
                    {
                        "phrase_sets": [
                            {
                                "country": "DE",
                                "platform": "amazon",
                                "page_type": "product_detail",
                                "phrases": ["Add to cart"],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            factory = RealObservationFactory(FakeOcr(OcrResult(text="Add to cart")), phrase_file)
            page = type("Page", (), {})()
            page.context = type("Context", (), {})()
            page.context.cookies = lambda: asyncio.sleep(0, result=[{"name": "sid", "value": "secret"}])

            observation = await factory(product(), page, b"roi")

        self.assertEqual(observation.status, ProductScanStatus.TECHNICAL_FAILURE)
        self.assertEqual(observation.error_code, "DOM_BUTTON_UNVERIFIED")
        self.assertNotIn("secret", str(observation.cookie_summary))
        self.assertEqual(observation.cookie_summary[0]["present"], True)


if __name__ == "__main__":
    unittest.main()
