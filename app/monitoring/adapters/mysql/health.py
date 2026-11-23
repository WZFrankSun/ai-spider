from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


@dataclass(frozen=True)
class DatabaseHealth:
    ok: bool
    error: str | None = None


async def check_database(engine: AsyncEngine | None) -> DatabaseHealth:
    if engine is None:
        return DatabaseHealth(ok=False, error="database engine is not configured")
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except Exception:
        return DatabaseHealth(ok=False, error="database health check failed")
    return DatabaseHealth(ok=True)
