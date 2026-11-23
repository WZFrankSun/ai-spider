import io
import unittest

from PIL import Image

from app.monitoring.adapters.roi import RoiCropper, RoiError, RoiProfile


def png_bytes(size=(100, 80), color="white"):
    image = Image.new("RGB", size, color)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


class FakeLocator:
    def __init__(self, box):
        self.box = box

    async def bounding_box(self):
        return self.box


class FakePage:
    def __init__(self, box):
        self.box = box

    def locator(self, selector):
        self.selector = selector
        return FakeLocator(self.box)


class RoiTests(unittest.IsolatedAsyncioTestCase):
    async def test_relative_region_scales_with_image_size(self):
        profile = RoiProfile.from_mapping(
            {"id": "default", "region": {"left": 0.25, "top": 0.25, "right": 0.75, "bottom": 0.75}}
        )

        result = await RoiCropper().crop(png_bytes(), profile)

        with Image.open(io.BytesIO(result)) as image:
            self.assertEqual(image.size, (50, 40))

    async def test_pixel_box_is_clipped_to_image_bounds(self):
        box = RoiCropper.clip_box((-10, -5, 70, 60), width=100, height=80)

        self.assertEqual(box, (0, 0, 70, 60))

    async def test_invalid_relative_region_is_rejected(self):
        with self.assertRaises(RoiError):
            RoiProfile.from_mapping(
                {"id": "broken", "region": {"left": 0.8, "top": 0, "right": 0.2, "bottom": 1}}
            )

    async def test_selector_has_priority_over_relative_region(self):
        profile = RoiProfile.from_mapping(
            {
                "id": "selector-first",
                "selector": "#buy-box",
                "region": {"left": 0, "top": 0, "right": 0.1, "bottom": 0.1},
            }
        )

        result = await RoiCropper().crop(
            png_bytes(), profile, page=FakePage({"x": 20, "y": 10, "width": 40, "height": 30})
        )

        with Image.open(io.BytesIO(result)) as image:
            self.assertEqual(image.size, (40, 30))

    async def test_profile_requires_region_or_selector(self):
        with self.assertRaises(RoiError):
            RoiProfile.from_mapping({"id": "empty"})


if __name__ == "__main__":
    unittest.main()
