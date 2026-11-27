import asyncio
import io
import unittest
from unittest.mock import patch

from PIL import Image

from app.monitoring.adapters.ocr_tesseract import OcrError, TesseractOcrAdapter
from app.monitoring.application.ports import ImageRegion


def image_region() -> ImageRegion:
    image = Image.new("RGB", (20, 20), "white")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return ImageRegion(content=buffer.getvalue())


class OcrAdapterTests(unittest.IsolatedAsyncioTestCase):
    async def test_recognizes_only_the_supplied_roi(self):
        adapter = TesseractOcrAdapter(lang="eng+deu+ita")
        fake_data = {"text": ["Add to cart"], "conf": ["96"]}

        with patch("pytesseract.image_to_data", return_value=fake_data) as image_to_data:
            result = await adapter.recognize(image_region())

        self.assertEqual(result.text, "Add to cart")
        self.assertEqual(result.confidence, 0.96)
        self.assertEqual(result.language, "eng+deu+ita")
        image_to_data.assert_called_once()

    async def test_scales_image_before_recognition(self):
        adapter = TesseractOcrAdapter(lang="eng+deu+ita", scale=3)
        fake_data = {"text": ["Add to cart"], "conf": ["96"]}

        with patch("pytesseract.image_to_data", return_value=fake_data) as image_to_data:
            await adapter.recognize(image_region())

        prepared = image_to_data.call_args.args[0]
        self.assertEqual(prepared.size, (60, 60))

    async def test_scale_one_keeps_original_size(self):
        adapter = TesseractOcrAdapter(lang="eng+deu+ita", scale=1)
        fake_data = {"text": ["Add to cart"], "conf": ["96"]}

        with patch("pytesseract.image_to_data", return_value=fake_data) as image_to_data:
            await adapter.recognize(image_region())

        prepared = image_to_data.call_args.args[0]
        self.assertEqual(prepared.size, (20, 20))

    async def test_scaling_failure_falls_back_to_original_image(self):
        adapter = TesseractOcrAdapter(lang="eng+deu+ita", scale=3)
        fake_data = {"text": ["Add to cart"], "conf": ["96"]}

        with patch.object(Image.Image, "resize", side_effect=OSError("resize failed")):
            with patch("pytesseract.image_to_data", return_value=fake_data) as image_to_data:
                result = await adapter.recognize(image_region())

        self.assertEqual(result.text, "Add to cart")
        prepared = image_to_data.call_args.args[0]
        self.assertEqual(prepared.size, (20, 20))

    async def test_maps_missing_tesseract_binary_to_ocr_error(self):
        adapter = TesseractOcrAdapter()

        with patch(
            "pytesseract.image_to_data",
            side_effect=adapter.tesseract_not_found_error("missing"),
        ):
            with self.assertRaisesRegex(OcrError, "TESSERACT_NOT_FOUND"):
                await adapter.recognize(image_region())

    async def test_ocr_timeout_is_reported(self):
        adapter = TesseractOcrAdapter(timeout_seconds=0.01)

        async def slow_call(*args, **kwargs):
            await asyncio.sleep(0.1)

        with patch.object(adapter, "_recognize_sync", side_effect=lambda image: asyncio.run(slow_call())):
            with self.assertRaisesRegex(OcrError, "OCR_TIMEOUT"):
                await adapter.recognize(image_region())


if __name__ == "__main__":
    unittest.main()
