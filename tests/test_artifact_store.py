import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from app.monitoring.adapters.artifact_store_local import LocalArtifactStore
from app.monitoring.application.ports import ArtifactMetadata


class ArtifactStoreTests(unittest.IsolatedAsyncioTestCase):
    async def test_save_path_contains_market_identity_and_timestamp(self):
        with tempfile.TemporaryDirectory() as directory:
            store = LocalArtifactStore(directory)
            metadata = ArtifactMetadata(
                country="DE",
                platform="amazon",
                sku="SKU-001",
                artifact_type="full",
                captured_at=datetime(2026, 11, 20, 10, 30, tzinfo=timezone.utc),
            )

            reference = await store.save(b"fake-png", metadata)

            path = Path(reference.path)
            self.assertTrue(path.exists())
            self.assertEqual(path.read_bytes(), b"fake-png")
            normalized = path.as_posix()
            self.assertIn("DE/amazon/SKU-001/20261120", normalized)
            self.assertIn("103000", normalized)
            self.assertNotIn("cookie", normalized.lower())

            await store.delete(reference.artifact_id)
            self.assertFalse(path.exists())

    async def test_delete_ignores_missing_artifact(self):
        with tempfile.TemporaryDirectory() as directory:
            store = LocalArtifactStore(directory)

            await store.delete("missing.png")


if __name__ == "__main__":
    unittest.main()
