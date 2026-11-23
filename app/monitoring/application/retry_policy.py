from __future__ import annotations

import asyncio

from app.monitoring.application.ports import Scanner, ScanTarget
from app.monitoring.domain.models import ProductScanStatus, ScanObservation


async def scan_with_retry(
    scanner: Scanner,
    target: ScanTarget,
    attempts: int = 3,
    backoff_seconds: float = 0.0,
) -> ScanObservation:
    """Retry technical failures within one scan cycle.

    A valid inventory result is returned immediately. Exceptions are retried
    for the same reason as technical observations, then re-raised after the
    final attempt so the application layer can record the failure.
    """
    if attempts < 1:
        raise ValueError("attempts must be at least 1")
    if backoff_seconds < 0:
        raise ValueError("backoff_seconds cannot be negative")

    for attempt in range(attempts):
        try:
            observation = await scanner.scan(target)
        except Exception:
            if attempt >= attempts - 1:
                raise
            await _backoff(backoff_seconds)
            continue

        if observation.status != ProductScanStatus.TECHNICAL_FAILURE:
            return observation
        if observation.error_code == "READY_SELECTOR_MISSING" or attempt >= attempts - 1:
            return observation
        await _backoff(backoff_seconds)

    raise AssertionError("retry loop completed without an observation")


async def _backoff(seconds: float) -> None:
    if seconds:
        await asyncio.sleep(seconds)
