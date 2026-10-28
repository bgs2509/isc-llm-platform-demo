# Runbook 2: slow answers or a growing queue

**Alerts:** `ModelQueueBuildingUp` (more than 4 requests waiting for 1 minute), `TimeToFirstTokenSlow`
(p95 above 5 seconds for 5 minutes), `GpuUnderusedUnderLoad` (many requests running, GPU mostly idle).

## Meaning

The model serves a fixed number of requests at once (its `--max-num-seqs` setting). Extra requests wait,
and time to first token grows with the wait.

## Check

1. Grafana dashboard "LLM platform": panel "Requests on the model" (running against waiting) and
   "Time to first token".
2. Who sends the load: panels "Gateway requests per second by team" and "Tokens per second by team".
3. Long answers: a team with a high `max_tokens` holds a slot longer.

## Fix

1. One team floods the model: lower its parallel limit or per-minute limit at the gateway (runbook 4).
2. Many long answers: ask the team to lower `max_tokens`, or lower the team's budget.
3. Steady overload from all teams: the model needs more capacity (a second replica or a larger server); use
   the benchmark report to size it.
4. `GpuUnderusedUnderLoad` with slow answers points to a bottleneck outside the GPU (gateway or network):
   check gateway pod CPU and the latency panel.

## Verify

Waiting requests return to 0, p95 time to first token drops below 5 seconds, alerts resolve.
