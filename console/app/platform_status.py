"""API to the running platform: answers the status views from Prometheus or from a recorded snapshot.

PURPOSE: answer `alerts`, `teams`, `signals` and `health` from Prometheus, or from a recorded snapshot
    in evaluation.
INPUTS: `view` in {"alerts", "teams", "signals", "health"}; a Prometheus base URL, or a snapshot dict
    with the same keys.
OUTPUTS:
    alerts  -> [{"name", "state": "firing"|"pending"|"inactive", "query", "value": float|None}],
               value = the left side of `<expr> <op> <number>` evaluated now, None for other rule shapes;
    teams   -> [{"team", "requests_per_s", "tokens_per_s"}] over 5 minutes;
    signals -> {"reliability"|"latency"|"usage"|"errors"|"cost": {"value": float|None,
               "series": [[unix_s, float|None], ...]}}, 15 minutes at a 30 s step; reliability and errors
               in percent, latency = TTFT p95 in seconds, usage = tokens/s, cost = USD per 1M output tokens
               computed in Python from usage and GPU_USD_PER_HOUR;
    health  -> {"prometheus": bool, "vllm"|"gpu"|"gateway"|"console": "up"|"down"|"unknown"}.
DEPENDS: `httpx`; Prometheus `/api/v1/rules?type=alert`, `/api/v1/query`, `/api/v1/query_range`;
    `stats.cost_per_million_tokens`, `stats.GPU_USD_PER_HOUR`.
Errors: an unknown `view` returns {"error": ...} to the model (the model's input is untrusted); Prometheus
    unreachable returns {"error": "prometheus unavailable"} (for `health`: prometheus False, every job
    "unknown") - the agent still answers and says so.
Rule: the model never sends PromQL; the team queries are the dashboard's with a 5m window.
"""
from __future__ import annotations

import logging
import math
import re
import time

import httpx

from .stats import GPU_USD_PER_HOUR, cost_per_million_tokens

log = logging.getLogger(__name__)

VIEWS = ("alerts", "teams", "signals", "health")
JOBS = ("vllm", "gpu", "gateway", "console")
RANGE_S, STEP_S = 900, 30

_TOTAL = 'litellm_proxy_total_requests_metric_total'
_FAILED = 'litellm_proxy_failed_requests_metric_total'
_ALIAS = '{api_key_alias!~"None|"}'
TEAM_REQUESTS = f"sum by (api_key_alias) (rate({_TOTAL}{_ALIAS}[5m]))"
TEAM_TOKENS = f'sum by (api_key_alias) (rate(litellm_total_tokens_metric_total{_ALIAS}[5m]))'
_ERR_SHARE = f"sum(rate({_FAILED}[5m])) / clamp_min(sum(rate({_TOTAL}[5m])), 0.001)"
SIGNAL_QUERIES = {
    "reliability": (f'100 * (1 - sum(rate({_FAILED}{{exception_status=~"5.."}}[5m]))'
                    f" / clamp_min(sum(rate({_TOTAL}[5m])), 0.001))"),
    "latency": "histogram_quantile(0.95, sum(rate(vllm:time_to_first_token_seconds_bucket[5m])) by (le))",
    "usage": "sum(rate(vllm:generation_tokens_total[1m]))",
    "errors": f"100 * {_ERR_SHARE}",
}

_COMPARE = re.compile(r"^(?P<left>.+?)\s*(?:>=|<=|==|!=|>|<)\s*-?[\d.]+$")
_LOGIC = re.compile(r"\b(?:and|or|unless)\b")


def _num(raw: object) -> float | None:
    try:
        value = float(raw)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


async def _get(client: httpx.AsyncClient, base: str, path: str, params: dict) -> dict:
    r = await client.get(f"{base}{path}", params=params)
    r.raise_for_status()
    body = r.json()
    if body.get("status") != "success":
        raise ValueError("prometheus answered with an error status")
    return body["data"]


async def _instant(client: httpx.AsyncClient, base: str, query: str) -> list[dict]:
    return (await _get(client, base, "/api/v1/query", {"query": query}))["result"]


def _left_side(expr: str) -> str | None:
    m = _COMPARE.match(expr.strip())
    if not m or _LOGIC.search(m["left"]):
        return None
    return m["left"]


async def _alerts(client: httpx.AsyncClient, base: str) -> list[dict]:
    data = await _get(client, base, "/api/v1/rules", {"type": "alert"})
    rows = []
    for group in data["groups"]:
        for rule in group["rules"]:
            left = _left_side(rule["query"])
            value = None
            if left:
                result = await _instant(client, base, left)
                value = _num(result[0]["value"][1]) if result else None
            rows.append({"name": rule["name"], "state": rule["state"],
                         "query": rule["query"], "value": value})
    return rows


async def _teams(client: httpx.AsyncClient, base: str) -> list[dict]:
    teams: dict[str, dict] = {}
    for field, query in (("requests_per_s", TEAM_REQUESTS), ("tokens_per_s", TEAM_TOKENS)):
        for item in await _instant(client, base, query):
            team = item["metric"].get("api_key_alias", "")
            row = teams.setdefault(team, {"team": team, "requests_per_s": None, "tokens_per_s": None})
            row[field] = _num(item["value"][1])
    return list(teams.values())


async def _series(client: httpx.AsyncClient, base: str, query: str) -> list[list]:
    end = time.time()
    params = {"query": query, "start": end - RANGE_S, "end": end, "step": STEP_S}
    result = (await _get(client, base, "/api/v1/query_range", params))["result"]
    return [[t, _num(v)] for t, v in result[0]["values"]] if result else []


def _signal(series: list[list]) -> dict:
    return {"value": series[-1][1] if series else None, "series": series}


async def _signals(client: httpx.AsyncClient, base: str) -> dict:
    out = {name: _signal(await _series(client, base, q)) for name, q in SIGNAL_QUERIES.items()}
    cost = [[t, cost_per_million_tokens(GPU_USD_PER_HOUR, v)] for t, v in out["usage"]["series"]]
    out["cost"] = _signal(cost)
    return {name: out[name] for name in ("reliability", "latency", "usage", "errors", "cost")}


async def _health(client: httpx.AsyncClient, base: str) -> dict:
    states = {job: "unknown" for job in JOBS}
    try:
        for item in await _instant(client, base, "up"):
            job = item["metric"].get("job")
            if job in states:
                states[job] = "up" if _num(item["value"][1]) == 1.0 else "down"
    except (httpx.HTTPError, ValueError, KeyError, IndexError) as exc:
        log.warning("[PlatformStatus][health][PROM_ERROR] %s", type(exc).__name__)
        return {"prometheus": False, **states}
    return {"prometheus": True, **states}


async def fetch(view: str, base_url: str = "", *, snapshot: dict | None = None,
                client: httpx.AsyncClient | None = None) -> list | dict:
    """Answer one view; never raises for Prometheus problems."""
    if view not in VIEWS:
        return {"error": f"unknown view {view!r}; use one of {', '.join(VIEWS)}"}
    if snapshot is not None:
        return snapshot.get(view, {"error": f"view {view!r} is not in the snapshot"})
    handlers = {"alerts": _alerts, "teams": _teams, "signals": _signals, "health": _health}
    own = client is None
    http = client or httpx.AsyncClient(timeout=3.0)
    try:
        return await handlers[view](http, base_url.rstrip("/"))
    except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError) as exc:
        log.warning("[PlatformStatus][fetch][PROM_ERROR] view=%s %s", view, type(exc).__name__)
        return {"error": "prometheus unavailable"}
    finally:
        if own:
            await http.aclose()
