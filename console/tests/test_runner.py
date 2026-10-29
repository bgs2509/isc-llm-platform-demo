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
