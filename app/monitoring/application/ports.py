from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.monitoring.domain.models import Alert, Product, Scan, ScanObservation


ScanTarget = Product


@dataclass(frozen=True)
class ArtifactMetadata:
    country: str
    platform: str
    sku: str
    artifact_type: str
    captured_at: datetime
    extension: str = "png"


@dataclass(frozen=True)
class ArtifactRef:
    artifact_id: str
    path: str


@dataclass(frozen=True)
class ArtifactRecord:
    artifact_id: str
    product_id: str
    country: str
    platform: str
    sku: str
    artifact_type: str
    path: str
    created_at: datetime
    deleted_at: datetime | None = None


class ArtifactStore(Protocol):
    async def save(self, content: bytes, metadata: ArtifactMetadata) -> ArtifactRef:
        ...

    async def delete(self, artifact_id: str) -> None:
        ...


class ArtifactRepository(Protocol):
    async def add(self, product_id: str, metadata: ArtifactMetadata, ref: ArtifactRef) -> None:
        ...

    async def list_for_product(self, product_id: str) -> list[ArtifactRecord]:
        ...

    async def mark_deleted(self, artifact_id: str, deleted_at: datetime) -> None:
        ...


@dataclass(frozen=True)
class ImageRegion:
    content: bytes
    mime_type: str = "image/png"


@dataclass(frozen=True)
class OcrResult:
    text: str
    confidence: float | None = None
    language: str | None = None
    boxes: list[dict] | None = None


class OcrEngine(Protocol):
    async def recognize(self, image: ImageRegion) -> OcrResult:
        ...


class Scanner(Protocol):
    async def scan(self, target: ScanTarget) -> ScanObservation:
        ...


class DuplicateProductError(ValueError):
    pass


class ProductRepository(Protocol):
    async def create(self, product: Product) -> None:
        ...

    async def get(self, product_id: str) -> Product | None:
        ...

    async def list_enabled(self) -> list[Product]:
        ...

    async def save(self, product: Product) -> None:
        ...


class ScanRepository(Protocol):
    async def add(self, scan: Scan) -> None:
        ...

    async def latest_for(self, product_id: str) -> Scan | None:
        ...

    async def list_all(self) -> list[Scan]:
        ...


class AlertRepository(Protocol):
    async def find_active_inventory_alert(self, product_id: str) -> Alert | None:
        ...

    async def save(self, alert: Alert) -> None:
        ...

    async def get(self, alert_id: str) -> Alert | None:
        ...

    async def list_all(self) -> list[Alert]:
        ...

    async def record_transition(self, alert: Alert, *, from_status: str | None, reason: str, operator: str) -> None:
        ...
