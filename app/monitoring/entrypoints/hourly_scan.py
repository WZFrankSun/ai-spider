from __future__ import annotations

import asyncio

from app.monitoring.application.scheduled_scan import HourlyScanRunner, ScanBatchSummary


async def run_once(runner: HourlyScanRunner) -> ScanBatchSummary:
    return await runner.run_once()


async def run_forever(
    runner: HourlyScanRunner,
    *,
    interval_seconds: float = 3600.0,
    stop_event: asyncio.Event | None = None,
) -> None:
    if interval_seconds <= 0:
        raise ValueError("interval_seconds must be positive")
    stop_event = stop_event or asyncio.Event()
    while not stop_event.is_set():
        await runner.run_once()
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds)
        except asyncio.TimeoutError:
            continue
