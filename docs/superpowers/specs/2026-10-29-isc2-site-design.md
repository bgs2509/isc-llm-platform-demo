---
feature: isc2-site
risk: medium
risk_reason: "new static site and two small console routes; one more site block in the shared portal proxy; no DB, no auth model change (the whole site behind the existing login)"
open_questions: []
approved: "2026-10-29, owner, in session: home = 6 interactive widgets (variant 4, live data, whole site behind the reviewer login); pages 1-6 as below"
---

# isc-2 site — design

## Rules for every page

1. English only: no character outside ASCII and typographic punctuation in any built page (checked by a test).
2. Bullets with keywords, no prose paragraphs; numbers carry units; percentages name their base.
3. Every page follows the client's own case format: Challenge -> Solution -> Results, then Trade-offs,
   What I'd change at scale, Links. Every link to another page or tool opens in a new tab.
4. Live data comes only from the console under the same origin (`/console/api/...`); the browser never talks to
   Prometheus or Kubernetes. Without load a widget shows the latest saved run (with its date); before the first
   run it shows the measurement baked in at build time.
5. The whole site is behind HTTP basic auth (login `reviewer`); the console and Grafana have no second login.

## Home page

Six widgets, one per mandatory requirement of the role; each widget shows its live or latest number and opens
its page in a new tab.

## Page 1 — LLM inference on GPU (vLLM)

- Requirement keywords: vLLM, GPU, latency, throughput, concurrency, KV cache.
- Interactive: concurrency slider 1 -> 16 (tokens/s, time to first token p95, cost per 1M tokens, the knee).
- New measurement: KV cache and queue against prompt length and concurrency (console timeline gains
  `kv_cache_pct` and `vllm_waiting`).
- Live strip: running of 16 slots, waiting, KV cache %, tokens/s, GPU %.

## Page 2 — GPU infrastructure, Kubernetes, operations

- Interactive two-host diagram (GPU host: model, relay, kind cluster with its pods and volumes; web server:
  proxy, origin; reverse tunnel); click -> what, why, failure mode, runbook.
- Live: dependency health (model, GPU exporter, gateway, Prometheus, console) through the console.
- Snapshot at build: Helm release history (8 revisions, 1 failed and fixed in 30 s).
- New measurement: gateway pod deleted during a load run -> seconds to ready, failed requests N of M.

## Page 3 — AI gateway (LiteLLM)

- Six items: tenant keys, quotas (daily budget), rate limits (rpm and parallel), cache, usage, cost.
- Interactive: request journey (key -> limits and budget -> cache -> accounting); team switcher with live
  requests/s, tokens/s, spend.
- Measurements: parallel limit (2 of 5,969), cache (1,133 of 1,148), new: budget and rpm drill on a temporary key.
- Fallback and model pools: "What I'd change at scale" (no GPU memory for a second model on this host).

## Page 4 — RAG, agent, evaluation, API

- Ask the agent: question -> tool steps -> answer with sources (blog article URLs).
- Evaluation board: five scores, 16 expandable rows, run date.
- Decision backed by the eval set: hit@3 of structure-aware chunking against fixed windows.
- API: one `curl` example and the response shape.

## Page 5 — Observability

- Signal map: reliability, latency, usage, errors, cost — live number, 15-minute sparkline, click -> metric,
  panel, alert rule, runbook.
- Six alert rules with live state.
- New measurement: `ModelQueueBuildingUp` fired under load and resolved -> seconds to fire, seconds to resolve.
- OpenTelemetry: named as the next step (gateway `otel` callback).

## Page 6 — Debugging, delivery, stakeholders

- Six incident cards from this build (Symptom, Evidence, Root cause, Fix, Prevention), filter by layer.
- Constraints and stakeholders by role only (GPU host owner, portal team, network admin) — no names, no hosts.
- Delivery checklist with numbers (tests, runbooks, releases, one-command install).
