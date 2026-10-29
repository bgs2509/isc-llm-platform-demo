# isc-llm-platform-demo

A small private LLM platform: **one gateway in front of one large model, with per-team keys and limits,
dashboards, alerts and a web console that proves the numbers.** It runs on a single GPU machine and is
packaged as a Helm chart for a local `kind` Kubernetes cluster.



## What you get

1. **Team gateway** (LiteLLM): one key per team, parallel and per-minute limits, spend budgets, response
   cache, token and cost accounting.
2. **Observability**: Prometheus (model server, GPU, gateway), 6 alert rules, a 12-panel Grafana dashboard.
3. **Console**: start a load test as any team, watch tokens per second, time to first token, GPU use, KV cache
   and queue update every second, save runs, compare "before" and "after".
4. **RAG agent** in the console: answers about the client firm's public blog (BM25 search) and about the
   running platform (Prometheus), through the gateway as a team, with a 16-question evaluation set.
5. **Runbooks and handover** for operating it, and a **benchmark report** with measured numbers.

## Measured results

On one NVIDIA GB10 with a large Qwen model served by vLLM (details and limits in
[docs/benchmark-report.md](docs/benchmark-report.md)):

1. Output throughput grew **5.2x** when parallel requests grew from 1 to 16 (35.0 -> 180.7 tokens/s).
2. Cost per million output tokens fell **81 %** at the same time (base: 1 request; assumed GPU price 0.20 USD/hour).
3. `nvidia-smi` GPU utilization stayed at 88–91 % in every run, so it cannot show this difference.
4. Team limits worked: a team limited to 2 parallel requests got 2 of 5,969 requests through.
5. RAG agent evaluation (2026-10-29, `docs/measurements/eval.json`): the expected article in the top 3 for
   9 of 10 blog questions, the right tool for 6 of 6 platform questions, 162 of 164 answer claims supported
   by the retrieved text, 8 of 8 expected platform facts stated, answer latency p95 10.3 s, 0.67 USD per
   1,000 questions.
6. Drills (`docs/measurements/`): a deleted gateway pod was ready again after 18 s (17 s without answers);
   the queue alert fired after 69 s of overload and cleared 14 s after it.

## How it fits together

See [docs/architecture.md](docs/architecture.md). The model server (vLLM) runs as a plain container on the
GPU host; everything else runs in the cluster. Two small host helpers in `tools/` connect them.

## Run it

Prerequisites: Docker, a GPU host with an OpenAI-compatible vLLM server, `kind`, `kubectl`, `helm`.

```bash
kind create cluster --config cluster/kind-cluster.yaml
python3 tools/model_forward.py 172.23.0.1 18310 127.0.0.1 18300 &   # relay to the model server
python3 tools/gpu_exporter.py 172.23.0.1 18311 &                    # GPU readings for Prometheus
scripts/install.sh                                                  # build, load images, helm install
```

Then open the console at `http://127.0.0.1:18500` and Grafana at `http://127.0.0.1:18501/grafana/`
(use an SSH tunnel from another computer). Edit `chart/llm-platform/values.yaml` for the model name, the host
address of your cluster network, team limits and prices.

## Publish

`site/build.py` (isc-1) and `site/isc2/build.py` (isc-2) build two static sites from this README, `docs/`
and the measurements into `deploy/origin/`; the pages are tracked in git and reach the web server by
`git pull`. `deploy/` also has the origin container, the reverse-proxy block and the tunnel unit (see
[deploy/README.md](deploy/README.md)).

## Tests

```bash
(cd console && python -m pip install -r requirements-dev.txt && python -m pytest)
python -m pytest site            # links, page rules, tracked pages equal a fresh build
python -m pytest scripts/tests   # measurement summaries
helm lint chart/llm-platform
```

## Layout

```
chart/llm-platform/   Helm chart
console/              console (FastAPI + plain JavaScript), RAG agent, corpus, evaluation set, tests
tools/                host helpers (relay, GPU exporter)
scripts/              install, benchmark, measurements, report and dashboard generators
site/                 site builders (isc-1 in build.py, isc-2 in isc2/)
deploy/               publishing: origin container with the built pages, proxy block, tunnel unit
docs/                 architecture, runbooks, handover, benchmark report, measurements
cluster/              kind cluster configuration
```

## Honest limits

One node and one model; the model runs outside Kubernetes, so GPU scheduling by Kubernetes is not shown;
benchmark numbers are one 30-second run per setting on a shared GPU; chargeback rates and GPU price are
demo values. See [docs/handover.md](docs/handover.md).
