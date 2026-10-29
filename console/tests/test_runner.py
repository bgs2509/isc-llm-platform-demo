import httpx

from app.runner import Runner, Settings

VLLM_TEXT = "vllm:kv_cache_usage_perc 0.25\nvllm:num_requests_waiting 3\nvllm:num_requests_running 5\n"


async def test_tick_of_an_active_run_appends_kv_cache_and_waiting(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/json":
            return httpx.Response(200, json={"gpu_utilization_percent": 80})
        return httpx.Response(200, text=VLLM_TEXT)

    runner = Runner(Settings(gateway_url="http://gw", model="m", tenants={},
                             vllm_metrics_url="http://vllm/metrics", gpu_url="http://gpu/json",
                             data_dir=str(tmp_path)))
    runner.run = {"active": True, "started": 0.0, "t0": 0.0, "finished": [], "in_flight": 0,
                  "timeline": [], "id": "r1", "params": {"duration_s": 30, "concurrency": 1}}
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        await runner._tick(client)
    point = runner.run["timeline"][0]
    assert point["kv_cache_pct"] == 25.0
    assert point["vllm_waiting"] == 3.0
    assert point["gpu_util"] == 80


async def test_load_client_fails_fast_on_connect_and_pauses_after_connection_errors(tmp_path, monkeypatch):
    # Drill D.2 (2026-10-29): with one 180 s timeout for everything, connects to a replaced gateway pod hung
    # for minutes, and the instant failures before that spun 6,815 requests in a busy loop.
    import time

    from app import runner as runner_mod
    from app.stats import RequestResult

    seen = {}
    real_client = httpx.AsyncClient

    class Capture(real_client):
        def __init__(self, *args, **kwargs):
            seen["timeout"] = kwargs.get("timeout")
            kwargs["transport"] = httpx.MockTransport(lambda request: httpx.Response(500))  # no TLS setup
            super().__init__(*args, **kwargs)

    calls = []

    async def failing_request(*args, **kwargs):
        calls.append(1)
        return RequestResult(False, 0, 0.001)

    monkeypatch.setattr(runner_mod.httpx, "AsyncClient", Capture)
    monkeypatch.setattr(runner_mod, "one_request", failing_request)
    runner = Runner(Settings(gateway_url="http://gw", model="m", tenants={"t": "k"},
                             vllm_metrics_url="http://vllm/metrics", gpu_url="http://gpu/json",
                             data_dir=str(tmp_path)))
    params = {"tenant": "t", "concurrency": 1, "duration_s": 1, "max_tokens": 8, "shape": "unique",
              "prompt_words": 5, "gpu_usd_per_hour": 0.2}
    run = {"id": "r1", "params": params, "active": True, "started": time.time(), "t0": time.perf_counter(),
           "finished": [], "in_flight": 0, "timeline": []}
    runner.run = run
    await runner._execute(run, "k")
    assert seen["timeout"].connect == 5.0 and seen["timeout"].read == 180.0
    assert 1 <= len(calls) <= 3
