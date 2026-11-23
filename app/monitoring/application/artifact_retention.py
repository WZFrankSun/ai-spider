from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable

from app.monitoring.application.ports import ArtifactStore


@dataclass(frozen=True)
class ArtifactRecord:
    artifact_id: str
    kind: str
    created_at: datetime
    handled: bool = False
    resolved: bool = False


class ArtifactRetentionService:
    def __init__(self, store: ArtifactStore, unprocessed_days: int = 3):
        if unprocessed_days < 1:
            raise ValueError("unprocessed_days must be at least 1")
        self.store = store
        self.unprocessed_days = unprocessed_days

    async def cleanup(
        self,
        records: Iterable[ArtifactRecord],
        *,
        now: datetime | None = None,
        completed_health_artifact_ids: set[str] | None = None,
        manual_delete_ids: set[str] | None = None,
    ) -> list[str]:
        current_time = now or datetime.now(timezone.utc)
        health_ids = completed_health_artifact_ids or set()
        manual_ids = manual_delete_ids or set()
        deleted: list[str] = []
        for record in records:
            if self._should_delete(
                record,
                current_time,
                health_ids,
                manual_ids,
            ):
                await self.store.delete(record.artifact_id)
                deleted.append(record.artifact_id)
        return deleted

    def _should_delete(
        self,
        record: ArtifactRecord,
        now: datetime,
        completed_health_ids: set[str],
        manual_ids: set[str],
    ) -> bool:
        if record.kind == "healthy":
            return record.artifact_id in completed_health_ids
        if record.handled:
            return record.resolved and record.artifact_id in manual_ids
        created_at = record.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        return now - created_at.astimezone(timezone.utc) >= timedelta(days=self.unprocessed_days)
