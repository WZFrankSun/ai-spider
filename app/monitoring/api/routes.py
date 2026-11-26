from __future__ import annotations

from dataclasses import dataclass
import re
import json
from pathlib import Path
from uuid import uuid4
from typing import Any, Callable

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse

from app.monitoring.adapters.demo_scanner import DemoScanner
from app.monitoring.adapters.memory_repositories import (
    MemoryAlertRepository,
    MemoryProductRepository,
    MemoryScanRepository,
)
from app.monitoring.application.scan_product import ScanCoordinator, ScanInProgressError, ScanProduct
from app.monitoring.application.dismiss_alert import DismissAlert, DismissRequest
from app.monitoring.application.verify_alert import VerifyAlert
from app.monitoring.domain.models import (
    Alert,
    Product,
    ProductScanStatus,
    Scan,
)
from app.monitoring.runtime_config import MonitoringRuntimeConfig, load_monitoring_config, monitoring_status

from .schemas import DemoResultRequest, ProductBatchDeleteRequest, ProductEntryRequest, amazon_asin
from app.monitoring.application.ports import DuplicateProductError, ProductRepository
from app.monitoring.domain.policies import supports_live_scan
from app.monitoring.config.markets import ENTRY_COUNTRIES, resolve_target_postal_code


@dataclass
class MonitoringContainer:
    products: ProductRepository
    scans: MemoryScanRepository
    alerts: MemoryAlertRepository
    scanner: Any
    scan_product: ScanProduct
    verify_alert: VerifyAlert
    dismiss_alert: DismissAlert
    demo_auto_recover: bool = False
    mode: str = "demo"
    scheduler_enabled: bool = False
    scheduler_running: bool = False

    @classmethod
    def demo(cls) -> "MonitoringContainer":
        products = MemoryProductRepository(_demo_products())
        scanner = DemoScanner(awaitable_products(products))
        return cls.from_dependencies(
            products=products,
            scanner=scanner,
            mode="demo",
        )

    @classmethod
    def from_dependencies(
        cls,
        products: ProductRepository,
        scanner: Any,
        *,
        scans: MemoryScanRepository | None = None,
        alerts: MemoryAlertRepository | None = None,
        mode: str = "real",
        demo_auto_recover: bool = False,
    ) -> "MonitoringContainer":
        scans = scans or MemoryScanRepository()
        alerts = alerts or MemoryAlertRepository()
        coordinator = ScanCoordinator()
        return cls(
            products=products,
            scans=scans,
            alerts=alerts,
            scanner=scanner,
            scan_product=ScanProduct(products, scans, alerts, scanner, coordinator),
            verify_alert=VerifyAlert(products, scans, alerts, scanner, coordinator),
            dismiss_alert=DismissAlert(alerts),
            demo_auto_recover=demo_auto_recover,
            mode=mode,
        )


def create_monitoring_app(
    container: MonitoringContainer | None = None,
    *,
    demo_auto_recover: bool = False,
    lifespan: Callable | None = None,
    monitoring_config: MonitoringRuntimeConfig | None = None,
) -> FastAPI:
    app = FastAPI(title="Cart Monitor MVP", version="0.2.0", lifespan=lifespan)
    state = container or MonitoringContainer.demo()
    state.demo_auto_recover = state.demo_auto_recover or demo_auto_recover
    runtime_config = monitoring_config or MonitoringRuntimeConfig(mode=state.mode)

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        template = Path(__file__).resolve().parents[1] / "templates" / "index.html"
        html = template.read_text(encoding="utf-8").replace("__ENTRY_COUNTRIES__", json.dumps(ENTRY_COUNTRIES))
        return re.sub(
            r"(?:<!--|/\*) demo:start (?:-->|\*/)(.*?)(?:<!--|/\*) demo:end (?:-->|\*/)",
            lambda block: block[1] if state.mode == "demo" else "",
            html,
            flags=re.DOTALL,
        )

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        payload = {
            "status": "ok",
            "mode": state.mode,
        }
        if state.mode == "real":
            payload.update(
                scheduler_enabled=state.scheduler_enabled,
                scheduler_running=state.scheduler_running,
            )
        return payload

    @app.get("/api/monitoring/status")
    def monitoring_runtime_status() -> dict:
        return monitoring_status(runtime_config, scheduler_running=state.scheduler_running)

    @app.get("/api/products")
    async def products() -> list[dict]:
        products = []
        for product in await state.products.list_enabled():
            payload = _product_json(product, demo=state.mode == "demo")
            if payload["status"] == "scanning" and not state.scan_product.coordinator.is_active(product.id):
                payload["status"] = "technical_failure"
            products.append(payload)
        return products

    @app.get("/api/products/manage")
    async def manage_products() -> list[dict]:
        if state.mode != "real":
            raise HTTPException(404, "商品管理仅在真实模式可用")
        return [_product_json(product) for product in await state.products.list_all()]

    @app.post("/api/products/batch-delete")
    async def delete_products(request: ProductBatchDeleteRequest) -> dict:
        if state.mode != "real":
            raise HTTPException(404, "商品管理仅在真实模式可用")
        coordinator = state.scan_product.coordinator
        locked = []
        try:
            for product_id in request.product_ids:
                coordinator.acquire(product_id)
                locked.append(product_id)
            await state.products.delete_many(request.product_ids)
        except ScanInProgressError as exc:
            raise HTTPException(409, "选中的商品正在扫描或复查，请等待结束后重试") from exc
        except KeyError as exc:
            raise HTTPException(409, "选中的商品已不存在，请刷新列表后重试") from exc
        finally:
            for product_id in locked:
                coordinator.release(product_id)
        return {"deleted_count": len(request.product_ids)}

    @app.post("/api/products", status_code=201)
    async def create_product(request: ProductEntryRequest) -> dict:
        if state.mode != "real":
            raise HTTPException(404, "商品录入仅在真实模式可用")
        product = Product(
            id=uuid4().hex,
            page_type="product_detail",
            roi_profile_id=(
                f"amazon_product_detail_{request.country.lower()}_buy_box"
                if request.platform == "amazon" else ""
            ),
            **request.model_dump(),
        )
        try:
            await state.products.create(product)
        except DuplicateProductError as exc:
            identity = (product.country, product.platform, product.store_code, product.sku.casefold())
            existing = next((
                row for row in await state.products.list_enabled()
                if (row.country, row.platform, row.store_code, row.sku.casefold()) == identity
            ), None)
            raise HTTPException(409, {
                "message": str(exc),
                "product_id": existing.id if existing else None,
            }) from exc
        return _product_json(product)

    async def ensure_scan_supported(product_id: str) -> None:
        if state.mode == "real":
            product = await state.products.get(product_id)
            if product is not None and not supports_live_scan(product):
                raise HTTPException(409, "此平台或站点暂未支持扫描")

    @app.get("/api/scans")
    async def scans() -> list[dict]:
        return [_scan_json(scan) for scan in await state.scans.list_all()]

    @app.get("/api/scans/{scan_id}/screenshots/{kind}")
    async def scan_screenshot(scan_id: str, kind: str):
        if kind not in {"full", "roi"}:
            raise HTTPException(status_code=404, detail="unknown screenshot kind")
        scan = next((item for item in await state.scans.list_all() if item.id == scan_id), None)
        if scan is None:
            raise HTTPException(status_code=404, detail="unknown scan")
        raw_path = scan.observation.full_screenshot_path if kind == "full" else scan.observation.roi_screenshot_path
        if not raw_path:
            raise HTTPException(status_code=404, detail="screenshot unavailable")
        root = (Path.cwd() / "output" / "artifacts").resolve()
        candidate = Path(raw_path).resolve()
        try:
            candidate.relative_to(root)
        except ValueError as error:
            raise HTTPException(status_code=404, detail="screenshot unavailable") from error
        if not candidate.is_file():
            raise HTTPException(status_code=404, detail="screenshot unavailable")
        return FileResponse(candidate, media_type="image/png")

    @app.get("/api/alerts")
    async def alerts() -> list[dict]:
        return [_alert_json(alert) for alert in await state.alerts.list_all()]

    @app.post("/api/products/{product_id}/scan")
    async def scan(product_id: str) -> dict:
        await ensure_scan_supported(product_id)
        try:
            result = await state.scan_product.execute(product_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error).strip("'")) from error
        except ScanInProgressError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return {
            "product_id": result.product.id,
            "status": result.product.status.value,
            "scan": _scan_json(result.scan),
            "alert": _alert_json(result.alert) if result.alert else None,
        }

    @app.post("/api/products/{product_id}/demo-result")
    async def set_demo_result(product_id: str, request: DemoResultRequest) -> dict:
        if state.mode != "demo" or not hasattr(state.scanner, "set_next_result"):
            raise HTTPException(status_code=404, detail="demo result is unavailable in real mode")
        product = await state.products.get(product_id)
        if product is None:
            raise HTTPException(status_code=404, detail=f"unknown product: {product_id}")
        state.scanner.set_next_result(product_id, ProductScanStatus(request.result))
        return {"product_id": product_id, "next_result": request.result}

    @app.post("/api/alerts/{alert_id}/verify")
    async def verify(alert_id: str) -> dict:
        alert = await state.alerts.get(alert_id)
        if alert is not None:
            await ensure_scan_supported(alert.product_id)
        if state.demo_auto_recover:
            demo_alert = await state.alerts.get(alert_id)
            if demo_alert is not None:
                state.scanner.set_outcome(demo_alert.product_id, ProductScanStatus.HEALTHY)
        try:
            alert = await state.verify_alert.execute(alert_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error).strip("'")) from error
        except ScanInProgressError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return _alert_json(alert)

    @app.post("/api/alerts/{alert_id}/dismiss")
    async def dismiss(alert_id: str, request: dict) -> dict:
        try:
            alert = await state.dismiss_alert.execute(alert_id, DismissRequest(
                operator=str(request.get("operator") or "local-operator"),
                reason=str(request.get("reason") or "confirmed_false_positive"),
                note=str(request.get("note") or ""),
            ))
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error).strip("'")) from error
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return _alert_json(alert)

    return app


def create_demo_app() -> FastAPI:
    """本地演示入口：使用确定性 DemoScanner，复查时自动模拟商品已恢复。"""
    return create_monitoring_app(MonitoringContainer.demo(), demo_auto_recover=True)


def _demo_products() -> list[Product]:
    products: list[Product] = []
    for country in ("DE", "IT"):
        for index in range(1, 11):
            product_id = f"{country}-{index:03d}"
            products.append(
                Product(
                    id=product_id,
                    country=country,
                    platform="amazon" if index % 2 else "shopify",
                    sku=f"{country}-SKU-{index:03d}",
                    url=f"https://demo.local/{country.lower()}/product-{index:03d}",
                    page_type="product_detail",
                    roi_profile_id="product_detail_default",
                    name=f"{country} home product {index}",
                )
            )
    return products


def awaitable_products(repository: MemoryProductRepository) -> list[Product]:
    return list(repository._products.values())


def _product_json(product: Product, *, demo: bool = False) -> dict:
    can_scan = demo or supports_live_scan(product)
    reason = None
    if not can_scan:
        reason = (
            f"Amazon {product.country} 站未配置 Live 扫描"
            if product.platform == "amazon" else f"{product.platform} 暂未接通 Live 扫描"
        )
    return {
        "id": product.id,
        "country": product.country,
        "platform": product.platform,
        "sku": product.sku,
        "asin": product.asin or (amazon_asin(product.url) if product.platform == "amazon" else ""),
        "store_code": product.store_code,
        "added_by": product.added_by,
        "can_scan": can_scan,
        "scan_unavailable_reason": reason,
        "target_postal_code": (
            resolve_target_postal_code(product.country) if product.platform == "amazon" else ""
        ),
        "name": product.name,
        "url": product.url,
        "page_type": product.page_type,
        "roi_profile": product.roi_profile_id,
        "enabled": product.enabled,
        "status": product.status.value,
    }


def _scan_json(scan: Scan) -> dict:
    observation = scan.observation
    return {
        "scan_id": scan.id,
        "product_id": scan.product_id,
        "status": scan.status.value,
        "ocr_text": observation.ocr_text,
        "matched_phrase": observation.matched_phrase,
        "ocr_confidence": observation.confidence,
        "error_code": observation.error_code,
        "error_message": observation.error_message,
        "full_screenshot_path": observation.full_screenshot_path,
        "roi_screenshot_path": observation.roi_screenshot_path,
        "cookie_summary": [
            {key: value for key, value in item.items() if key != "value_hash"}
            for item in observation.cookie_summary
        ],
        "screenshots": {
            "full_url": f"/api/scans/{scan.id}/screenshots/full" if observation.full_screenshot_path else None,
            "roi_url": f"/api/scans/{scan.id}/screenshots/roi" if observation.roi_screenshot_path else None,
        },
        "started_at": scan.started_at.isoformat(),
        "finished_at": scan.finished_at.isoformat(),
    }


def _alert_json(alert: Alert | None) -> dict | None:
    if alert is None:
        return None
    return {
        "id": alert.id,
        "type": alert.type.value,
        "status": alert.status.value,
        "product_id": alert.product_id,
        "failure_count": alert.failure_count,
        "operator_note": alert.operator_note,
    }
