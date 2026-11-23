import unittest
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.monitoring.adapters.mysql.health import check_database
from app.monitoring.adapters.mysql.models import ArtifactModel, Base
from app.monitoring.adapters.mysql.artifact_repository import SqlAlchemyArtifactRepository
from app.monitoring.application.ports import ArtifactMetadata, ArtifactRef


class ArtifactRepositoryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)

    async def asyncTearDown(self):
        await self.engine.dispose()

    async def test_database_health_returns_ok_for_sqlite_contract_engine(self):
        health = await check_database(self.engine)

        self.assertTrue(health.ok)
        self.assertIsNone(health.error)

    async def test_artifact_index_can_be_saved_and_marked_deleted(self):
        repository = SqlAlchemyArtifactRepository(self.sessions)
        metadata = ArtifactMetadata(
            country="DE",
            platform="amazon",
            sku="SKU-001",
            artifact_type="roi",
            captured_at=datetime.now(timezone.utc),
        )
        ref = ArtifactRef("artifact-1", "/tmp/roi.png")

        await repository.add("DE-001", metadata, ref)
        records = await repository.list_for_product("DE-001")
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].path, "/tmp/roi.png")

        await repository.mark_deleted("artifact-1", datetime.now(timezone.utc))
        records = await repository.list_for_product("DE-001")
        self.assertIsNotNone(records[0].deleted_at)

    async def test_real_database_url_is_never_echoed_in_health_error(self):
        health = await check_database(None)

        self.assertFalse(health.ok)
        self.assertNotIn("password", health.error or "")


if __name__ == "__main__":
    unittest.main()
