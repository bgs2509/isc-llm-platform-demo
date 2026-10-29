# isc-llm-platform-demo

`project_type: dev`

A small private LLM platform: a team gateway, observability and a load-test console in front of an
existing OpenAI-compatible model server (vLLM). Packaged as a Helm chart, run on one machine with `kind`.

## Layout

- `chart/llm-platform/` — Helm chart (gateway, Postgres, Prometheus, Grafana, console, bootstrap job)
- `console/` — web console (FastAPI + plain JavaScript), tests in `console/tests/`
- `tools/` — host-side helpers (`model_forward.py` relay, `gpu_exporter.py`)
- `scripts/` — `install.sh`, `benchmark.py`, `make_dashboard.py`, `make_report.py`
- `docs/` — architecture, runbooks, handover, benchmark report

## Commands

- Tests: `cd console && python -m pytest`
- Chart checks: `helm lint chart/llm-platform`
- Install: `scripts/install.sh`
