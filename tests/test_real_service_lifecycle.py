import asyncio
import unittest
from dataclasses import replace
from types import SimpleNamespace

from app.monitoring.api.routes import MonitoringContainer
from app.monitoring.entrypoints.service import (
    RuntimeHandles,
    start_monitoring_runtime,
    stop_monitoring_runtime,
)
from app.monitoring.runtime_config import MonitoringRuntimeConfig


class FakeBrowserManager:
    def __init__(self):
        self.started = 0
        self.closed = 0

    async def start(self):
        self.started += 1

    async def close(self):
        self.closed += 1


class FakeRunner:
    async def run_once(self):
        await asyncio.sleep(3600)


class FakeScanProduct:
    async def execute(self, product_id):
        return SimpleNamespace(observation=SimpleNamespace(status="healthy"))


class ServiceLifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def test_demo_lifespan_does_not_start_scheduler_or_browser(self):
        container = MonitoringContainer.demo()
        config = MonitoringRuntimeConfig(mode="demo", scheduler_enabled=True)

        handles = await start_monitoring_runtime(container, config)

        self.assertFalse(handles.scheduler_enabled)
        self.assertIsNone(handles.scheduler_task)

    async def test_real_lifespan_starts_scheduler_once(self):
        container = MonitoringContainer.demo()
        container.mode = "real"
        browser = FakeBrowserManager()
        container.scanner = SimpleNamespace(browser_manager=browser)
        container.scan_product = FakeScanProduct()
        config = MonitoringRuntimeConfig(mode="real", scheduler_enabled=True, scan_interval_seconds=3600)

        handles = await start_monitoring_runtime(container, config, runner=FakeRunner())

        self.assertTrue(handles.scheduler_enabled)
        self.assertIsNotNone(handles.scheduler_task)
        self.assertEqual(browser.started, 1)
        await stop_monitoring_runtime(handles)
        self.assertEqual(browser.closed, 1)

    async def test_shutdown_cancels_scheduler_and_closes_browser(self):
        container = MonitoringContainer.demo()
        container.mode = "real"
        browser = FakeBrowserManager()
        container.scanner = SimpleNamespace(browser_manager=browser)
        config = MonitoringRuntimeConfig(mode="real", scheduler_enabled=True)

        handles = await start_monitoring_runtime(container, config, runner=FakeRunner())
        await stop_monitoring_runtime(handles)

        self.assertTrue(handles.scheduler_task.done())
        self.assertEqual(browser.closed, 1)


if __name__ == "__main__":
    unittest.main()
