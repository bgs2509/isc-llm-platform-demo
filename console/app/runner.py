"""Run controller: a 1 Hz sampler (GPU and vLLM metrics) and one load-test run at a time."""
from __future__ import annotations

import asyncio
import json
import os
import time
import uuid
from dataclasses import dataclass

import httpx

from .loadgen import make_prompt, one_request
from .stats import RequestResult, parse_prometheus_text, percentile, summarize

WINDOW_S = 5.0
# A replaced gateway pod: connects hang until the timeout, so connect gets its own short one.
REQUEST_TIMEOUT_S, CONNECT_TIMEOUT_S, RETRY_PAUSE_S = 180.0, 5.0, 0.5


@dataclass
class Settings:
    gateway_url: str
    model: str
    tenants: dict[str, str]
    vllm_metrics_url: str
    gpu_url: str
    data_dir: str
    prometheus_url: str = "http://prometheus:9090"


class Runner:
    def __init__(self, settings: Settings) -> None:
        self.s = settings
        self.subscribers: set[asyncio.Queue] = set()
        self.run: dict | None = None
        self.runs: list[dict] = []
        self.latest: dict = {}
        self._stop = asyncio.Event()
        self._prev_gen: float | None = None
        self._prev_t: float | None = None
        self._load_runs()

    # ---- persistence -------------------------------------------------
    def _runs_path(self) -> str:
        return os.path.join(self.s.data_dir, "runs.json")

    def _load_runs(self) -> None:
        try:
            with open(self._runs_path(), encoding="utf8") as f:
                self.runs = json.load(f)
        except (OSError, ValueError):
            self.runs = []

    def _save_runs(self) -> None:
        try:
            os.makedirs(self.s.data_dir, exist_ok=True)
            with open(self._runs_path(), "w", encoding="utf8") as f:
                json.dump(self.runs, f)
        except OSError:
            pass  # the console keeps working in memory

    # ---- sampler -----------------------------------------------------
    async def _get(self, client: httpx.AsyncClient, url: str, as_json: bool):
        r = await client.get(url)
        r.raise_for_status()
        return r.json() if as_json else r.text

    async def _tick(self, client: httpx.AsyncClient) -> dict:
        gpu, vm = await asyncio.gather(
            self._get(client, self.s.gpu_url, True),
            self._get(client, self.s.vllm_metrics_url, False),
            return_exceptions=True,
        )
        now = time.time()
        tick: dict = {"t": now}
        if isinstance(gpu, dict):
            tick["gpu_util"] = gpu.get("gpu_utilization_percent")
            tick["gpu_power_w"] = gpu.get("gpu_power_watts")
            tick["gpu_temp_c"] = gpu.get("gpu_temperature_celsius")
        if isinstance(vm, str):
            m = parse_prometheus_text(vm)
            tick["vllm_running"] = m.get("vllm:num_requests_running")
            tick["vllm_waiting"] = m.get("vllm:num_requests_waiting")
            kv = m.get("vllm:kv_cache_usage_perc")
            tick["kv_cache_pct"] = None if kv is None else kv * 100.0
            gen = m.get("vllm:generation_tokens_total")
            if gen is not None and self._prev_gen is not None and self._prev_t and now > self._prev_t:
                tick["server_tokens_per_s"] = max(0.0, (gen - self._prev_gen) / (now - self._prev_t))
            self._prev_gen, self._prev_t = gen, now
        tick["run"] = self._snapshot()
        run = self.run
        if run and run["active"]:
            run["timeline"].append({
                "t": now - run["started"],
                "gpu_util": tick.get("gpu_util"),
                "tokens_per_s": tick["run"].get("tokens_per_s"),
                "ttft_p95_s": tick["run"].get("ttft_p95_s"),
                "in_flight": tick["run"].get("in_flight"),
                "kv_cache_pct": tick.get("kv_cache_pct"),
                "vllm_waiting": tick.get("vllm_waiting"),
            })
        return tick

    async def sample_loop(self) -> None:
        async with httpx.AsyncClient(timeout=2.0) as client:
            while True:
                try:
                    self.latest = await self._tick(client)
                    for q in list(self.subscribers):
                        if q.full():
                            q.get_nowait()
                        q.put_nowait(self.latest)
                except Exception:  # keep sampling whatever happens
                    pass
                await asyncio.sleep(1.0)

    # ---- run ---------------------------------------------------------
    def _snapshot(self) -> dict:
        r = self.run
        if not r:
            return {"active": False}
        now = time.perf_counter()
        window_ok = [x for ts, x in r["finished"] if now - ts <= WINDOW_S and x.ok]
        ttft = [x.ttft_s for x in window_ok if x.ttft_s is not None]
        ok_all = [x for _, x in r["finished"] if x.ok]
        return {
            "active": r["active"],
            "id": r["id"],
            "elapsed_s": (now - r["t0"]) if r["active"] else r.get("elapsed_s"),
            "duration_s": r["params"]["duration_s"],
            "concurrency": r["params"]["concurrency"],
            "in_flight": r["in_flight"],
            "ok": len(ok_all),
            "failed": len(r["finished"]) - len(ok_all),
            "cache_hits": sum(1 for x in ok_all if x.cached),
            "ttft_p50_s": percentile(ttft, 50),
            "ttft_p95_s": percentile(ttft, 95),
            "tokens_per_s": sum(x.completion_tokens for x in window_ok) / WINDOW_S,
        }

    async def start(self, params: dict) -> dict:
        if self.run and self.run["active"]:
            raise RuntimeError("a run is already active")
        key = self.s.tenants[params["tenant"]]
        run = {
            "id": uuid.uuid4().hex[:8], "params": params, "active": True,
            "started": time.time(), "t0": time.perf_counter(),
            "finished": [], "in_flight": 0, "timeline": [],
        }
        self.run = run
        self._stop = asyncio.Event()
        asyncio.create_task(self._execute(run, key))
        return {"id": run["id"]}

    def stop(self) -> None:
        self._stop.set()

    async def _execute(self, run: dict, key: str) -> None:
        p = run["params"]
        deadline = run["t0"] + p["duration_s"]
        limits = httpx.Limits(max_connections=p["concurrency"] + 4)
        timeout = httpx.Timeout(REQUEST_TIMEOUT_S, connect=CONNECT_TIMEOUT_S)
        async with httpx.AsyncClient(timeout=timeout, limits=limits) as client:
            async def worker() -> None:
                while time.perf_counter() < deadline and not self._stop.is_set():
                    prompt = make_prompt(p["shape"], p["prompt_words"])
                    run["in_flight"] += 1
                    try:
                        result = await one_request(client, self.s.gateway_url, key, self.s.model,
                                                   prompt, p["max_tokens"])
                    finally:
                        run["in_flight"] -= 1
                    run["finished"].append((time.perf_counter(), result))
                    if result.status == 0:  # no connection: do not spin while the gateway is away
                        await asyncio.sleep(RETRY_PAUSE_S)

            await asyncio.gather(*[worker() for _ in range(p["concurrency"])])
        elapsed = max(time.perf_counter() - run["t0"], 1e-9)
        run["elapsed_s"] = elapsed
        results: list[RequestResult] = [x for _, x in run["finished"]]
        gpu = [pt["gpu_util"] for pt in run["timeline"] if pt.get("gpu_util") is not None]
        summary = summarize(results, elapsed, gpu, p["gpu_usd_per_hour"])
        run["active"] = False
        self.runs.append({
            "id": run["id"], "label": None, "params": p, "summary": summary,
            "timeline": run["timeline"], "finished_at": time.time(),
        })
        self._save_runs()

    def label(self, run_id: str, label: str | None) -> bool:
        for r in self.runs:
            if r["id"] == run_id:
                r["label"] = label
                self._save_runs()
                return True
        return False
