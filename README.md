# isc-llm-platform-demo

A small private LLM platform: **one gateway in front of one large model, with per-team keys and limits,
dashboards, alerts and a web console that proves the numbers.** One GPU machine, a Helm chart, a local
`kind` cluster.

```
 Teams (one key each)
 [research]    [engineering]    [operations]
        \            |             /
         v           v            v
   +--------------------------------------------+
   | Gateway (LiteLLM): keys, budgets, limits,  |
   | cache, token and cost accounting           |
   +------------------+-------------------------+
                      v
          Relay (host) -> vLLM server (GPU host)
                      |
   +------------------+------------------+
   v                                     v
 Prometheus  <----  nvidia-smi exporter (host)
   |   alert rules (6)
   v
 Grafana dashboard        Console: load tests, live charts, RAG agent
```

## What it is made of

1. **Gateway** (LiteLLM): per-team keys, parallel and per-minute limits, budgets, cache, cost accounting.
2. **Observability**: Prometheus, 6 alert rules, a 12-panel Grafana dashboard.
3. **Console**: load tests as any team, live tokens per second, time to first token, GPU and queue.
4. **RAG agent**: answers about the client firm's public blog and the running platform.
5. **Docs**: [architecture](docs/architecture.md), [benchmark report](docs/benchmark-report.md),
   [handover and limits](docs/handover.md), [publishing](deploy/README.md).

## Key numbers

On one NVIDIA GB10 with a Qwen model on vLLM ([details](docs/benchmark-report.md)):

1. Output throughput **5.2x** from 1 to 16 parallel requests (35.0 -> 180.7 tokens/s).
2. Cost per million output tokens **-81 %** at 16 parallel requests (base: 1 request).
3. Team limits hold: a team limited to 2 parallel requests got 2 of 5,969 requests through.

## Run it

```bash
kind create cluster --config cluster/kind-cluster.yaml
python3 tools/model_forward.py 172.23.0.1 18310 127.0.0.1 18300 &   # relay to the model server
python3 tools/gpu_exporter.py 172.23.0.1 18311 &                    # GPU readings for Prometheus
scripts/install.sh                                                  # build, load images, helm install
```

Console: `http://127.0.0.1:18500`, Grafana: `http://127.0.0.1:18501/grafana/`.

## Layout

```
chart/llm-platform/   Helm chart
console/              console, RAG agent, corpus, evaluation set, tests
tools/                host helpers (relay, GPU exporter)
scripts/              install, benchmark, measurements, generators
site/                 static site builders
deploy/               publishing
docs/                 architecture, runbooks, handover, benchmark report, measurements
cluster/              kind cluster configuration
```
