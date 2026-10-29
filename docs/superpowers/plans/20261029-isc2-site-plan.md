# isc-2 site — implementation plan

Status (2026-10-29): page contents approved (design file); plan NOT yet approved. Static mockups of the home
page and the 6 pages (placeholders, no real data) are in `docs/superpowers/mockups/isc2/`, awaiting owner
approval; then a detailed execution plan. No task started.

Design: `docs/superpowers/specs/2026-10-29-isc2-site-design.md`. Depends on the RAG agent plan
(`docs/superpowers/plans/20261029-rag-agent-plan.md`), which runs first. Tests: `cd console && python -m pytest`,
`python -m pytest site`, `helm lint chart/llm-platform`.

## Phase A — RAG agent (the RAG plan, phases 0-5) with two additions

A.1 `corpus.py`: a fixed-window chunker (about 250 words, used only by the comparison) and a test that both
    chunkers cover every word of an article.
A.2 `evaluate.py`: `chunking_comparison()` -> hit@3 of both chunkers on the 10 blog questions (search only, no
    model); saved with the evaluation result.

## Phase B — console additions (TDD)

B.1 Run timeline gains `kv_cache_pct` and `vllm_waiting` (`runner.py`); test on one tick.
B.2 `platform_status` gains two views: `signals` (one number per page-5 tile plus a 15-minute series) and
    `health` (`up` of model, GPU exporter, gateway, console, and Prometheus itself); tests with a fake HTTP
    transport.
B.3 Route `GET /api/status?view=alerts|teams|signals|health` (unknown view 422); the browser uses only this.

## Phase C — measurements (scripts in `scripts/`, results in `docs/measurements/*.json`, tracked)

C.1 KV sweep: 5 runs of 30 s (prompt 200 -> 2,000 words, concurrency 4 -> 16) through the console API.
C.2 Gateway pod drill: 60 s run at concurrency 8, delete the `litellm` pod at 20 s; record seconds to ready,
    failed requests, throughput recovery.
C.3 Budget and rpm drill: temporary key (budget 0.001 USD, 5 rpm), requests until refusal, spend recorded vs
    computed; the key is deleted afterwards.
C.4 Alert drill: about 24 parallel requests for about 2 minutes; record when `ModelQueueBuildingUp` fires and
    resolves (Prometheus `ALERTS` series).
C.5 Snapshot of `helm history` for page 2.
Every script prints what it will load and for how long before it starts; GPU load in total about 7 minutes.

## Phase D — site builder `site/isc2/`

D.1 `site/isc2/build.py`: home + 6 pages from the measurement JSON files and the benchmark results; plain HTML,
    CSS and JavaScript, no external scripts; every link to another page or tool has `target="_blank"`.
D.2 Live JavaScript per widget: `/console/api/stream`, `/console/api/runs`, `/console/api/status`,
    `/console/api/agent/*`; fallback order live -> latest saved run -> build-time measurement.
D.3 Tests `site/test_isc2.py`: every local link resolves; no non-ASCII letter in any page; every page has the
    six sections; every external or cross-page link opens in a new tab.

## Phase E — publish

E.1 Origin: a second site directory and a whole-site login for the isc-2 host (`deploy/origin/Caddyfile`),
    validated with `caddy validate`.
E.2 Portal: one more site block and the variable `ISC2_DOMAIN`, through the portal's repository and
    `remote-deploy.sh edge` as for isc-1 (the owner confirms this step again before it runs).
E.3 Verify from outside: certificate, 401 without the login, every page 200 with it, live widgets update.
E.4 Docs: `deploy/README.md`, `README.md`.

## Open decisions (asked when the step comes)

1. isc-1 after isc-2 works: keep, or redirect to isc-2.
2. E.2 touches the shared portal proxy again: confirmation before the container is recreated.

## Deviations from the standard procedure

Same as the RAG plan: no `bd` (no beads database), no GRACE XML (not a GRACE project), tasks list the tests and
their assertions instead of full code.
