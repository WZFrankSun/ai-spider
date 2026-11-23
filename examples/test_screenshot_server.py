import asyncio
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Literal

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

ROOT = next(
    parent
    for parent in Path(__file__).resolve().parents
    if (parent / "app" / "__init__.py").is_file()
)
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_screenshot import (  # noqa: E402
    MARKET_POSTAL_CODES,
    MQ_SEND_MODE,
    TASKS,
    main,
    postal_code_for_market,
)

HOST = "0.0.0.0"
PORT = 28000

app = FastAPI(title="Amazon screenshot trigger")
jobs: dict[str, dict] = {}
current_job_id = ""


class ScreenshotTask(BaseModel):
    sku: str = Field(min_length=1)
    url: str = Field(min_length=1)
    market: str = Field(min_length=1)


class ScreenshotRequest(BaseModel):
    tasks: list[ScreenshotTask] | None = None
    show_browser: bool = False
    mq_send_mode: Literal["batch", "each"] = MQ_SEND_MODE


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _normalize_tasks(request: ScreenshotRequest) -> list[dict] | None:
    if request.tasks is None:
        return None
    if not request.tasks:
        raise HTTPException(status_code=400, detail="tasks must not be empty")

    normalized = []
    for task in request.tasks:
        market = task.market.upper()
        try:
            postal_code_for_market(market)
        except KeyError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        url = task.url.strip()
        if not url.startswith(("http://", "https://")):
            raise HTTPException(status_code=400, detail=f"invalid url: {url}")
        normalized.append({
            "sku": task.sku.strip(),
            "url": url,
            "market": market,
        })
    return normalized


async def _execute(job_id: str, request: ScreenshotRequest, tasks: list[dict] | None) -> None:
    global current_job_id
    job = jobs[job_id]
    try:
        job["summary"] = await main(
            show_browser=request.show_browser,
            mq_send_mode=request.mq_send_mode,
            tasks=tasks,
        )
        job["status"] = "succeeded"
    except Exception as error:
        job["status"] = "failed"
        job["error"] = str(error)
    finally:
        job["finished_at"] = _now()
        if current_job_id == job_id:
            current_job_id = ""


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.post("/api/screenshots", status_code=202)
async def trigger_screenshots(request: ScreenshotRequest) -> dict:
    global current_job_id
    if current_job_id:
        raise HTTPException(
            status_code=409,
            detail={"message": "a screenshot job is already running", "job_id": current_job_id},
        )

    tasks = _normalize_tasks(request)
    job_id = uuid.uuid4().hex
    job = {
        "job_id": job_id,
        "status": "running",
        "total": len(TASKS if tasks is None else tasks),
        "mq_send_mode": request.mq_send_mode,
        "created_at": _now(),
        "finished_at": "",
        "summary": None,
        "error": "",
    }
    jobs[job_id] = job
    current_job_id = job_id
    asyncio.create_task(_execute(job_id, request, tasks))
    return job


@app.get("/api/screenshots/{job_id}")
async def screenshot_job(job_id: str) -> dict:
    job = jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return job


if __name__ == "__main__":
    uvicorn.run(app, host=HOST, port=PORT)
