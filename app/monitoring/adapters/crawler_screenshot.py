from __future__ import annotations

import inspect
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Awaitable, Callable, Protocol

from app.monitoring.adapters.roi import RoiCropper
from app.monitoring.application.ports import ArtifactMetadata, ArtifactStore
from app.monitoring.domain.models import Product, ProductScanStatus, ScanObservation


class ScreenshotManifestError(ValueError):
    pass


@dataclass(frozen=True)
class CrawlerScreenshotRecord:
    product_id: str
    path: str
    captured_at: datetime
    url: str | None = None
    country: str | None = None
    platform: str | None = None
    sku: str | None = None


class ScreenshotSource(Protocol):
    def load(self, product_id: str) -> tuple[bytes, CrawlerScreenshotRecord]:
        ...


class JsonScreenshotManifestSource:
    def __init__(self, manifest_path: str | Path, screenshot_root: str | Path):
        self.manifest_path = Path(manifest_path)
        self.root = Path(screenshot_root).resolve()
        self._records = self._load_records()

    def load(self, product_id: str) -> tuple[bytes, CrawlerScreenshotRecord]:
        record = self._records.get(product_id)
        if record is None:
            raise ScreenshotManifestError(f"screenshot record not found: {product_id}")
        path = Path(record.path).resolve()
        self._ensure_inside_root(path)
        try:
            return path.read_bytes(), record
        except FileNotFoundError as exc:
            raise FileNotFoundError(f"screenshot file not found: {path}") from exc
        except OSError as exc:
            raise ScreenshotManifestError(f"screenshot file cannot be read: {path}") from exc

    def _load_records(self) -> dict[str, CrawlerScreenshotRecord]:
        try:
            payload = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ScreenshotManifestError(f"invalid screenshot manifest: {self.manifest_path}") from exc
        records = payload.get("screenshots") if isinstance(payload, dict) else payload
        if not isinstance(records, list):
            raise ScreenshotManifestError("screenshot manifest must contain a screenshots list")

        result: dict[str, CrawlerScreenshotRecord] = {}
        for index, item in enumerate(records):
            if not isinstance(item, dict):
                raise ScreenshotManifestError(f"invalid screenshot record at index {index}")
            product_id = str(item.get("product_id") or item.get("id") or "").strip()
            raw_path = str(item.get("path") or item.get("screenshot_path") or "").strip()
            if not product_id or not raw_path:
                raise ScreenshotManifestError(f"screenshot record requires product_id and path at index {index}")
            path = Path(raw_path)
            if not path.is_absolute():
                path = self.root / path
            path = path.resolve()
            self._ensure_inside_root(path)
            if product_id in result:
                raise ScreenshotManifestError(f"duplicate screenshot product_id: {product_id}")
            result[product_id] = CrawlerScreenshotRecord(
                product_id=product_id,
                path=str(path),
                captured_at=_parse_datetime(item.get("captured_at")),
                url=_optional_text(item.get("url")),
                country=_optional_text(item.get("country")),
                platform=_optional_text(item.get("platform")),
                sku=_optional_text(item.get("sku")),
            )
        return result

    def _ensure_inside_root(self, path: Path) -> None:
        try:
            path.relative_to(self.root)
        except ValueError as exc:
            raise ScreenshotManifestError("screenshot path escapes configured root") from exc


ObservationFactory = Callable[
    [Product, object | None, bytes], ScanObservation | Awaitable[ScanObservation]
]


class CrawlerScreenshotScanner:
    def __init__(
        self,
        source: ScreenshotSource,
        roi_profile_loader,
        observation_factory: ObservationFactory,
        *,
        artifact_store: ArtifactStore | None = None,
        roi_cropper: RoiCropper | None = None,
    ):
        self.source = source
        self.roi_profile_loader = roi_profile_loader
        self.observation_factory = observation_factory
        self.artifact_store = artifact_store
        self.roi_cropper = roi_cropper or RoiCropper()

    async def scan(self, product: Product) -> ScanObservation:
        started_at = datetime.now(timezone.utc)
        full_path: str | None = None
        roi_path: str | None = None
        try:
            screenshot, record = self.source.load(product.id)
            full_path = record.path
        except FileNotFoundError as exc:
            return _failure("SCREENSHOT_NOT_FOUND", str(exc), started_at)
        except Exception as exc:
            return _failure("SCREENSHOT_SOURCE_FAILED", str(exc), started_at)

        try:
            profile = self.roi_profile_loader.load(product.roi_profile_id)
            roi = await self.roi_cropper.crop(screenshot, profile)
        except Exception as exc:
            return _failure("ROI_FAILED", str(exc), started_at, full_path)

        if self.artifact_store is not None:
            try:
                full_ref = await self.artifact_store.save(
                    screenshot,
                    ArtifactMetadata(
                        country=product.country,
                        platform=product.platform,
                        sku=product.sku,
                        artifact_type="full",
                        captured_at=started_at,
                    ),
                )
                roi_ref = await self.artifact_store.save(
                    roi,
                    ArtifactMetadata(
                        country=product.country,
                        platform=product.platform,
                        sku=product.sku,
                        artifact_type="roi",
                        captured_at=started_at,
                    ),
                )
                full_path, roi_path = full_ref.path, roi_ref.path
            except Exception as exc:
                return _failure("ARTIFACT_SAVE_FAILED", str(exc), started_at, full_path)

        try:
            observation = self.observation_factory(product, None, roi)
            if inspect.isawaitable(observation):
                observation = await observation
            if not isinstance(observation, ScanObservation):
                raise TypeError("observation_factory must return ScanObservation")
        except Exception as exc:
            return _failure("OBSERVATION_BUILD_FAILED", str(exc), started_at, full_path, roi_path)

        observation.started_at = started_at
        observation.finished_at = datetime.now(timezone.utc)
        observation.full_screenshot_path = full_path
        observation.roi_screenshot_path = roi_path
        return observation


def _parse_datetime(value: object) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise ScreenshotManifestError(f"invalid captured_at: {value}") from exc
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _optional_text(value: object) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None


def _failure(
    code: str,
    message: str,
    started_at: datetime,
    full_path: str | None = None,
    roi_path: str | None = None,
) -> ScanObservation:
    return ScanObservation(
        status=ProductScanStatus.TECHNICAL_FAILURE,
        error_code=code,
        error_message=message,
        started_at=started_at,
        finished_at=datetime.now(timezone.utc),
        full_screenshot_path=full_path,
        roi_screenshot_path=roi_path,
    )
