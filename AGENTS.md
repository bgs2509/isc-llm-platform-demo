# isc-llm-platform-demo

`project_type: dev`

A small private LLM platform: a team gateway, observability and a load-test console in front of an
existing OpenAI-compatible model server (vLLM). Packaged as a Helm chart, run on one machine with `kind`.

## Layout

- `chart/llm-platform/` — Helm chart (gateway, Postgres, Prometheus, Grafana, console, bootstrap job)
- `console/` — web console (FastAPI + plain JavaScript), RAG agent, tests in `console/tests/`;
  `console/corpus/blog/` — the 36 blog articles (tracked); `console/eval/` — the evaluation set
- `tools/` — host-side helpers (`model_forward.py` relay, `gpu_exporter.py`)
- `scripts/` — `install.sh`, `benchmark.py`, `measure.py`, `build_blog_corpus.py`, `make_dashboard.py`,
  `make_report.py`; tests in `scripts/tests/`
- `site/` — isc-1 builder (`build.py`), isc-2 builder, templates and static files (`site/isc2/`), tests
- `deploy/` — publishing: origin container with the built pages (`deploy/origin/site`, `site-isc2`, tracked),
  portal proxy block, reverse tunnel unit (`deploy/README.md`)
- `docs/` — architecture, runbooks, handover, benchmark report; `docs/measurements/` — drill and evaluation
  results; `docs/superpowers/` — designs and plans
- `corpus/` — raw HTML of the blog corpus (git-ignored)

## Commands

- Tests: `cd console && python -m pytest`; sites: `python -m pytest site`; scripts: `python -m pytest scripts/tests`
- Rebuild sites: `python site/build.py`, `python site/isc2/build.py` (then commit the pages)
- Chart checks: `helm lint chart/llm-platform`
- Install: `scripts/install.sh`
