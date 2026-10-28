"""Pure helpers: percentiles, cost arithmetic, Prometheus text parsing, run summaries."""
from __future__ import annotations

import math
import re
from dataclasses import dataclass


def percentile(values: list[float], p: float) -> float | None:
    """Percentile with linear interpolation, p in [0, 100]; None for an empty list."""
    if not values:
        return None
    xs = sorted(values)
    if len(xs) == 1:
        return xs[0]
    k = (len(xs) - 1) * p / 100.0
    lo, hi = math.floor(k), math.ceil(k)
    if lo == hi:
        return xs[int(k)]
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


def cost_per_million_tokens(gpu_usd_per_hour: float, tokens_per_second: float | None) -> float | None:
    """USD per 1 million output tokens when the GPU is paid by the hour; None without throughput."""
    if not tokens_per_second or tokens_per_second <= 0:
        return None
    return gpu_usd_per_hour / (tokens_per_second * 3600.0) * 1_000_000.0


_LINE = re.compile(r"^([a-zA-Z_:][a-zA-Z0-9_:]*)(\{[^}]*\})?\s+(\S+)\s*$")


def parse_prometheus_text(text: str) -> dict[str, float]:
    """Sum sample values per metric name (labels ignored); skips comments, NaN and Inf."""
    out: dict[str, float] = {}
    for line in text.splitlines():
        if not line or line.startswith("#"):
            continue
        m = _LINE.match(line)
        if not m:
            continue
        try:
            value = float(m.group(3))
        except ValueError:
            continue
        if math.isnan(value) or math.isinf(value):
            continue
        out[m.group(1)] = out.get(m.group(1), 0.0) + value
    return out


@dataclass
class RequestResult:
    ok: bool
    status: int
    total_s: float
    ttft_s: float | None = None
    completion_tokens: int = 0
    cached: bool = False


def summarize(results: list[RequestResult], duration_s: float, gpu_util: list[float],
              gpu_usd_per_hour: float) -> dict:
    """Aggregate one load-test run into the numbers shown in the console and the report."""
    ok = [r for r in results if r.ok]
    errors: dict[str, int] = {}
    for r in results:
        if not r.ok:
            errors[str(r.status)] = errors.get(str(r.status), 0) + 1
    tokens = sum(r.completion_tokens for r in ok)
    tps = tokens / duration_s if duration_s > 0 else None
    ttft = [r.ttft_s for r in ok if r.ttft_s is not None]
    latency = [r.total_s for r in ok]
    return {
        "requests": len(results),
        "ok": len(ok),
        "errors": errors,
        "cache_hits": sum(1 for r in ok if r.cached),
        "completion_tokens": tokens,
        "tokens_per_second": tps,
        "requests_per_second": len(ok) / duration_s if duration_s > 0 else None,
        "ttft_p50_s": percentile(ttft, 50),
        "ttft_p95_s": percentile(ttft, 95),
        "latency_p50_s": percentile(latency, 50),
        "latency_p95_s": percentile(latency, 95),
        "gpu_util_avg": sum(gpu_util) / len(gpu_util) if gpu_util else None,
        "gpu_util_max": max(gpu_util) if gpu_util else None,
        "gpu_usd_per_hour": gpu_usd_per_hour,
        "usd_per_million_tokens": cost_per_million_tokens(gpu_usd_per_hour, tps),
    }
