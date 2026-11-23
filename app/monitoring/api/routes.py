from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
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

from .schemas import DemoResultRequest


@dataclass
class MonitoringContainer:
    products: MemoryProductRepository
    scans: MemoryScanRepository
    alerts: MemoryAlertRepository
    scanner: Any
    scan_product: ScanProduct
    verify_alert: VerifyAlert
    dismiss_alert: DismissAlert
    legacy_auto_recover: bool = False
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
        products: MemoryProductRepository,
        scanner: Any,
        *,
        scans: MemoryScanRepository | None = None,
        alerts: MemoryAlertRepository | None = None,
        mode: str = "real",
        legacy_auto_recover: bool = False,
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
            legacy_auto_recover=legacy_auto_recover,
            mode=mode,
        )


def create_monitoring_app(
    container: MonitoringContainer | None = None,
    *,
    legacy_auto_recover: bool = False,
    lifespan: Callable | None = None,
    monitoring_config: MonitoringRuntimeConfig | None = None,
) -> FastAPI:
    app = FastAPI(title="Cart Monitor MVP", version="0.2.0", lifespan=lifespan)
    state = container or MonitoringContainer.demo()
    state.legacy_auto_recover = state.legacy_auto_recover or legacy_auto_recover
    runtime_config = monitoring_config or MonitoringRuntimeConfig(mode=state.mode)

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        template = Path(__file__).resolve().parents[2] / "mvp" / "templates" / "index.html"
        return template.read_text(encoding="utf-8")

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
            payload = _product_json(product)
            if payload["status"] == "scanning" and not state.scan_product.coordinator.is_active(product.id):
                payload["status"] = "technical_failure"
            products.append(payload)
        return products

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
        if state.legacy_auto_recover:
            legacy_alert = await state.alerts.get(alert_id)
            if legacy_alert is not None:
                state.scanner.set_outcome(legacy_alert.product_id, ProductScanStatus.HEALTHY)
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


def _product_json(product: Product) -> dict:
    return {
        "id": product.id,
        "country": product.country,
        "platform": product.platform,
        "sku": product.sku,
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
