import unittest
from datetime import datetime, timedelta, timezone

from app.monitoring.adapters.artifact_store_local import LocalArtifactStore
from app.monitoring.application.artifact_retention import (
    ArtifactRecord,
    ArtifactRetentionService,
)


class ArtifactRetentionTests(unittest.IsolatedAsyncioTestCase):
    async def test_health_artifact_is_deleted_after_next_health_scan(self):
        service = ArtifactRetentionService(LocalArtifactStore("output/test-retention"))
        record = ArtifactRecord(
            artifact_id="health-1",
            kind="healthy",
            created_at=datetime.now(timezone.utc),
        )

        deleted = await service.cleanup([record], completed_health_artifact_ids={"health-1"})

        self.assertEqual(deleted, ["health-1"])

    async def test_unprocessed_exception_is_retained_for_three_days(self):
        service = ArtifactRetentionService(LocalArtifactStore("output/test-retention"))
        record = ArtifactRecord(
            artifact_id="error-1",
            kind="inventory_risk",
            created_at=datetime.now(timezone.utc) - timedelta(days=2, hours=23),
            handled=False,
        )

        deleted = await service.cleanup([record], now=datetime.now(timezone.utc))

        self.assertEqual(deleted, [])

    async def test_unprocessed_exception_is_deleted_after_three_days(self):
        service = ArtifactRetentionService(LocalArtifactStore("output/test-retention"))
        record = ArtifactRecord(
            artifact_id="error-1",
            kind="technical_failure",
            created_at=datetime.now(timezone.utc) - timedelta(days=3, seconds=1),
            handled=False,
        )

        deleted = await service.cleanup([record], now=datetime.now(timezone.utc))

        self.assertEqual(deleted, ["error-1"])

    async def test_handled_exception_requires_manual_delete(self):
        service = ArtifactRetentionService(LocalArtifactStore("output/test-retention"))
        record = ArtifactRecord(
            artifact_id="error-1",
            kind="inventory_risk",
            created_at=datetime.now(timezone.utc) - timedelta(days=30),
            handled=True,
            resolved=True,
        )

        retained = await service.cleanup([record], now=datetime.now(timezone.utc))
        deleted = await service.cleanup(
            [record], now=datetime.now(timezone.utc), manual_delete_ids={"error-1"}
        )

        self.assertEqual(retained, [])
        self.assertEqual(deleted, ["error-1"])


if __name__ == "__main__":
    unittest.main()
