import unittest
from contextlib import asynccontextmanager
from urllib.parse import urlsplit

from fastapi.testclient import TestClient
from playwright.sync_api import expect, sync_playwright

from app.monitoring.adapters.mysql.engine import create_session_factory, create_sqlalchemy_engine
from app.monitoring.adapters.mysql.models import Base
from app.monitoring.adapters.mysql.repositories import SqlAlchemyProductRepository
from app.monitoring.api.routes import MonitoringContainer, create_monitoring_app
from app.monitoring.domain.models import ProductScanStatus


class ProductManagementTests(unittest.TestCase):
    def test_list_and_delete_only_selected_products(self):
        container = MonitoringContainer.demo()
        container.mode = "real"
        with TestClient(create_monitoring_app(container)) as client:
            payload = {
                "platform": "amazon", "country": "DE", "store_code": "H1-A1",
                "name": "Test", "added_by": "Frank",
                "url": "https://www.amazon.de/dp/B07Q3DYMRD",
            }
            first, second = [
                client.post("/api/products", json={**payload, "sku": sku}).json()["id"]
                for sku in ("MANAGE-1", "MANAGE-2")
            ]
            url = "/api/products/batch-delete"
            self.assertEqual(client.post(url, json={"product_ids": []}).status_code, 422)
            self.assertEqual(client.post(url, json={"product_ids": [first, first]}).status_code, 422)
            container.scan_product.coordinator.acquire(first)
            try:
                self.assertEqual(client.post(url, json={"product_ids": [second, first]}).status_code, 409)
                self.assertFalse(container.scan_product.coordinator.is_active(second))
            finally:
                container.scan_product.coordinator.release(first)
            self.assertEqual(client.post(url, json={"product_ids": [first, "missing"]}).status_code, 409)
            before = {item["id"] for item in client.get("/api/products/manage").json()}
            self.assertIn(first, before)
            self.assertEqual(client.post(url, json={"product_ids": [first]}).json(), {"deleted_count": 1})
            self.assertEqual({item["id"] for item in client.get("/api/products/manage").json()}, before - {first})
            self.assertIn(second, {item["id"] for item in client.get("/api/products").json()})

    def test_browser_filters_confirms_and_deletes_from_database(self):
        engine = create_sqlalchemy_engine("sqlite+aiosqlite:///:memory:")
        products = SqlAlchemyProductRepository(create_session_factory(engine))
        container = MonitoringContainer.from_dependencies(products, scanner=None)

        @asynccontextmanager
        async def lifespan(app):
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            try:
                yield
            finally:
                await engine.dispose()

        with TestClient(create_monitoring_app(container, lifespan=lifespan)) as client:
            common = {"name": "Management test", "store_code": "H1-A1", "added_by": "Frank"}
            entries = (
                dict(platform="amazon", country="DE", sku="MATCH-ONE", url="https://www.amazon.de/dp/B07Q3DYMRD"),
                dict(platform="amazon", country="DE", sku="MATCH-TWO", url="https://www.amazon.de/dp/B07Q3DYMRD"),
                dict(platform="amazon", country="IT", sku="MATCH-THREE", url="https://www.amazon.it/dp/B07Q3DYMRD"),
                dict(platform="temu", country="DE", sku="MATCH-TEMU", url="https://www.temu.com/goods.html"),
                dict(platform="amazon", country="DE", sku="OTHER", url="https://www.amazon.de/dp/B07Q3DYMRD"),
                dict(platform="amazon", country="DE", sku="MATCH-STORE", store_code="H4-A1",
                     url="https://www.amazon.de/dp/B07Q3DYMRD"),
                dict(platform="amazon", country="DE", sku="MATCH-STATUS", url="https://www.amazon.de/dp/B07Q3DYMRD"),
            )
            ids = {}
            for entry in entries:
                response = client.post("/api/products", json={**common, **entry})
                self.assertEqual(response.status_code, 201)
                ids[entry["sku"]] = response.json()["id"]
            status_product = client.portal.call(products.get, ids["MATCH-STATUS"])
            status_product.status = ProductScanStatus.HEALTHY
            client.portal.call(products.save, status_product)

            delete_path = "/api/products/batch-delete"
            delete_calls = []
            page_errors = []

            def route_request(route):
                request = route.request
                path = urlsplit(request.url).path
                if path == delete_path:
                    delete_calls.append(request.post_data_json)
                    if len(delete_calls) == 1:
                        route.fulfill(status=409, json={"detail": "测试删除冲突"})
                        return
                response = client.request(request.method, path, json=request.post_data_json)
                route.fulfill(status=response.status_code, content_type=response.headers["content-type"],
                              body=response.content)

            with sync_playwright() as playwright:
                browser = playwright.chromium.launch()
                try:
                    page = browser.new_page()
                    page.on("pageerror", lambda error: page_errors.append(str(error)))
                    page.route("http://management.test/**", route_request)
                    page.goto("http://management.test/")
                    page.get_by_role("button", name="商品管理", exact=True).click()
                    rows = page.locator("#managed-products tr[data-managed-id]")
                    expect(rows).to_have_count(7)
                    page.get_by_role("searchbox", name="SKU", exact=True).fill("match")
                    page.locator("#manage-platform").select_option("amazon")
                    page.locator("#manage-country").select_option("DE")
                    page.locator("#manage-status").select_option("not_scanned")
                    page.locator("#manage-store").select_option("H1-A1")
                    expect(rows).to_have_count(2)
                    delete = page.get_by_role("button", name="删除", exact=True)
                    expect(delete).to_be_disabled()
                    page.get_by_role("button", name="批量选择", exact=True).click()
                    expect(delete).to_have_class("delete-products selecting")
                    expect(delete).to_be_disabled()
                    checkboxes = page.get_by_role("region", name="商品管理列表").get_by_role("checkbox")
                    expect(checkboxes).to_have_count(2)
                    for checkbox in checkboxes.all():
                        checkbox.check()
                    prompts = []

                    def cancel(dialog):
                        prompts.append(dialog.message)
                        dialog.dismiss()

                    page.once("dialog", cancel)
                    delete.click()
                    self.assertEqual(prompts, ["确定删除选中的 2 件商品吗？"])
                    self.assertEqual(delete_calls, [])
                    self.assertEqual(len(client.get("/api/products/manage").json()), 7)

                    page.once("dialog", lambda dialog: dialog.accept())
                    delete.click()
                    expect(page.get_by_role("alert")).to_have_text("删除失败：测试删除冲突×")
                    expect(rows).to_have_count(2)
                    self.assertEqual(len(client.get("/api/products/manage").json()), 7)

                    page.once("dialog", lambda dialog: dialog.accept())
                    delete.click()
                    expect(page.get_by_text("已删除 2 件商品")).to_be_visible()
                    expect(rows).to_have_count(0)
                    self.assertEqual(
                        {item["sku"] for item in client.get("/api/products/manage").json()},
                        set(ids) - {"MATCH-ONE", "MATCH-TWO"},
                    )
                    self.assertEqual(page_errors, [])
                finally:
                    browser.close()
