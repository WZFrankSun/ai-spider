from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass
from typing import AsyncIterator

from app.monitoring.application.scheduled_scan import HourlyScanRunner
from app.monitoring.adapters.mysql.health import check_database
from app.monitoring.entrypoints.hourly_scan import run_forever
from app.monitoring.runtime_config import MonitoringRuntimeConfig


@dataclass
class RuntimeHandles:
    stop_event: asyncio.Event
    scheduler_task: asyncio.Task | None
    browser_manager: object | None
    scheduler_enabled: bool


async def start_monitoring_runtime(
    container,
    config: MonitoringRuntimeConfig,
    *,
    runner: object | None = None,
) -> RuntimeHandles:
    if config.mode != "real":
        return RuntimeHandles(asyncio.Event(), None, None, False)

    database_engine = getattr(container, "database_engine", None)
    if database_engine is not None:
        health = await check_database(database_engine)
        if not health.ok:
            raise RuntimeError(health.error or "database health check failed")

    scanner = getattr(container, "scanner", None)
    catalog_products = getattr(container, "catalog_products", None)
    if catalog_products:
        for product in catalog_products:
            await container.products.save(product)
    browser_manager = getattr(scanner, "browser_manager", None)
    if browser_manager is not None:
        await browser_manager.start()

    stop_event = asyncio.Event()
    scheduler_task = None
    enabled = bool(config.scheduler_enabled)
    if enabled:
        scan_runner = runner or HourlyScanRunner(
            container.products,
            container.scan_product,
            max_concurrency=config.max_concurrency,
            per_product_timeout_seconds=config.scan_timeout_seconds,
        )
        scheduler_task = asyncio.create_task(
            run_forever(
                scan_runner,
                interval_seconds=config.scan_interval_seconds,
                stop_event=stop_event,
            )
        )
    container.scheduler_enabled = enabled
    container.scheduler_running = bool(scheduler_task)
    return RuntimeHandles(stop_event, scheduler_task, browser_manager, enabled)


async def stop_monitoring_runtime(handles: RuntimeHandles) -> None:
    handles.stop_event.set()
    if handles.scheduler_task is not None:
        handles.scheduler_task.cancel()
        with suppress(asyncio.CancelledError):
            await handles.scheduler_task
    if handles.browser_manager is not None:
        await handles.browser_manager.close()


@asynccontextmanager
async def monitoring_lifespan(app, *, container, config: MonitoringRuntimeConfig) -> AsyncIterator[None]:
    handles = await start_monitoring_runtime(container, config)
    app.state.monitoring_runtime = handles
    try:
        yield
    finally:
        await stop_monitoring_runtime(handles)
