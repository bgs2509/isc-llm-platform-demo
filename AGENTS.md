# isc-llm-platform-demo

`project_type: dev`

A small private LLM platform: a team gateway, observability and a load-test console in front of an
existing OpenAI-compatible model server (vLLM). Packaged as a Helm chart, run on one machine with `kind`.

## Layout

- `chart/llm-platform/` — Helm chart (gateway, Postgres, Prometheus, Grafana, console, bootstrap job)
- `console/` — web console (FastAPI + plain JavaScript), tests in `console/tests/`
- `tools/` — host-side helpers (`model_forward.py` relay, `gpu_exporter.py`)
- `scripts/` — `install.sh`, `benchmark.py`, `make_dashboard.py`, `make_report.py`
- `site/` — static site builder (`build.py`) and its link test
- `deploy/` — publishing: origin container, portal proxy block, reverse tunnel unit (`deploy/README.md`)
- `docs/` — architecture, runbooks, handover, benchmark report; `docs/superpowers/` — designs and plans
- `corpus/` — raw HTML of the blog corpus (git-ignored)

## Commands

- Tests: `cd console && python -m pytest`; site links: `python -m pytest site`
- Chart checks: `helm lint chart/llm-platform`
- Install: `scripts/install.sh`
