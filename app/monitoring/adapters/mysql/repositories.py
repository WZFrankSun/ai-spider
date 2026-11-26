from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import desc, select
from sqlalchemy.exc import IntegrityError
from app.monitoring.application.ports import DuplicateProductError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.monitoring.domain.models import (
    Alert,
    AlertStatus,
    AlertType,
    Product,
    ProductScanStatus,
    Scan,
    ScanObservation,
)
from app.monitoring.adapters.mysql.models import (
    AlertModel, AlertTransitionModel, DeletedProductModel, ProductModel, ScanRunModel,
)


class SqlAlchemyProductRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self.session_factory = session_factory

    async def get(self, product_id: str) -> Product | None:
        async with self.session_factory() as session:
            record = await session.get(ProductModel, product_id)
            return _to_product(record) if record else None

    async def list_all(self) -> list[Product]:
        async with self.session_factory() as session:
            records = await session.scalars(select(ProductModel).order_by(ProductModel.id))
            return [_to_product(record) for record in records]

    async def delete_many(self, product_ids: list[str]) -> None:
        async with self.session_factory() as session, session.begin():
            result = await session.scalars(
                select(ProductModel).where(ProductModel.id.in_(product_ids))
                .order_by(ProductModel.id).with_for_update()
            )
            records = result.all()
            if {record.id for record in records} != set(product_ids):
                raise KeyError("Selected product no longer exists")
            for record in records:
                session.add(DeletedProductModel(product_id=record.id))
                await session.delete(record)

    async def seed(self, product: Product) -> None:
        async with self.session_factory() as session, session.begin():
            existing = await session.get(ProductModel, product.id, with_for_update=True)
            if existing is None and await session.get(DeletedProductModel, product.id) is None:
                session.add(_product_record(product, None, datetime.now(timezone.utc)))

    async def list_enabled(self) -> list[Product]:
        async with self.session_factory() as session:
            result = await session.execute(
                select(ProductModel).where(ProductModel.enabled.is_(True)).order_by(ProductModel.id)
            )
            return [_to_product(record) for record in result.scalars()]

    async def create(self, product: Product) -> None:
        try:
            async with self.session_factory() as session, session.begin():
                session.add(_product_record(product, None, datetime.now(timezone.utc)))
        except IntegrityError as exc:
            if "uq_products_store_market_sku" in str(exc.orig) or (
                "UNIQUE constraint failed" in str(exc.orig) and "products.store_code" in str(exc.orig)
            ):
                raise DuplicateProductError("该店铺与站点已存在此 SKU") from exc
            raise

    async def save(self, product: Product) -> None:
        now = datetime.now(timezone.utc)
        async with self.session_factory() as session:
            async with session.begin():
                existing = await session.get(ProductModel, product.id)
                record = _product_record(product, existing, now)
                await session.merge(record)


class SqlAlchemyScanRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self.session_factory = session_factory

    async def add(self, scan: Scan) -> None:
        async with self.session_factory() as session:
            async with session.begin():
                await session.merge(_scan_record(scan))

    async def latest_for(self, product_id: str) -> Scan | None:
        async with self.session_factory() as session:
            result = await session.execute(
                select(ScanRunModel)
                .where(ScanRunModel.product_id == product_id)
                .order_by(desc(ScanRunModel.started_at))
                .limit(1)
            )
            record = result.scalar_one_or_none()
            return _to_scan(record) if record else None

    async def list_all(self) -> list[Scan]:
        async with self.session_factory() as session:
            result = await session.execute(select(ScanRunModel).order_by(ScanRunModel.started_at.desc()))
            return [_to_scan(record) for record in result.scalars()]


class SqlAlchemyAlertRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self.session_factory = session_factory

    async def find_active_inventory_alert(self, product_id: str) -> Alert | None:
        async with self.session_factory() as session:
            result = await session.execute(
                select(AlertModel)
                .where(
                    AlertModel.product_id == product_id,
                    AlertModel.type == AlertType.PRODUCT_ADD_TO_CART_MISSING.value,
                    AlertModel.status.not_in([AlertStatus.RESOLVED.value, AlertStatus.DISMISSED.value]),
                )
                .order_by(AlertModel.updated_at.desc())
                .limit(1)
            )
            record = result.scalar_one_or_none()
            return _to_alert(record) if record else None

    async def save(self, alert: Alert) -> None:
        now = datetime.now(timezone.utc)
        async with self.session_factory() as session:
            async with session.begin():
                existing = await session.get(AlertModel, alert.id)
                await session.merge(_alert_record(alert, existing, now))

    async def get(self, alert_id: str) -> Alert | None:
        async with self.session_factory() as session:
            record = await session.get(AlertModel, alert_id)
            return _to_alert(record) if record else None

    async def list_all(self) -> list[Alert]:
        async with self.session_factory() as session:
            result = await session.execute(select(AlertModel).order_by(AlertModel.updated_at.desc()))
            return [_to_alert(record) for record in result.scalars()]

    async def record_transition(self, alert, *, from_status, reason, operator) -> None:
        async with self.session_factory() as session:
            async with session.begin():
                session.add(AlertTransitionModel(
                    alert_id=alert.id,
                    from_status=from_status,
                    to_status=alert.status.value,
                    reason=reason,
                    operator=operator,
                    created_at=datetime.now(timezone.utc),
                ))


def _product_record(product: Product, existing: ProductModel | None, now: datetime) -> ProductModel:
    return ProductModel(
        id=product.id,
        country=product.country,
        platform=product.platform,
        sku=product.sku,
        store_code=product.store_code,
        asin=product.asin,
        added_by=product.added_by,
        url=product.url,
        page_type=product.page_type,
        roi_profile_id=product.roi_profile_id,
        name=product.name,
        enabled=product.enabled,
        status=product.status.value,
        created_at=existing.created_at if existing else now,
        updated_at=now,
    )


def _scan_record(scan: Scan) -> ScanRunModel:
    observation = scan.observation
    return ScanRunModel(
        id=scan.id,
        product_id=scan.product_id,
        status=scan.status.value,
        started_at=scan.started_at,
        finished_at=scan.finished_at,
        ocr_text=observation.ocr_text,
        matched_phrase=observation.matched_phrase,
        ocr_confidence=observation.confidence,
        error_code=observation.error_code,
        error_message=observation.error_message,
        full_screenshot_path=observation.full_screenshot_path,
        roi_screenshot_path=observation.roi_screenshot_path,
        cookie_summary=observation.cookie_summary,
    )


def _alert_record(alert: Alert, existing: AlertModel | None, now: datetime) -> AlertModel:
    return AlertModel(
        id=alert.id,
        type=alert.type.value,
        status=alert.status.value,
        product_id=alert.product_id,
        failure_count=alert.failure_count,
        operator_note=alert.operator_note,
        metadata_json=alert.metadata,
        created_at=existing.created_at if existing else now,
        updated_at=now,
    )


def _to_product(record: ProductModel) -> Product:
    return Product(
        id=record.id,
        country=record.country,
        platform=record.platform,
        sku=record.sku,
        store_code=record.store_code,
        asin=record.asin,
        added_by=record.added_by,
        url=record.url,
        page_type=record.page_type,
        roi_profile_id=record.roi_profile_id,
        name=record.name,
        enabled=record.enabled,
        status=ProductScanStatus(record.status),
    )


def _to_scan(record: ScanRunModel) -> Scan:
    observation = ScanObservation(
        status=ProductScanStatus(record.status),
        ocr_text=record.ocr_text,
        matched_phrase=record.matched_phrase,
        confidence=record.ocr_confidence,
        error_code=record.error_code,
        error_message=record.error_message,
        started_at=record.started_at,
        finished_at=record.finished_at,
        full_screenshot_path=record.full_screenshot_path,
        roi_screenshot_path=record.roi_screenshot_path,
        cookie_summary=list(record.cookie_summary or []),
    )
    return Scan(
        id=record.id,
        product_id=record.product_id,
        status=ProductScanStatus(record.status),
        observation=observation,
        started_at=record.started_at,
        finished_at=record.finished_at,
    )


def _to_alert(record: AlertModel) -> Alert:
    return Alert(
        id=record.id,
        type=AlertType(record.type),
        status=AlertStatus(record.status),
        product_id=record.product_id,
        failure_count=record.failure_count,
        operator_note=record.operator_note,
        metadata=dict(record.metadata_json or {}),
    )
