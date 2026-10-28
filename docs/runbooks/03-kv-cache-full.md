# Runbook 3: KV cache nearly full

**Alert:** `KvCacheNearlyFull` (`vllm:kv_cache_usage_perc` above 0.9 for 2 minutes).
**Impact:** the server cannot start new requests until memory frees up; queue and latency rise.

## Meaning

The KV cache holds the processed text of running requests. Long prompts and long answers fill it; many
parallel requests fill it faster.

## Check

1. Dashboard panel "KV cache used" next to "Requests on the model".
2. Which teams send long requests: compare "Tokens per second by team".

## Fix

1. Lower the parallel limit of the heavy team at the gateway, or ask it to shorten prompts and `max_tokens`.
2. If the pressure is normal for the workload, the owner of the model server can change engine settings
   (context length, number of parallel sequences, cache memory share). This restarts the model; plan it.

## Verify

KV cache usage stays below 80 % under the usual load; the alert resolves.
