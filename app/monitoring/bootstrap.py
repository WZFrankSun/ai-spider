from __future__ import annotations

from functools import partial

from fastapi import FastAPI

from app.monitoring.adapters.artifact_store_local import LocalArtifactStore
from app.monitoring.adapters.crawler_screenshot import (
    CrawlerScreenshotScanner,
    JsonScreenshotManifestSource,
)
from app.monitoring.adapters.demo_scanner import DemoScanner
from app.monitoring.adapters.memory_repositories import (
    MemoryAlertRepository,
    MemoryProductRepository,
    MemoryScanRepository,
)
from app.monitoring.adapters.ocr_tesseract import TesseractOcrAdapter
from app.monitoring.adapters.playwright_scanner import PlaywrightScanner
from app.monitoring.adapters.product_catalog import JsonProductCatalogLoader
from app.monitoring.adapters.roi import JsonRoiProfileLoader
from app.monitoring.adapters.mysql.engine import create_session_factory, create_sqlalchemy_engine
from app.monitoring.adapters.mysql.repositories import (
    SqlAlchemyAlertRepository,
    SqlAlchemyProductRepository,
    SqlAlchemyScanRepository,
)
from app.monitoring.api.routes import MonitoringContainer, create_monitoring_app
from app.monitoring.application.phrase_matching import JsonPhraseSetLoader
from app.monitoring.application.real_observation import RealObservationFactory
from app.monitoring.entrypoints.service import monitoring_lifespan
from app.monitoring.runtime_config import (
    MonitoringRuntimeConfig,
    load_monitoring_config,
    validate_real_prerequisites,
)


def build_monitoring_container(config: MonitoringRuntimeConfig) -> MonitoringContainer:
    if config.mode == "demo":
        return MonitoringContainer.demo()

    errors = validate_real_prerequisites(config)
    if errors:
        raise RuntimeError("real monitoring preflight failed: " + "; ".join(errors))

    catalog_products = JsonProductCatalogLoader().load(config.catalog_path)
    if config.database_url:
        engine = create_sqlalchemy_engine(config.database_url)
        sessions = create_session_factory(engine)
        products = SqlAlchemyProductRepository(sessions)
        scans = SqlAlchemyScanRepository(sessions)
        alerts = SqlAlchemyAlertRepository(sessions)
    else:
        products = MemoryProductRepository(catalog_products)
        scans = MemoryScanRepository()
        alerts = MemoryAlertRepository()
    artifact_store = LocalArtifactStore(config.artifact_root)
    roi_loader = JsonRoiProfileLoader(config.roi_profiles_path)
    phrase_loader = JsonPhraseSetLoader(config.phrase_sets_path)
    observation_factory = RealObservationFactory(
        TesseractOcrAdapter(
            lang=config.tesseract_languages,
            timeout_seconds=config.scan_timeout_seconds,
            tesseract_cmd=config.tesseract_cmd,
        ),
        phrase_loader,
    )

    if config.input_mode == "manifest":
        scanner = CrawlerScreenshotScanner(
            source=JsonScreenshotManifestSource(
                config.screenshot_manifest_path,
                config.screenshot_root,
            ),
            roi_profile_loader=roi_loader,
            observation_factory=observation_factory,
            artifact_store=artifact_store,
        )
    else:
        scanner = PlaywrightScanner(
            observation_factory=observation_factory,
            artifact_store=artifact_store,
            roi_profile_loader=roi_loader,
            timeout_ms=int(config.scan_timeout_seconds * 1000),
        )

    container = MonitoringContainer.from_dependencies(
        products=products,
        scans=scans,
        alerts=alerts,
        scanner=scanner,
        mode="real",
    )
    container.catalog_products = catalog_products
    if config.database_url:
        container.database_engine = engine
    return container


def create_application(config: MonitoringRuntimeConfig | None = None) -> FastAPI:
    runtime_config = config or load_monitoring_config()
    container = build_monitoring_container(runtime_config)
    lifespan = partial(monitoring_lifespan, container=container, config=runtime_config)
    return create_monitoring_app(container, lifespan=lifespan, monitoring_config=runtime_config)
