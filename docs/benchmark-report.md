# Benchmark report

Generated 2026-10-28 21:10:20 by `scripts/make_report.py` from `docs/benchmark-results.json`.

## What was measured

One large model (qwen38-flash-next-125B, served by vLLM on one NVIDIA GB10 (DGX Spark 128G) GPU with unified memory)
shared by several teams through the gateway. Each run lasts 30 seconds;
every request is a streamed chat completion with a unique prompt of about
60 words and a limit of 128 output tokens;
the load generator keeps a fixed number of requests in flight ("concurrency"). Requests go through the
gateway with a team key, so the numbers include the gateway.

Measured per run: output tokens per second (completed tokens divided by run time), time to first token
(p50 and p95), request latency (p95), GPU utilization from `nvidia-smi` (average over the run), and the cost
per 1 million output tokens, computed as GPU price per hour / (tokens per second x 3600) x 1,000,000 with an
assumed GPU price of **0.20 USD per hour** (a demo assumption, editable in the console).

## Result 1: more parallel requests, much cheaper tokens

| Concurrency | OK requests | Refused | Output tokens/s | vs concurrency 1 | Tokens/s per request | TTFT p50 / p95, s | Latency p95, s | GPU util avg, % | USD per 1M tokens |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 9 | 0 | 35.0 | 1.0x | 35.0 | 0.36 / 0.36 | 3.9 | 89 | 1.59 |
| 2 | 14 | 0 | 55.5 | 1.6x | 27.8 | 0.45 / 0.64 | 5.1 | 91 | 1.00 |
| 4 | 23 | 0 | 86.2 | 2.5x | 21.5 | 0.52 / 0.77 | 6.8 | 88 | 0.64 |
| 8 | 32 | 0 | 128.0 | 3.7x | 16.0 | 0.82 / 1.18 | 9.0 | 90 | 0.43 |
| 16 | 49 | 429x3 | 180.7 | 5.2x | 11.3 | 1.14 / 2.82 | 12.0 | 90 | 0.31 |

1. **Throughput grows 5.2x** when concurrency grows from 1 to 16
   (35.0 -> 180.7 output tokens/s). The server batches
   parallel requests, so each extra request adds output at little extra cost.
2. **Cost per million output tokens falls by 81 %** (1.59 -> 0.31 USD;
   base: concurrency 1, price assumption above).
3. **The price is latency.** Time to first token p95 rises from 0.36 to 2.82 s
   and each stream slows from 35.0 to 11.3 tokens/s.
4. **GPU utilization does not show any of this.** It stays between 88 and 91 %
   in every run, because `nvidia-smi` reports the "percent of time over the past sample period during which one or more
   kernels was executing on the GPU" (its own field description). One stream already keeps the GPU "busy";
   tokens per second and cost per million tokens separate good use from poor use.
5. **The ceiling is the server's slot count.** The model server runs at most 16 requests at once (observed
   setting `--max-num-seqs 16`). At concurrency 16 the queue starts to show in time to first token.

## Result 2: what the gateway adds

| Scenario | Requests sent | OK | Refused (429) | Cache hits | TTFT p95, s | Output tokens/s |
|---|---|---|---|---|---|---|
| Repeated prompts, team *research* (600 requests per minute limit), concurrency 8 | 2844 | 1148 | 1696 | 1133 | 0.04 | 4210.9 |
| Unique prompts, team *operations* (2 parallel, 30 requests per minute), concurrency 8 | 5969 | 2 | 5967 | 0 | 0.72 | 12.8 |

1. **Response cache.** With 8 distinct prompts repeated, 1133 of 1148 OK answers came from the gateway
   cache with time to first token p95 of 0.04 s, and the model did no work for them. The
   tokens-per-second figure of that run counts cached tokens, so it is not GPU throughput.
   The team's per-minute limit then refused 1696 requests; the gateway's counting window was not investigated.
2. **Team limits protect the model.** The *operations* team, limited to 2 parallel requests and 30 per minute,
   had 2 of 5969 requests served; the rest were refused immediately, so one team cannot take
   all model slots from the others.
3. **A limit equal to the load refuses a few requests.** In the concurrency-16 run, 3 of
   52 requests were refused with 429 because the *research* team's parallel limit is 16,
   the same as the load. Set team limits with some headroom above the planned concurrency.

## Sizing hints

1. For interactive use with p95 time to first token under 1 second, plan for about **4 parallel requests**
   (0.77 s at concurrency 4; 1.18 s at 8).
2. At concurrency 8 the model completed 1.00 answers of up to
   128 tokens per second, about 3600 answers per hour.
3. A batch workload with no latency target should run near the slot ceiling (16): the cheapest tokens.

## Limits of these numbers

1. One 30-second run per setting; the spread between repeated runs was not measured.
2. Every answer reached the 128-token limit, so the numbers describe long answers;
   short answers shift the balance toward time to first token.
3. The GPU is shared with other work on the host; GPU utilization is a whole-GPU reading.
4. The GPU price is an assumption; the cost figures scale linearly with it.
5. The response-cache run measures the gateway, not the model.

## Reproduce

`scripts/benchmark.py` runs the sweep through the console API (the same API the web page uses) and writes
`docs/benchmark-results.json`; `scripts/make_report.py` rebuilds this report.
