# Architecture

## Goal

Give several teams controlled access to one large model that runs on one GPU machine, and make cost,
latency and GPU use visible. The platform is a small, runnable copy of what a customer would get:
one gateway in front of the model, per-team keys and limits, dashboards, alerts, and a console to prove
the numbers.

## Components

```
 Teams (one key each)
 [research]    [engineering]    [operations]
        \            |             /
         v           v            v
   +--------------------------------------------+
   | Gateway (LiteLLM): per-team keys, budgets, |
   | parallel and per-minute limits, response   |
   | cache, token and cost accounting           |
   +------------------+-------------------------+
                      |  OpenAI-compatible API
                      v
          Relay (host) -> vLLM server (GPU host)
                      |
    metrics           |            metrics
   +------------------+------------------+
   v                                     v
 Prometheus  <----  nvidia-smi exporter (host)
   |   alert rules (6)
   v
 Grafana dashboard           Console: load tests, live charts, before/after comparison
```

1. **Gateway** (LiteLLM, in the cluster) is the only entry point for teams. It checks the team key, enforces
   limits and a spend budget, caches repeated answers in memory, and counts tokens and cost per team.
   Keys are created by a Helm post-install job; random secrets are generated once and kept across upgrades.
2. **Model server** (vLLM, outside the cluster) serves the model on the GPU. It was already running on the
   host and is used as it is; the platform never restarts or reconfigures it.
3. **Relay and GPU exporter** (host processes, `tools/`) connect the cluster to the host: the model server
   listens only on the host loopback, so a small TCP relay passes traffic from the cluster network, and a
   tiny exporter turns `nvidia-smi` readings into Prometheus metrics.
4. **Prometheus** scrapes the model server, the GPU exporter, the gateway and the console every 5 seconds and
   evaluates the alert rules in `chart/llm-platform/templates/prometheus-config.yaml`.
5. **Grafana** shows one provisioned dashboard (12 panels plus a "RAG agent" row of 5), read-only for
   anonymous viewers.
6. **Console** (FastAPI and a plain JavaScript page) starts load tests through the gateway as a chosen team,
   streams live numbers once a second, saves runs and compares two of them.
7. **RAG agent** (in the console, `console/app/agent.py`) answers one question with two tools chosen by the
   model: `search_docs` (BM25 over 36 articles of the client firm's public blog, `console/app/corpus.py`) and
   `platform_status` (alerts or per-team traffic from Prometheus, `console/app/platform_status.py`). It calls
   the model through the gateway with a team key, so its tokens and spend count per team like any request.
8. **Evaluation set** (`console/eval/`, `console/app/evaluate.py`): 16 questions (10 about the blog, 6 about
   the platform on two recorded Prometheus snapshots); scores hit@3, tool accuracy, faithfulness (claims
   checked by the same model as judge), answer latency p95 and cost per 1,000 questions, exported on
   `/metrics` for Prometheus.
9. **Status API** (`GET /api/status?view=alerts|teams|signals|health`): the only way the two demo sites read
   live platform data; the browser never talks to Prometheus or Kubernetes.
10. **Demo sites**: isc-1 (`site/build.py`, open documents) and isc-2 (`site/isc2/build.py`, six pages, one
    per requirement of the role, whole site behind a login). Both are built into `deploy/origin/` and tracked
    in git; the origin container serves them by host name (`deploy/README.md`).

## Decisions and trade-offs

1. **Kubernetes for everything except the GPU workload.** `kind` runs Kubernetes nodes as Docker
   containers and needs no administrator rights, so it is safe on a shared machine. The kind project lists GPU
   device plugins among things it cannot reasonably test, so the model stays a plain container. On a real
   cluster the model would run as a pod scheduled by the NVIDIA device plugin; only `values.yaml` and one
   template change.
2. **Use the running model as it is.** No second model is started; tests run against the real model.
   Priority scheduling in vLLM needs the server flag `--scheduling-policy priority` (a restart), so it is
   not used; requests from the platform are served first-come, first-served.
3. **Gateway cache is in memory.** Fine for one replica. With several gateway replicas a shared cache (Redis)
   is needed.
4. **GPU utilization is a weak signal.** `nvidia-smi` reports the "percent of time over the past sample period during which one or more
   kernels was executing on the GPU", so a single stream already shows a high value. Throughput (tokens per second) and cost per million tokens are
   the numbers that separate good and bad use; see `docs/benchmark-report.md`.
5. **Costs are arithmetic, not billing.** The cost per million tokens in the console is the GPU price per hour
   divided by the measured tokens per hour; the price is an assumption the user can edit. The gateway's
   per-team spend uses fixed chargeback rates from `values.yaml`.
6. **BM25 instead of embeddings.** No second model fits in GPU memory next to the served one, so retrieval is
   lexical (standard library, no vector store). Chunking follows the kind of text (a case study stays whole,
   a long article splits by section); on the 10 blog questions it found the expected article in the top 3
   for 9 of 10, the same as fixed 250-word windows (`docs/measurements/eval.json`).
7. **The evaluation bypasses the gateway cache.** The cache key ignores `chat_template_kwargs`, and a repeated
   question would come back in 0.02 s; evaluation requests send `cache: {"no-cache": true}` so latency and
   cost are measured, while questions asked on the site may use the cache.

## Security notes

1. Console and Grafana ports are published on the host loopback only (`127.0.0.1`); use an SSH tunnel.
2. Team keys, the gateway master key and passwords live in one Kubernetes Secret (`llm-platform-secrets`).
3. The relay passes bytes and does not read or store prompts.

## What changes at customer scale

1. Several nodes, GPU scheduling by the device plugin or GPU Operator, and gateway replicas with a shared cache.
2. Alertmanager (or the customer's paging tool) behind the existing alert rules.
3. Single sign-on in front of the console and Grafana; keys in the customer's secret store.
4. Per-team quotas tuned from the benchmark report instead of the demo values.
5. Fallback to a second model and model pools per team (needs GPU memory for a second model).
6. Dense retrieval through an embedding model behind the same gateway; a judge from another model family.
7. OpenTelemetry traces from the gateway (its `otel` callback) to follow one request across services.
