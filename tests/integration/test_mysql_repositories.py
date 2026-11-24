import unittest
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.monitoring.adapters.mysql.engine import create_session_factory, create_sqlalchemy_engine
from app.monitoring.adapters.mysql.models import Base
from app.monitoring.adapters.mysql.repositories import (
    SqlAlchemyAlertRepository,
    SqlAlchemyProductRepository,
    SqlAlchemyScanRepository,
)
from app.monitoring.domain.models import (
    Alert,
    AlertStatus,
    AlertType,
    Product,
    ProductScanStatus,
    Scan,
    ScanObservation,
)


def product(product_id="DE-001"):
    return Product(
        id=product_id,
        country="DE",
        platform="amazon",
        sku=f"{product_id}-SKU",
        url="https://example.test/product",
        page_type="product_detail",
        roi_profile_id="default",
    )


def scan_for(current_product):
    now = datetime.now(timezone.utc)
    observation = ScanObservation(
        status=ProductScanStatus.INVENTORY_RISK,
        error_code=None,
        started_at=now,
        finished_at=now,
        cookie_summary=[{"name": "sid", "present": True, "value_hash": "abc"}],
    )
    return Scan(
        id=f"scan-{current_product.id}",
        product_id=current_product.id,
        status=observation.status,
        observation=observation,
        started_at=now,
        finished_at=now,
    )


class SqlAlchemyRepositoryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_sqlalchemy_engine("sqlite+aiosqlite:///:memory:")
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        self.session_factory = create_session_factory(self.engine)
        self.products = SqlAlchemyProductRepository(self.session_factory)
        self.scans = SqlAlchemyScanRepository(self.session_factory)
        self.alerts = SqlAlchemyAlertRepository(self.session_factory)

    async def asyncTearDown(self):
        await self.engine.dispose()

    async def test_product_entry_round_trip_and_store_uniqueness(self):
        from dataclasses import replace

        from app.monitoring.application.ports import DuplicateProductError

        first = replace(product(), store_code="H1-A1", asin="B07Q3DYMRD", added_by="Frank", postal_code="00174")
        await self.products.create(first)
        await self.products.create(replace(first, id="different-store", store_code="H4-A1", postal_code="SW1A 1AA"))
        with self.assertRaises(DuplicateProductError):
            await self.products.create(replace(first, id="duplicate"))
        self.assertEqual(await self.products.get(first.id), first)
        different = await self.products.get("different-store")
        self.assertEqual(different.postal_code, "SW1A 1AA")

    async def test_product_save_get_and_enabled_listing(self):
        current_product = product()
        disabled = product("DE-002")
        disabled.enabled = False
        await self.products.save(current_product)
        await self.products.save(disabled)

        loaded = await self.products.get(current_product.id)
        enabled = await self.products.list_enabled()

        self.assertEqual(loaded.sku, current_product.sku)
        self.assertEqual([item.id for item in enabled], [current_product.id])

    async def test_scan_write_and_latest_query(self):
        current_product = product()
        await self.products.save(current_product)
        first = scan_for(current_product)
        await self.scans.add(first)

        latest = await self.scans.latest_for(current_product.id)

        self.assertEqual(latest.id, first.id)
        self.assertEqual(latest.observation.status, ProductScanStatus.INVENTORY_RISK)
        self.assertEqual(latest.observation.cookie_summary[0]["name"], "sid")

    async def test_active_inventory_alert_is_found_and_failure_count_updates(self):
        current_product = product()
        await self.products.save(current_product)
        alert = Alert(
            id="alert-DE-001",
            type=AlertType.PRODUCT_ADD_TO_CART_MISSING,
            status=AlertStatus.OPEN,
            product_id=current_product.id,
        )
        await self.alerts.save(alert)

        active = await self.alerts.find_active_inventory_alert(current_product.id)
        active.failure_count += 1
        await self.alerts.save(active)
        loaded = await self.alerts.get(alert.id)

        self.assertEqual(active.id, alert.id)
        self.assertEqual(loaded.failure_count, 2)

    async def test_resolved_alert_is_not_an_active_inventory_alert(self):
        alert = Alert(
            id="alert-DE-001",
            type=AlertType.PRODUCT_ADD_TO_CART_MISSING,
            status=AlertStatus.RESOLVED,
            product_id="DE-001",
        )
        await self.alerts.save(alert)

        self.assertIsNone(await self.alerts.find_active_inventory_alert("DE-001"))


if __name__ == "__main__":
    unittest.main()
