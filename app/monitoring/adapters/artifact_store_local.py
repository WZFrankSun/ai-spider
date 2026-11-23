from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from app.monitoring.application.ports import ArtifactMetadata, ArtifactRef


class LocalArtifactStore:
    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    async def save(self, content: bytes, metadata: ArtifactMetadata) -> ArtifactRef:
        captured_at = metadata.captured_at
        if captured_at.tzinfo is None:
            captured_at = captured_at.replace(tzinfo=timezone.utc)
        captured_at = captured_at.astimezone(timezone.utc)

        country = _safe_segment(metadata.country.upper())
        platform = _safe_segment(metadata.platform.lower())
        sku = _safe_segment(metadata.sku)
        artifact_type = _safe_segment(metadata.artifact_type.lower())
        extension = _safe_extension(metadata.extension)
        relative_directory = Path(country) / platform / sku / captured_at.strftime("%Y%m%d")
        directory = self.root / relative_directory
        directory.mkdir(parents=True, exist_ok=True)
        filename = f"{captured_at.strftime('%Y%m%dT%H%M%S%fZ')}_{artifact_type}.{extension}"
        path = (directory / filename).resolve()
        self._ensure_inside_root(path)
        path.write_bytes(content)
        return ArtifactRef(artifact_id=path.relative_to(self.root).as_posix(), path=str(path))

    async def delete(self, artifact_id: str) -> None:
        relative = Path(artifact_id)
        path = (self.root / relative).resolve()
        self._ensure_inside_root(path)
        if path.exists() and path.is_file():
            path.unlink()

    def _ensure_inside_root(self, path: Path) -> None:
        try:
            path.relative_to(self.root)
        except ValueError as exc:
            raise ValueError("artifact path escapes configured root") from exc


def _safe_segment(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())
    if not value or value in {".", ".."}:
        raise ValueError("artifact path segment is empty")
    return value


def _safe_extension(value: str) -> str:
    extension = value.lower().lstrip(".")
    if not re.fullmatch(r"[a-z0-9]{1,8}", extension):
        raise ValueError("invalid artifact extension")
    return extension
