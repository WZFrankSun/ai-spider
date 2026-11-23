from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.monitoring.adapters.mysql.models import ArtifactModel
from app.monitoring.application.ports import ArtifactMetadata, ArtifactRecord, ArtifactRef


class SqlAlchemyArtifactRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self.session_factory = session_factory

    async def add(self, product_id: str, metadata: ArtifactMetadata, ref: ArtifactRef) -> None:
        async with self.session_factory() as session:
            async with session.begin():
                await session.merge(
                    ArtifactModel(
                        id=ref.artifact_id,
                        product_id=product_id,
                        country=metadata.country,
                        platform=metadata.platform,
                        sku=metadata.sku,
                        artifact_type=metadata.artifact_type,
                        path=ref.path,
                        created_at=metadata.captured_at,
                    )
                )

    async def list_for_product(self, product_id: str) -> list[ArtifactRecord]:
        async with self.session_factory() as session:
            result = await session.execute(
                select(ArtifactModel)
                .where(ArtifactModel.product_id == product_id)
                .order_by(ArtifactModel.created_at)
            )
            return [_to_record(item) for item in result.scalars()]

    async def mark_deleted(self, artifact_id: str, deleted_at: datetime) -> None:
        async with self.session_factory() as session:
            async with session.begin():
                item = await session.get(ArtifactModel, artifact_id)
                if item is not None:
                    item.deleted_at = deleted_at


def _to_record(item: ArtifactModel) -> ArtifactRecord:
    return ArtifactRecord(
        artifact_id=item.id,
        product_id=item.product_id,
        country=item.country,
        platform=item.platform,
        sku=item.sku,
        artifact_type=item.artifact_type,
        path=item.path,
        created_at=item.created_at,
        deleted_at=item.deleted_at,
    )
