from __future__ import annotations

import asyncio
import io
from typing import Any

from PIL import Image
import pytesseract

from app.monitoring.application.ports import ImageRegion, OcrResult


class OcrError(RuntimeError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(f"{code}: {message}")


class TesseractOcrAdapter:
    # 按钮裁剪图通常只有 200x30 像素，Tesseract 在这种尺寸下常把带附加符号的
    # 字母读错，例如西班牙语 "Añadir" 被读成 "Afiadir"。放大后再识别可稳定
    # 还原字母本身，归一化阶段再剥离重音符号即可匹配词库。
    DEFAULT_SCALE = 3

    def __init__(
        self,
        lang: str = "eng+deu+ita",
        timeout_seconds: float = 30.0,
        tesseract_cmd: str | None = None,
        config: str = "",
        scale: int = DEFAULT_SCALE,
    ):
        self.lang = lang
        self.timeout_seconds = timeout_seconds
        self.config = config
        self.scale = scale
        if tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

    async def recognize(self, image: ImageRegion) -> OcrResult:
        if not isinstance(image, ImageRegion) or not image.content:
            raise OcrError("INVALID_IMAGE", "OCR requires a non-empty ImageRegion")
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(self._recognize_sync, image),
                timeout=self.timeout_seconds,
            )
        except asyncio.TimeoutError as exc:
            raise OcrError("OCR_TIMEOUT", "Tesseract recognition timed out") from exc
        except pytesseract.TesseractNotFoundError as exc:
            raise OcrError("TESSERACT_NOT_FOUND", str(exc)) from exc
        except OcrError:
            raise
        except Exception as exc:
            raise OcrError("OCR_FAILED", str(exc)) from exc

    def _recognize_sync(self, image: ImageRegion) -> OcrResult:
        with Image.open(io.BytesIO(image.content)) as source:
            prepared = self._scale(source)
            result: dict[str, Any] = pytesseract.image_to_data(
                prepared,
                lang=self.lang,
                config=self.config,
                output_type=pytesseract.Output.DICT,
            )
        texts = [str(value).strip() for value in result.get("text", []) if str(value).strip()]
        confidences = []
        for value in result.get("conf", []):
            try:
                confidence = float(value)
            except (TypeError, ValueError):
                continue
            if confidence >= 0:
                confidences.append(confidence)
        average_confidence = (
            sum(confidences) / len(confidences) / 100 if confidences else None
        )
        return OcrResult(
            text=" ".join(texts),
            confidence=average_confidence,
            language=self.lang,
            boxes=None,
        )

    def _scale(self, source: Image.Image) -> Image.Image:
        """按配置倍数放大图片，供 Tesseract 识别。

        放大只作用于送进 OCR 的副本，存档证据仍是原始尺寸。
        放大失败时退回原图，不让 OCR 因缩放问题整体失败。
        """
        if self.scale <= 1:
            return source
        try:
            return source.convert("RGB").resize(
                (source.width * self.scale, source.height * self.scale),
                Image.LANCZOS,
            )
        except Exception:
            return source

    @staticmethod
    def tesseract_not_found_error(message: str):
        return pytesseract.TesseractNotFoundError()
