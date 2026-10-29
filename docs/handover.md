# Handover

What the customer team receives and how to run it.

## Delivered

1. **Helm chart** `chart/llm-platform` — gateway (LiteLLM) with Postgres, Prometheus with 6 alert rules,
   Grafana with a 12-panel dashboard, the load-test console, and a job that creates the team keys.
2. **Host helpers** in `tools/` — a relay from the cluster network to the model server and an `nvidia-smi` exporter.
3. **Console** `console/` — load tests, live charts, saved runs, before/after comparison, the RAG agent
   (`POST /api/agent/ask`), its evaluation (`/api/agent/eval`, `/metrics`) and the status API used by the
   sites (`/api/status`); 67 unit tests.
4. **Runbooks** `docs/runbooks/` — five procedures for the five alert groups and for upgrades.
5. **Benchmark report** `docs/benchmark-report.md` — measured throughput, latency and cost per million tokens.
6. **Measurements** `docs/measurements/` — KV cache sweep, gateway pod drill, budget and rate-limit drill,
   alert drill, Helm history, latest evaluation; written by `scripts/measure.py`.
7. **Architecture** `docs/architecture.md` — components, decisions, what changes at scale.
8. **Two demo sites** — isc-1 (`site/build.py`) and isc-2 (`site/isc2/build.py`), built pages in
   `deploy/origin/`; publishing in `deploy/README.md`.

## Access

| What | Where |
|---|---|
| Console | `http://127.0.0.1:18500` on the host (SSH tunnel from elsewhere) |
| Grafana | `http://127.0.0.1:18501/grafana/`, dashboard "LLM platform" |
| Team keys | Secret `llm-platform-secrets`, entries `key-research`, `key-engineering`, `key-operations` |
| Gateway admin | master key in the same Secret, entry `masterKey` |

## Operating

1. Install or update: `scripts/install.sh` (builds the console image, loads images, runs `helm upgrade --install`).
2. Check health: `kubectl -n llm-platform get pods`; Prometheus targets `vllm`, `gpu`, `gateway`, `console`
   must be `up` (also `curl http://127.0.0.1:18500/api/status?view=health`).
3. Alerts: see `docs/runbooks/` (each alert annotation names its runbook). Alerts are evaluated by Prometheus;
   routing them to a pager needs Alertmanager, which is not included.
4. Host processes (`tools/model_forward.py`, `tools/gpu_exporter.py`) do not start after a reboot of the host.
5. Run the evaluation (about 2 minutes, 16 questions plus one judge call each, as the team research):
   `curl -X POST http://127.0.0.1:18500/api/agent/eval -H 'Content-Type: application/json'
   -d '{"tenant": "research"}'`, then `GET /api/agent/eval`; Grafana row "RAG agent" shows the scores.
6. Re-measure for the sites (GPU load in total about 7 minutes, the gateway pod is deleted once):
   `scripts/measure.py kv|gateway|budget|alert|helm|eval` on the GPU host; each step prints its load first.
7. Rebuild the sites after a change of a document or a measurement: `python site/build.py` (isc-1) and
   `python site/isc2/build.py` (isc-2; runs all tests first and stops on a failure); commit the pages,
   push, then on the web server `git pull --ff-only` and recreate the origin container
   (`deploy/README.md`). `python -m pytest site` fails while tracked pages differ from a fresh build.

## Who owns what

1. The model server and the GPU host belong to the host owner; the platform only reads its metrics and calls its API.
2. Team limits and budgets belong to the platform operator (`values.yaml`, gateway admin API).
3. Dashboards and alert rules belong to the platform operator.

## Known limits

1. One node, one model, one gateway replica; the response cache is in memory.
2. The model runs outside Kubernetes, so GPU scheduling is not demonstrated (see architecture, decision 1).
3. Priority scheduling is not enabled on the model server.
4. Benchmark numbers come from one run per setting on a shared GPU.
5. Demo chargeback rates and GPU price are placeholders.
6. The evaluation judge is the model under test; the 16 questions were written by us from the corpus.

## Next steps for a real customer

1. Move the model server into the cluster with the NVIDIA device plugin; add nodes.
2. Add Alertmanager and single sign-on; keep keys in the customer's secret store.
3. Re-run `scripts/benchmark.py` on the customer's hardware and set team limits from the results.
