"""Console API: configuration, load-test runs, live stream (server-sent events), static page."""
from __future__ import annotations

import asyncio
import functools
import json
import logging
import os
from contextlib import asynccontextmanager
from typing import Literal

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import agent, corpus, evaluate, platform_status
from .runner import Runner, Settings
from .stats import GPU_USD_PER_HOUR


log = logging.getLogger(__name__)
# uvicorn configures only its own loggers; the console's log anchors are INFO lines on stderr.
logging.getLogger("app").setLevel(logging.INFO)
if not logging.getLogger().handlers:
    logging.basicConfig(format="%(levelname)s %(name)s %(message)s")


def load_settings() -> Settings:
    return Settings(
        gateway_url=os.environ.get("GATEWAY_URL", "http://litellm:4000"),
        model=os.environ.get("GATEWAY_MODEL", "qwen38"),
        tenants=json.loads(os.environ.get("TENANT_KEYS_JSON", "{}")),
        vllm_metrics_url=os.environ.get("VLLM_METRICS_URL", "http://127.0.0.1:18300/metrics"),
        gpu_url=os.environ.get("GPU_URL", "http://127.0.0.1:18311/json"),
        data_dir=os.environ.get("DATA_DIR", "/data"),
        prometheus_url=os.environ.get("PROMETHEUS_URL", "http://prometheus:9090"),
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
    gpu_usd_per_hour: float = Field(GPU_USD_PER_HOUR, ge=0, le=1000)


class LabelBody(BaseModel):
    label: str | None = Field(None, max_length=40)


@app.get("/healthz")
async def healthz() -> dict:
    return {"ok": True}


@app.get("/api/config")
async def config() -> dict:
    return {"model": runner.s.model, "tenants": sorted(runner.s.tenants)}


@app.get("/api/status")
async def status(view: Literal["alerts", "teams", "signals", "health"]) -> list | dict:
    return await platform_status.fetch(view, runner.s.prometheus_url)


class AskBody(BaseModel):
    tenant: str
    question: str = Field(max_length=500)


@functools.lru_cache(maxsize=1)
def search_index() -> corpus.Index:
    """The blog index, built once on first use."""
    return corpus.Index([c for a in corpus.load_articles() for c in corpus.chunk(a)])


def search_docs(query: str) -> list[dict]:
    return [{"title": h.chunk.title, "url": h.chunk.url, "text": h.chunk.text}
            for h in search_index().search(query, k=3)]


@app.post("/api/agent/ask")
async def agent_ask(body: AskBody) -> dict:
    key = runner.s.tenants.get(body.tenant)
    if key is None:
        raise HTTPException(404, "unknown tenant")

    async def status(view: str):
        return await platform_status.fetch(view, runner.s.prometheus_url)

    async with httpx.AsyncClient(timeout=120.0) as client:
        result = await agent.run_agent(
            body.question, client=client, gateway_url=runner.s.gateway_url, model=runner.s.model,
            key=key, team=body.tenant, search=search_docs, status=status, no_cache=False)
    return result.to_dict()


class EvalBody(BaseModel):
    tenant: str


eval_state: dict = {"task": None, "latest": evaluate.load_result(runner.s.data_dir)}


async def run_eval_job(team: str, key: str) -> None:
    """Run the 16 questions with the team key and keep the result (memory and disk)."""
    questions, snapshots = evaluate.load_eval_set()
    s = runner.s
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            async def ask(question: str, snapshot: dict):
                async def status(view: str):
                    return await platform_status.fetch(view, snapshot=snapshot)

                return await agent.run_agent(question, client=client, gateway_url=s.gateway_url, model=s.model,
                                             key=key, team=team, search=search_docs, status=status, no_cache=True)

            async def judge(context: str, answer: str, facts: list[str]):
                return await evaluate.judge_answer(client, s.gateway_url, s.model, key, context, answer, facts)

            result = await evaluate.run_evaluation(
                questions, snapshots, search_index(), ask, judge, team=team,
                chunking=evaluate.chunking_comparison(corpus.load_articles(), questions))
    except Exception as exc:  # the run must never take the console down
        log.error("[Evaluate][job][FAILED] %s", type(exc).__name__)
        return
    eval_state["latest"] = result
    evaluate.save_result(s.data_dir, result)


@app.post("/api/agent/eval")
async def agent_eval(body: EvalBody) -> dict:
    key = runner.s.tenants.get(body.tenant)
    if key is None:
        raise HTTPException(404, "unknown tenant")
    task = eval_state["task"]
    if task is not None and not task.done():
        raise HTTPException(409, "an evaluation is already running")
    eval_state["task"] = asyncio.create_task(run_eval_job(body.tenant, key))
    return {"started": True}


@app.get("/api/agent/eval")
async def agent_eval_result() -> dict:
    if eval_state["latest"] is None:
        raise HTTPException(404, "no evaluation has run yet")
    return eval_state["latest"]


@app.get("/metrics")
async def metrics() -> Response:
    return Response(evaluate.metrics_text(eval_state["latest"]), media_type="text/plain")


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
