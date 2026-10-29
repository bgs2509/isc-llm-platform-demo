import httpx

from app import platform_status
from app.stats import GPU_USD_PER_HOUR, cost_per_million_tokens

BASE = "http://prom"

RULES = {"status": "success", "data": {"groups": [{"rules": [
    {"name": "ModelQueueBuildingUp", "query": "sum(vllm:num_requests_waiting) > 4", "state": "firing"},
    {"name": "GpuUnderusedUnderLoad",
     "query": "avg_over_time(gpu_utilization_percent[2m]) < 30 and sum(vllm:num_requests_running) > 4",
     "state": "inactive"},
]}]}}


def _vector(*items: tuple[dict, str]) -> dict:
    return {"status": "success", "data": {"resultType": "vector",
            "result": [{"metric": m, "value": [1.0, v]} for m, v in items]}}


def _matrix(values: list[str]) -> dict:
    return {"status": "success", "data": {"resultType": "matrix", "result": [
        {"metric": {}, "values": [[1000 + 30 * i, v] for i, v in enumerate(values)]}]}}


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def _boom(request: httpx.Request) -> httpx.Response:
    raise httpx.ConnectError("no route")


def _prom(query_values: dict[str, dict] | None = None, range_values: dict[str, list[str]] | None = None):
    """Fake Prometheus: instant and range answers keyed by a substring of the query."""
    def handler(request: httpx.Request) -> httpx.Response:
        path, q = request.url.path, request.url.params.get("query", "")
        if path == "/api/v1/rules":
            assert request.url.params["type"] == "alert"
            return httpx.Response(200, json=RULES)
        if path == "/api/v1/query":
            for key, body in (query_values or {}).items():
                if key in q:
                    return httpx.Response(200, json=body)
            return httpx.Response(200, json=_vector())
        if path == "/api/v1/query_range":
            assert request.url.params["step"] == "30"
            span = float(request.url.params["end"]) - float(request.url.params["start"])
            assert span == 900
            for key, vals in (range_values or {}).items():
                if key in q:
                    return httpx.Response(200, json=_matrix(vals))
            return httpx.Response(200, json=_matrix(["0"]))
        return httpx.Response(404)
    return handler


async def test_alerts_rows_and_states():
    async with _client(_prom({"num_requests_waiting": _vector(({}, "7"))})) as c:
        rows = await platform_status.fetch("alerts", BASE, client=c)
    assert [r["state"] for r in rows] == ["firing", "inactive"]
    assert rows[0]["name"] == "ModelQueueBuildingUp"
    assert rows[0]["query"] == "sum(vllm:num_requests_waiting) > 4"


async def test_alert_value_is_left_side_or_none_for_and():
    seen: list[str] = []
    inner = _prom({"num_requests_waiting": _vector(({}, "7"))})

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/query":
            seen.append(request.url.params["query"])
        return inner(request)

    async with _client(handler) as c:
        rows = await platform_status.fetch("alerts", BASE, client=c)
    assert rows[0]["value"] == 7.0
    assert rows[1]["value"] is None
    assert seen == ["sum(vllm:num_requests_waiting)"]


async def test_teams_one_row_per_alias():
    qv = {
        "total_requests_metric_total": _vector(({"api_key_alias": "research"}, "0.5"),
                                               ({"api_key_alias": "engineering"}, "1.5")),
        "total_tokens_metric_total": _vector(({"api_key_alias": "research"}, "40"),
                                             ({"api_key_alias": "engineering"}, "90")),
    }
    async with _client(_prom(qv)) as c:
        rows = await platform_status.fetch("teams", BASE, client=c)
    by = {r["team"]: r for r in rows}
    assert by["research"] == {"team": "research", "requests_per_s": 0.5, "tokens_per_s": 40.0}
    assert by["engineering"]["tokens_per_s"] == 90.0
    assert len(rows) == 2


async def test_signals_five_entries_with_series_and_cost_from_usage():
    rv = {"generation_tokens_total": ["100", "200", "0"], "time_to_first_token": ["0.4", "NaN", "0.6"]}
    async with _client(_prom(range_values=rv)) as c:
        out = await platform_status.fetch("signals", BASE, client=c)
    assert list(out) == ["reliability", "latency", "usage", "errors", "cost"]
    assert out["usage"]["value"] == 0.0
    assert [p[1] for p in out["usage"]["series"]] == [100.0, 200.0, 0.0]
    assert [p[1] for p in out["latency"]["series"]] == [0.4, None, 0.6]
    assert out["latency"]["value"] == 0.6
    assert out["cost"]["series"][0][1] == cost_per_million_tokens(GPU_USD_PER_HOUR, 100.0)
    assert out["cost"]["series"][2][1] is None
    assert out["cost"]["series"][0][0] == out["usage"]["series"][0][0]


async def test_health_up_down_unknown():
    qv = {"up": _vector(({"job": "vllm"}, "1"), ({"job": "gpu"}, "0"), ({"job": "gateway"}, "1"))}
    async with _client(_prom(qv)) as c:
        out = await platform_status.fetch("health", BASE, client=c)
    assert out == {"prometheus": True, "vllm": "up", "gpu": "down", "gateway": "up",
                   "console": "unknown"}


async def test_health_prometheus_unreachable_all_unknown():
    async with _client(_boom) as c:
        out = await platform_status.fetch("health", BASE, client=c)
    assert out == {"prometheus": False, "vllm": "unknown", "gpu": "unknown", "gateway": "unknown",
                   "console": "unknown"}


async def test_unknown_view_and_connection_error():
    async with _client(_prom()) as c:
        assert "error" in await platform_status.fetch("nope", BASE, client=c)
    async with _client(_boom) as c:
        for view in ("alerts", "teams", "signals"):
            assert await platform_status.fetch(view, BASE, client=c) == {"error": "prometheus unavailable"}


async def test_snapshot_returned_unchanged():
    snap = {"alerts": [{"name": "A", "state": "firing", "query": "x > 1", "value": 3.0}],
            "teams": [{"team": "t", "requests_per_s": 1.0, "tokens_per_s": 2.0}]}
    assert await platform_status.fetch("alerts", snapshot=snap) == snap["alerts"]
    assert await platform_status.fetch("teams", snapshot=snap) == snap["teams"]


def test_reliability_counts_zero_failures_when_no_5xx_series_exists():
    # Prometheus returns an empty vector for a sum over absent series; 1 - empty would be empty too.
    q = platform_status.SIGNAL_QUERIES["reliability"]
    assert 'exception_status=~"5.."' in q and "or vector(0)" in q
