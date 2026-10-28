"""Console API: configuration, load-test runs, live stream (server-sent events), static page."""
from __future__ import annotations

import asyncio
import json
import os
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .runner import Runner, Settings


def load_settings() -> Settings:
    return Settings(
        gateway_url=os.environ.get("GATEWAY_URL", "http://litellm:4000"),
        model=os.environ.get("GATEWAY_MODEL", "qwen38"),
        tenants=json.loads(os.environ.get("TENANT_KEYS_JSON", "{}")),
        vllm_metrics_url=os.environ.get("VLLM_METRICS_URL", "http://127.0.0.1:18300/metrics"),
        gpu_url=os.environ.get("GPU_URL", "http://127.0.0.1:18311/json"),
        data_dir=os.environ.get("DATA_DIR", "/data"),
    )


runner = Runner(load_settings())


@asynccontextmanager
async def lifespan(_: FastAPI):
    task = asyncio.create_task(runner.sample_loop())
    yield
    task.cancel()


app = FastAPI(title="LLM platform console", lifespan=lifespan)


class RunParams(BaseModel):
    tenant: str
    concurrency: int = Field(4, ge=1, le=64)
    duration_s: int = Field(30, ge=5, le=300)
    max_tokens: int = Field(128, ge=8, le=2048)
    shape: Literal["unique", "repeated"] = "unique"
    prompt_words: int = Field(60, ge=5, le=2000)
    gpu_usd_per_hour: float = Field(0.2, ge=0, le=1000)


class LabelBody(BaseModel):
    label: str | None = Field(None, max_length=40)


@app.get("/healthz")
async def healthz() -> dict:
    return {"ok": True}


@app.get("/api/config")
async def config() -> dict:
    return {"model": runner.s.model, "tenants": sorted(runner.s.tenants)}


@app.post("/api/runs")
async def start_run(params: RunParams) -> dict:
    if params.tenant not in runner.s.tenants:
        raise HTTPException(404, "unknown tenant")
    try:
        return await runner.start(params.model_dump())
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc


@app.post("/api/runs/stop")
async def stop_run() -> dict:
    runner.stop()
    return {"stopping": True}


@app.get("/api/runs")
async def list_runs() -> list[dict]:
    return [{k: v for k, v in r.items() if k != "timeline"} | {"points": len(r["timeline"])}
            for r in reversed(runner.runs)]


@app.get("/api/runs/{run_id}")
async def get_run(run_id: str) -> dict:
    for r in runner.runs:
        if r["id"] == run_id:
            return r
    raise HTTPException(404, "unknown run")


@app.patch("/api/runs/{run_id}")
async def label_run(run_id: str, body: LabelBody) -> dict:
    if not runner.label(run_id, body.label):
        raise HTTPException(404, "unknown run")
    return {"id": run_id, "label": body.label}


@app.get("/api/stream")
async def stream(request: Request) -> StreamingResponse:
    queue: asyncio.Queue = asyncio.Queue(maxsize=10)
    runner.subscribers.add(queue)

    async def events():
        try:
            yield f"data: {json.dumps(runner.latest)}\n\n"
            while not await request.is_disconnected():
                try:
                    tick = await asyncio.wait_for(queue.get(), timeout=15)
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
                    continue
                yield f"data: {json.dumps(tick)}\n\n"
        finally:
            runner.subscribers.discard(queue)

    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache"})


app.mount("/", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static"), html=True),
          name="static")
