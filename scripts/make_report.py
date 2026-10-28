#!/usr/bin/env python3
"""Build docs/benchmark-report.md from docs/benchmark-results.json (all numbers are computed here).

Usage: scripts/make_report.py [results.json] [report.md]
"""
import json
import sys

src = sys.argv[1] if len(sys.argv) > 1 else "docs/benchmark-results.json"
dst = sys.argv[2] if len(sys.argv) > 2 else "docs/benchmark-report.md"
data = json.load(open(src, encoding="utf8"))
runs = {r["name"]: r for r in data["runs"]}
sweep = [runs[f"baseline c={c}"] for c in (1, 2, 4, 8, 16)]
cache = runs["gateway cache, repeated prompts, c=8"]
limit = runs["team limit, operations, c=8"]


def f(x, d=1):
    return "–" if x is None else f"{x:.{d}f}"


base = sweep[0]["summary"]
rows = []
for r in sweep:
    s, p = r["summary"], r["params"]
    c = p["concurrency"]
    errs = ", ".join(f"{k}×{v}" for k, v in s["errors"].items()) or "0"
    rows.append(
        f"| {c} | {s['ok']} | {errs} | {f(s['tokens_per_second'])} | "
        f"{s['tokens_per_second'] / base['tokens_per_second']:.1f}× | {f(s['tokens_per_second'] / c)} | "
        f"{f(s['ttft_p50_s'], 2)} / {f(s['ttft_p95_s'], 2)} | {f(s['latency_p95_s'])} | "
        f"{f(s['gpu_util_avg'], 0)} | {f(s['usd_per_million_tokens'], 2)} |")

top = sweep[-1]["summary"]
mid = sweep[3]["summary"]
gpu_vals = [r["summary"]["gpu_util_avg"] for r in sweep]
price = sweep[0]["params"]["gpu_usd_per_hour"]
cs, ls = cache["summary"], limit["summary"]
cost_drop = (1 - top["usd_per_million_tokens"] / base["usd_per_million_tokens"]) * 100
refused_cache = sum(cs["errors"].values())
refused_limit = sum(ls["errors"].values())

text = f"""# Benchmark report

Generated {data['generated_at']} by `scripts/make_report.py` from `docs/benchmark-results.json`.

## What was measured

One large model (a Qwen3.8 Flash Next build, served by vLLM on one NVIDIA GB10 GPU with unified memory)
shared by several teams through the gateway. Each run lasts {sweep[0]['params']['duration_s']} seconds;
every request is a streamed chat completion with a unique prompt of about
{sweep[0]['params']['prompt_words']} words and a limit of {sweep[0]['params']['max_tokens']} output tokens;
the load generator keeps a fixed number of requests in flight ("concurrency"). Requests go through the
gateway with a team key, so the numbers include the gateway.

Measured per run: output tokens per second (completed tokens divided by run time), time to first token
(p50 and p95), request latency (p95), GPU utilization from `nvidia-smi` (average over the run), and the cost
per 1 million output tokens, computed as GPU price per hour ÷ (tokens per second × 3600) × 1,000,000 with an
assumed GPU price of **{price:.2f} USD per hour** (a demo assumption, editable in the console).

## Result 1: more parallel requests, much cheaper tokens

| Concurrency | OK requests | Refused | Output tokens/s | vs concurrency 1 | Tokens/s per request | TTFT p50 / p95, s | Latency p95, s | GPU util avg, % | USD per 1M tokens |
|---|---|---|---|---|---|---|---|---|---|
""" + "\n".join(rows) + f"""

1. **Throughput grows {top['tokens_per_second'] / base['tokens_per_second']:.1f}×** when concurrency grows from 1 to 16
   ({f(base['tokens_per_second'])} → {f(top['tokens_per_second'])} output tokens/s). The server batches
   parallel requests, so each extra request adds output at little extra cost.
2. **Cost per million output tokens falls by {cost_drop:.0f} %** ({f(base['usd_per_million_tokens'], 2)} → {f(top['usd_per_million_tokens'], 2)} USD;
   base: concurrency 1, price assumption above).
3. **The price is latency.** Time to first token p95 rises from {f(base['ttft_p95_s'], 2)} to {f(top['ttft_p95_s'], 2)} s
   and each stream slows from {f(base['tokens_per_second'])} to {f(top['tokens_per_second'] / 16)} tokens/s.
4. **GPU utilization does not show any of this.** It stays between {min(gpu_vals):.0f} and {max(gpu_vals):.0f} %
   in every run, because `nvidia-smi` reports the "percent of time over the past sample period during which one or more
   kernels was executing on the GPU" (its own field description). One stream already keeps the GPU "busy";
   tokens per second and cost per million tokens separate good use from poor use.
5. **The ceiling is the server's slot count.** The model server runs at most 16 requests at once (observed
   setting `--max-num-seqs 16`). At concurrency 16 the queue starts to show in time to first token.

## Result 2: what the gateway adds

| Scenario | Requests sent | OK | Refused (429) | Cache hits | TTFT p95, s | Output tokens/s |
|---|---|---|---|---|---|---|
| Repeated prompts, team *research* (600 requests per minute limit), concurrency 8 | {cs['requests']} | {cs['ok']} | {refused_cache} | {cs['cache_hits']} | {f(cs['ttft_p95_s'], 2)} | {f(cs['tokens_per_second'])} |
| Unique prompts, team *operations* (2 parallel, 30 requests per minute), concurrency 8 | {ls['requests']} | {ls['ok']} | {refused_limit} | {ls['cache_hits']} | {f(ls['ttft_p95_s'], 2)} | {f(ls['tokens_per_second'])} |

1. **Response cache.** With 8 distinct prompts repeated, {cs['cache_hits']} of {cs['ok']} OK answers came from the gateway
   cache with time to first token p95 of {f(cs['ttft_p95_s'], 2)} s, and the model did no work for them. The
   tokens-per-second figure of that run counts cached tokens, so it is not GPU throughput.
   The team's per-minute limit then refused {refused_cache} requests; the gateway's counting window was not investigated.
2. **Team limits protect the model.** The *operations* team, limited to 2 parallel requests and 30 per minute,
   had {ls['ok']} of {ls['requests']} requests served; the rest were refused immediately, so one team cannot take
   all model slots from the others.
3. **A limit equal to the load refuses a few requests.** In the concurrency-16 run, {sweep[-1]['summary']['errors'].get('429', 0)} of
   {sweep[-1]['summary']['requests']} requests were refused with 429 because the *research* team's parallel limit is 16,
   the same as the load. Set team limits with some headroom above the planned concurrency.

## Sizing hints

1. For interactive use with p95 time to first token under 1 second, plan for about **4 parallel requests**
   ({f(sweep[2]['summary']['ttft_p95_s'], 2)} s at concurrency 4; {f(mid['ttft_p95_s'], 2)} s at 8).
2. At concurrency 8 the model completed {f(mid['requests_per_second'], 2)} answers of up to
   {sweep[0]['params']['max_tokens']} tokens per second, about {mid['requests_per_second'] * 3600:.0f} answers per hour.
3. A batch workload with no latency target should run near the slot ceiling (16): the cheapest tokens.

## Limits of these numbers

1. One {sweep[0]['params']['duration_s']}-second run per setting; the spread between repeated runs was not measured.
2. Every answer reached the {sweep[0]['params']['max_tokens']}-token limit, so the numbers describe long answers;
   short answers shift the balance toward time to first token.
3. The GPU is shared with other work on the host; GPU utilization is a whole-GPU reading.
4. The GPU price is an assumption; the cost figures scale linearly with it.
5. The response-cache run measures the gateway, not the model.

## Reproduce

`scripts/benchmark.py` runs the sweep through the console API (the same API the web page uses) and writes
`docs/benchmark-results.json`; `scripts/make_report.py` rebuilds this report.
"""
open(dst, "w", encoding="utf8").write(text)
print("written", dst, len(text), "characters")
