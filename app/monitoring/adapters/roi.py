from __future__ import annotations

import io
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image


def has_image_content(content: bytes, *, below_header: bool = False) -> bool:
    """Reject unreadable or nearly uniform evidence, ignoring page chrome when requested."""
    try:
        with Image.open(io.BytesIO(content)) as source:
            if below_header:
                bottom = min(source.height, 1100)
                area = source.crop((0, int(bottom * .18), source.width, bottom))
            else:
                area = source
            pixels = area.convert("L")
            pixels.thumbnail((640, 1024))
            histogram = pixels.histogram()
    except (OSError, ValueError):
        return False
    minimum = max(1, int(sum(histogram) * .002))

    def percentile(levels):
        total = 0
        for level in levels:
            total += histogram[level]
            if total >= minimum:
                return level
        return 0
    return percentile(range(255, -1, -1)) - percentile(range(256)) >= 18


class RoiError(ValueError):
    """Raised when an ROI cannot be validated or cropped."""


@dataclass(frozen=True)
class RoiProfile:
    id: str
    region: dict[str, float] | None = None
    selector: str | None = None

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "RoiProfile":
        profile_id = str(data.get("id", "")).strip()
        if not profile_id:
            raise RoiError("ROI profile id is required")

        selector = data.get("selector")
        if selector is not None:
            selector = str(selector).strip() or None

        raw_region = data.get("region")
        region = None
        if raw_region is not None:
            if not isinstance(raw_region, dict):
                raise RoiError("ROI region must be an object")
            required = ("left", "top", "right", "bottom")
            if any(key not in raw_region for key in required):
                raise RoiError("ROI region requires left, top, right and bottom")
            try:
                region = {key: float(raw_region[key]) for key in required}
            except (TypeError, ValueError) as exc:
                raise RoiError("ROI coordinates must be numbers") from exc
            if any(value < 0 or value > 1 for value in region.values()):
                raise RoiError("ROI coordinates must be between 0 and 1")
            if region["left"] >= region["right"] or region["top"] >= region["bottom"]:
                raise RoiError("ROI region must have positive width and height")

        if not selector and region is None:
            raise RoiError("ROI profile requires a selector or region")
        return cls(id=profile_id, region=region, selector=selector)


class JsonRoiProfileLoader:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def load(self, profile_id: str) -> RoiProfile:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise RoiError(f"failed to load ROI profiles: {self.path}") from exc

        profiles = data.get("profiles") if isinstance(data, dict) else data
        if not isinstance(profiles, list):
            raise RoiError("ROI profile file must contain a profiles list")
        for item in profiles:
            if isinstance(item, dict) and item.get("id") == profile_id:
                return RoiProfile.from_mapping(item)
        raise RoiError(f"ROI profile not found: {profile_id}")


class RoiCropper:
    async def crop(
        self,
        screenshot: bytes,
        profile: RoiProfile,
        page: object | None = None,
    ) -> bytes:
        """按 ROI 配置从整页截图里裁出待识别的区域。

        ROI 配置有两种定位方式（见 RoiProfile）：
          selector —— 用 CSS 选择器在页面上定位元素的包围盒（更精确，
                      因为拿到的是元素实际渲染区域）；
          region  —— 用相对坐标（0~1 的比例）裁剪，用于页面结构不稳定、
                      选择器定位不到的站点。九个亚马逊站点目前都用 selector
                      #rightCol（购买区）。

        selector 方式需要 page 对象；如果取不到包围盒会退化为按整图比例
        估算的相对区域。
        """
        try:
            with Image.open(io.BytesIO(screenshot)) as source:
                image = source.convert("RGB")
                width, height = image.size
                box = await self._resolve_box(profile, page, width, height)
                cropped = image.crop(box)
                output = io.BytesIO()
                cropped.save(output, format="PNG")
                return output.getvalue()
        except RoiError:
            raise
        except Exception as exc:
            raise RoiError(f"failed to crop ROI: {exc}") from exc

    async def _resolve_box(
        self,
        profile: RoiProfile,
        page: object | None,
        width: int,
        height: int,
    ) -> tuple[int, int, int, int]:
        if profile.selector:
            if page is None or not hasattr(page, "locator"):
                raise RoiError("ROI selector requires a page")
            locator = page.locator(profile.selector)
            box = await locator.bounding_box()
            if box is None:
                raise RoiError(f"ROI selector not found: {profile.selector}")
            try:
                pixel_box = (
                    float(box["x"]),
                    float(box["y"]),
                    float(box["x"]) + float(box["width"]),
                    float(box["y"]) + float(box["height"]),
                )
            except (KeyError, TypeError, ValueError) as exc:
                raise RoiError("ROI selector returned an invalid bounding box") from exc
        elif profile.region:
            pixel_box = (
                profile.region["left"] * width,
                profile.region["top"] * height,
                profile.region["right"] * width,
                profile.region["bottom"] * height,
            )
        else:
            raise RoiError("ROI profile has no selector or region")

        return self.clip_box(pixel_box, width, height)

    @staticmethod
    def clip_box(
        box: tuple[float, float, float, float],
        width: int,
        height: int,
    ) -> tuple[int, int, int, int]:
        left, top, right, bottom = box
        clipped = (
            max(0, min(width, round(left))),
            max(0, min(height, round(top))),
            max(0, min(width, round(right))),
            max(0, min(height, round(bottom))),
        )
        if clipped[0] >= clipped[2] or clipped[1] >= clipped[3]:
            raise RoiError("ROI is empty after clipping")
        return clipped
