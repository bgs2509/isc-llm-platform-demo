# isc-2 site and RAG agent — execution plan

Status (2026-10-29): mockups approved by the owner (as is); plan approved by the owner (do-feature step 10,
2026-10-29, in session). All phases 0 and A-G done, review (step 12) done; isc-2 is live at
https://isc-2.178-208-78-85.sslip.io:9443/ (2026-10-29 16:36). Log below. Replaces `20261029-rag-agent-plan.md` and `20261029-isc2-site-plan.md` (see git history).

Inputs:

1. Design and contracts of the agent: `docs/superpowers/specs/2026-10-29-rag-agent-design.md` (approved).
2. Site content: `docs/superpowers/specs/2026-10-29-isc2-site-design.md` (approved).
3. Page mockups: `docs/superpowers/mockups/isc2/` (approved 2026-10-29, as is; commit `62a0291`).

Tests: `cd console && python -m pytest`; `python -m pytest site`; `python -m pytest scripts/tests` (new in
Phase D); `helm lint chart/llm-platform`.

## Decisions taken while planning (2026-10-29, /best-questions)

1. One plan file (this one); the two earlier plans are deleted. [auto-selected]
2. Pages are built from the approved mockup HTML used as templates with `{{key}}` placeholders, filled from
   JSON by `site/isc2/build.py` (standard library only); no f-string pages, no Jinja2. [auto-selected]
3. Built pages are tracked in git (`deploy/origin/site-isc2/`) and reach the web server by `git pull --ff-only`
   (owner rule of 2026-10-07); no `tar` or `rsync` for isc-2. [auto-selected]
4. The origin serves isc-2 from the same `:19080` site block through a `@isc2 host` matcher placed after the
   `/console/*` and `/grafana/*` handles and before the fallback (Caddy sorting rules: a named matcher keeps
   its Caddyfile position; caddyserver.com/docs/caddyfile/directives); no new port, no new firewall rule.
   [auto-selected]
5. The test count on page 6 and home widget 6 comes from a `pytest` run done by the build command; any failing
   test stops the build. [auto-selected]
6. "Ask the agent" on page 4 always uses the team `research`; no team picker. [owner]
7. isc-1 stays next to isc-2 (open documents, login only on console and Grafana). [owner]
8. isc-1 moves to git delivery too (task F.0); `deploy/publish.sh` is deleted. [auto-selected]
9. Merged GitHub branches deleted on 2026-10-29: `worktree-fix+branch-origin-host-match` (this repository,
   was `934f2903`) and `feat/branch-isc1-site` (portal repository, was `ab285eb5`, contained in its
   `master`). [owner, done]
10. The documents the isc-2 pages link to (README, architecture, benchmark report, handover, 5 runbooks,
    publishing) are built into isc-2 too (task E.3); the 14 non-ASCII signs in them (`×` 10, `→` 3, `÷` 1)
    are replaced in the source files (task E.0). [owner]
11. Evaluation requests carry `"cache": {"no-cache": true}` (LiteLLM per-request cache control,
    docs.litellm.ai/docs/proxy/caching_controls); `POST /api/agent/ask` keeps the gateway cache. Reason: the
    gateway cache answered a repeated request in 0.02 s and its key ignores `chat_template_kwargs` (Phase 0
    log), so a second evaluation run would report cached latency. [auto-selected]

## Rules for every task

1. TDD: write the failing test, run it and see it fail (RED), write the least code that passes (GREEN), run
   all tests of the package, commit. Each task lists its tests and their assertions.
2. Commits: `feat(console): ...`, `test(console): ...`, `feat(site): ...`, `feat(chart): ...`,
   `feat(deploy): ...`, `docs(...): ...`. Commits are local; `git push` only when the owner asks.
3. Every new module starts with its contract (PURPOSE, INPUTS, OUTPUTS, DEPENDS) copied from the design.
4. Logs follow `[Module][function][BLOCK] message`; no question text, no key, no password in any log.
5. Remote steps: ssh to spark-1 and vpn-2 as separate Bash calls; the model `qwen38-lil` is never restarted;
   the portal on vpn-2 changes only through its own repository and after the owner confirms.
6. Any step that differs from this plan stops with "deviation detected, approve?" before it continues.

## Phase 0 — checks on spark-1 (no code kept)

0.1 Gateway spike, from the console pod with the `research` key: one request with `tools` (expect
    `tool_calls` in the reply); one with `chat_template_kwargs: {"enable_thinking": false}` (expect no
    reasoning text). Record both reply shapes in the log below. Either fails -> stop and ask.
0.2 Read only: the vLLM launch arguments of the running container (`docker inspect`, no restart) — the
    `--max-num-seqs` value (default if absent) and the context length. Record in the log.
0.3 Decide the alert drill load from 0.2. If the model has 16 slots or more, one team (research, at most 16
    parallel requests) cannot make `waiting > 4`: the drill then runs two loads at once (console run as
    research at 16 plus engineering at 8 from the drill script). If that still cannot reach 21 waiting-or-
    running requests, stop and ask the owner before Phase D.

## Phase A — corpus and retrieval (`console/app/corpus.py`)

A.1 Move the corpus. Copy `corpus/blog/md/*.md` (36 files, git-ignored, only in the main checkout) to
    `console/corpus/blog/` (tracked). Turn `corpus/_scripts/` into `scripts/build_blog_corpus.py` (fetch and
    extract, writes to `console/corpus/blog/`). Dockerfile: `COPY corpus ./corpus`. Commit
    `feat(console): blog corpus for the RAG agent`.
A.2 Tests `console/tests/test_corpus.py`:
    1. `load_articles` reads the five front-matter keys; a file without `url` raises `ValueError` naming the
       file.
    2. A `case` article gives exactly 1 chunk; its text starts with `"<title> (<url>)"`.
    3. A `sections` article: a 50-word section merges into the next; a 900-word section gives at least
       2 chunks.
    4. A `plain` article of 600 words gives 3 chunks of at most about 300 words; neighbours share one
       paragraph.
    5. `chunk_fixed(article)` (fixed windows of about 250 words, used only by the comparison) and `chunk`
       each cover every word of the article at least once.
    6. `Index.search("cloud migration manufacturing")` ranks the cloud-migration case first (fixture of
       3 short articles); a query of unknown words returns `[]`.
    7. Real corpus: 36 articles load; 60 to 120 chunks; every chunk has a URL.
A.3 Implement: front-matter parser (five `key: "json string"` lines), the three kind chunkers, the
    fixed-window chunker, BM25 (k1 = 1.5, b = 0.75, lower-case word tokens). Commit.

## Phase B — platform status (`console/app/platform_status.py`) and `GET /api/status`

B.1 Tests `console/tests/test_platform_status.py` (fake Prometheus through `httpx.MockTransport`):
    1. `/api/v1/rules?type=alert` with one firing and one inactive rule -> two rows, states `firing`,
       `inactive`.
    2. `value` of `sum(vllm:num_requests_waiting) > 4` = the instant value of the left side; a rule with
       `and` -> `None`.
    3. `teams` parses `api_key_alias` series into one row per team (requests/s, tokens/s over 5 minutes).
    4. `signals` returns five entries `reliability, latency, usage, errors, cost`, each with `value` and
       `series` (15 minutes, step 30 s, from `/api/v1/query_range`); `cost` is computed from `usage` and the
       GPU price, not by PromQL.
    5. `health` returns `up` for `vllm, gpu, gateway, console` from the `up` series and `prometheus: true`
       when Prometheus answered; Prometheus unreachable -> every entry `unknown`.
    6. Unknown view -> `{"error": ...}`; connection error -> `{"error": "prometheus unavailable"}`.
    7. A snapshot source returns the snapshot's `alerts` / `teams` unchanged.
B.2 Implement. The PromQL of `teams` is the dashboard's (`scripts/make_dashboard.py` panels 7 and 10); the
    model never sends PromQL. GPU price: one constant `GPU_USD_PER_HOUR = 0.2` in `stats.py`, used by
    `RunParams` and by this module (one home for the price).
B.3 Tests in `console/tests/test_api.py` (FastAPI `TestClient`, Prometheus faked): `GET /api/status?view=alerts`
    -> 200 list; `view=nope` -> 422. Implement the route. Commit.
B.4 Run timeline: test that one tick of an active run appends `kv_cache_pct` and `vllm_waiting` to
    `run["timeline"]` (fake GPU and vLLM sources). Implement in `runner.py` `_tick`. Commit.

## Phase C — agent, evaluation, routes, wiring, deploy

C.1 Tests `console/tests/test_agent.py` (fake gateway with scripted replies):
    1. Reply 1 asks `search_docs`, reply 2 answers -> one step; sources = the hits' title and URL; tokens
       summed over both replies.
    2. A reply asks `platform_status(view="alerts")` -> the status callable receives `"alerts"`.
    3. The model keeps asking for tools -> after 3 rounds the request goes without `tools`; `rounds == 3`.
    4. Malformed tool arguments -> the tool result is `{"error": ...}`; the loop continues.
    5. Every request carries `temperature: 0` and `chat_template_kwargs.enable_thinking: false`.
    6. With `no_cache=True` (used by the evaluation) every request carries `cache: {"no-cache": true}`;
       without it (used by `ask`) no `cache` field is sent.
C.2 Implement `agent.py`; route `POST /api/agent/ask` with tests: unknown tenant 404, question over
    500 characters 422, success returns the `AgentResult` fields. Commit.
C.3 Evaluation set: `console/eval/questions.json` (16 questions: 10 blog with `expected_url`; 6 platform with
    `expected_tool`, `snapshot`, `expected_facts`), snapshots `idle.json` and `overload.json`. The owner
    reviews the 16 questions before the first scored run. Dockerfile: `COPY eval ./eval`.
C.4 Tests `console/tests/test_evaluate.py`:
    1. hit@3 = blog rows whose `expected_url` is among the first 3 hits, of 10.
    2. tool accuracy = rows whose first tool call matches `expected_tool`, of 6.
    3. faithfulness = supported claims / all claims, from a fake judge reply in JSON.
    4. `chunking_comparison()` returns hit@3 of `chunk` and of `chunk_fixed` on the 10 blog questions
       (search only, no model calls).
    5. `metrics_text` prints the six gauges with the design's names and values; empty before the first run.
    6. The result is saved to and loaded from `data_dir/eval.json`.
C.5 Implement the runner (one question at a time), routes `POST /api/agent/eval` (409 while one runs),
    `GET /api/agent/eval` (404 before the first run), `GET /metrics`. Commit.
C.6 Chart and dashboard: console env `PROMETHEUS_URL=http://prometheus:9090`; scrape job `console`
    (`console:8000/metrics`); `make_dashboard.py` row "RAG agent" (5 stat panels); regenerate
    `chart/llm-platform/files/dashboard.json`; `helm lint`. Commit `feat(chart): ...`.
C.7 Deploy on spark-1 (owner asks for the push first): `git pull --ff-only`, `scripts/install.sh` with
    `-f deploy/values-site.yaml`; checks: target `console` is `up`; one `ask` per tool; `GET /api/status` for
    the four views.
C.8 First evaluation run with the `research` key; record the summary and the chunking comparison in the log.

## Phase D — measurements (`scripts/measure_*.py`, results in `docs/measurements/*.json`, tracked)

Every script prints what load it will start and for how long, and waits for Enter. GPU load in total about
7 minutes; the owner confirms the start of the phase.

D.1 `measure_kv.py`: 5 runs of 30 s through the console API (prompt 200, 500, 1,000, 1,000, 2,000 words at
    4, 8, 8, 16, 16 parallel); records peak KV cache, peak waiting, TTFT p95, tokens/s ->
    `kv-sweep.json`.
D.2 `measure_gateway_drill.py`: 60 s run at 8 parallel; at 20 s delete the `litellm` pod; record seconds to
    ready, failed requests N of M, throughput recovery -> `gateway-drill.json`.
D.3 `measure_budget_drill.py`: temporary key (budget 0.001 USD, 5 requests/min) created and deleted through
    the gateway API with the master key read from the cluster secret (never printed); requests until
    refusal; spend recorded vs computed -> `budget-drill.json`. The key is deleted in a `finally` block.
D.4 `measure_alert_drill.py`: load from 0.3 for about 2 minutes; times when `ModelQueueBuildingUp` fires and
    resolves from the Prometheus `ALERTS` series; peak waiting -> `alert-drill.json`.
D.5 `helm history llm-platform -o json` -> `helm-history.json`; latest evaluation -> `eval.json`.
D.6 Each script has a test of its pure part (summary arithmetic over a recorded sample) in
    `scripts/tests/`; the network part is checked by the run itself. Commit the scripts, then the results.

## Phase E — site builder (`site/isc2/`)

E.0 Documents: replace `×` with `x`, `→` with `->`, `÷` with `/` in `README.md`, `docs/benchmark-report.md`,
    `docs/handover.md`, `deploy/README.md`, `docs/runbooks/05-release-upgrade-rollback.md`; en and em dashes
    stay (typographic punctuation, allowed by rule 1 of the site design). `scripts/make_report.py` writes
    the benchmark report (lines 27, 30, 58, 67-70): change its output strings the same way and regenerate.
    The isc-1 landing page (`site/build.py` lines 84-86) keeps its signs: isc-1 is not under rule 1.
    Commit `docs(...): ...`.
E.1 `git mv docs/superpowers/mockups/isc2/*.html site/isc2/templates/`; `mock.css` -> `site/isc2/static/site.css`;
    `mock.js` -> `site/isc2/static/site.js`. Remove every "Mock note" element and the notes button; replace
    each placeholder `<span class="ph">...</span>` with `{{key}}`; repeated rows (KV table, Helm history,
    16 evaluation rows, incident cards) become one key each, filled with HTML built in Python.
E.2 Tests `site/test_isc2.py` (render with a fixture inputs dict; no pytest inside pytest):
    1. Every `{{key}}` is filled; an unknown key fails the build with its name.
    2. No character outside ASCII in any page.
    3. Every page except home has the six sections, in order.
    4. Every `<a>` has `target="_blank"` and `rel="noopener"`.
    5. Every local link and asset resolves inside the output.
    6. The pages in `deploy/origin/site-isc2/` equal `render(load("site/isc2/inputs.json"))` byte for byte
       (no drift between the tracked pages and the inputs).
E.3 Implement `site/isc2/build.py`: `gather()` runs `pytest -q` in `console` and `site` (stops on a failure),
    reads `docs/benchmark-results.json` and `docs/measurements/*.json`, the commit hash, and writes
    `site/isc2/inputs.json`; `render(inputs)` fills the templates and turns the 10 linked documents into
    pages with the isc-2 header (reuses `md_to_html` from `site/build.py`; the E.2 tests cover these pages
    too); `main()` = gather, render, write to `deploy/origin/site-isc2/`. The footer shows the input commit and the date of the newest measurement,
    not the build time (keeps E.2.6 deterministic).
E.4 Live JavaScript in `site.js`: `/console/api/stream` (strip of page 1, home widget 1), `/console/api/status`
    (views per page), `/console/api/agent/eval` and `POST /console/api/agent/ask` with `tenant: "research"`,
    `/console/api/runs` (latest saved run). Order of sources per widget: live -> latest saved run with its
    date -> build-time value already in the page. Checked by hand in E.5; no browser test framework.
E.5 Build, open the pages locally against the console through an SSH tunnel to spark-1; check each live
    widget once. Commit `feat(site): ...` and the built pages.

## Phase F — publish isc-2

F.0 isc-1 to git delivery: `site/build.py` writes to `deploy/origin/site/` (tracked; remove it and `site/dist/`
    from `.gitignore`); its footer shows the commit and the date of `docs/benchmark-results.json` instead of
    the build time; test in `site/test_build.py` that the tracked pages equal a fresh build; delete
    `deploy/publish.sh`. Commit `feat(site): ...` and the built pages.
F.1 `deploy/origin/Caddyfile`: `@isc2 host {$ISC2_DOMAIN}` and `handle @isc2 { import /run/secrets/auth.caddy;
    root * /srv/isc2; file_server }` after the console and Grafana handles, before the fallback;
    `compose.yaml`: mount `./site-isc2` read-only at `/srv/isc2`, pass `ISC2_DOMAIN` (from the
    git-ignored `deploy/site.env`, like the other site settings). `caddy validate` in the `caddy:2.11.4-alpine`
    image. Commit.
F.2 Portal (owner confirms before the container is recreated): one block `{$ISC2_DOMAIN}:{$HTTPS_PORT}` ->
    `host.docker.internal:19080` and the variable `ISC2_DOMAIN`, through the portal repository and
    `remote-deploy.sh edge` as for isc-1. Domain (hypothesis, to confirm): `isc-2.178-208-78-85.sslip.io`.
F.3 vpn-2: `git pull --ff-only` in the project clone; `docker compose up -d --force-recreate` in
    `deploy/origin/` (the Caddyfile is a single-file mount).
F.4 Verify from outside: valid certificate; 401 on `/` and on a page without the login; every page 200 with
    it; `/console/api/status?view=health` 200 with the same login and no second prompt; isc-1 unchanged
    (its home page still 200 without a login).

## Phase G — documents and finish

G.1 `docs/architecture.md` (components: RAG agent, status API, isc-2 site); `docs/handover.md` (run the
    evaluation, rebuild and publish isc-2); `deploy/README.md` (isc-2 host, matcher, git delivery);
    `README.md` (measured numbers); `AGENTS.md` layout (`site/isc2/`, `docs/measurements/`,
    `console/corpus/`, `console/eval/`).
G.2 All checks: `cd console && python -m pytest`, `python -m pytest site`, `helm lint chart/llm-platform`.
G.3 Review (do-feature step 12) and finish (step 13).

## Traceability (requirement of the role -> tasks)

1. Inference on GPU -> B.4, D.1, page 1.
2. GPU infrastructure, Kubernetes, operations -> B.1.5, D.2, D.5, page 2.
3. Gateway -> B.1.3, D.3, page 3.
4. RAG, agents, evaluation, APIs -> A, B.1.1-2, C.1-C.5, C.8, page 4.
5. Observability -> B.1.4, C.6, D.4, page 5.
6. Debugging, delivery, stakeholders -> E.3 (test count), D.5, page 6.

Contract items without a task: none. Tasks without a contract or design item: none.

## Deviations from the standard procedure

1. No `bd` issue: the project has no beads database.
2. No GRACE artifacts: the project is not a GRACE project; contracts live in the design and module headers.
3. Tasks list tests and assertions instead of full code: the plan is executed by the author of the design.
4. Written inline by the orchestrator, not by a mid-tier subagent (do-feature step 9): the whole context
   (code read in this session, six decisions) was already here.

## Open questions

None (the three earlier ones and the documents gap were decided on 2026-10-29: decisions 7-10).

## Log

### 2026-10-29 — Phase 0 done

1. 0.2 vLLM `qwen38-lil` launch flags (read with `docker inspect`, no restart): `--max-num-seqs 16`,
   `--max-model-len 262144`, `--kv-cache-dtype fp8`, `--gpu-memory-utilization 0.734`,
   `--enable-auto-tool-choice --tool-call-parser qwen3_coder`, `--reasoning-parser qwen3`.
2. 0.3 With 16 slots one team cannot make `waiting > 4`; the alert drill (D.4) runs research at 16 parallel
   (console run) plus engineering at 8 (drill script): 24 requests, up to 8 waiting. No stop needed.
3. FP8 KV cache is already on: remove "FP8 KV cache" from page 1 "What I'd change" in E.1.
4. 0.1 Gateway spike from the console pod (namespace `llm-platform`, `~/bin/kubectl` on spark-1), team
   `research`, `temperature 0`:
   1. `tools` + `enable_thinking: false` -> 200, `finish_reason: tool_calls`, one call `search_docs` with
      argument `query`, no content, no reasoning, 0.99 s, 304 tokens.
   2. Fresh prompt, `enable_thinking: false` -> 200, `content` only (296 characters), no
      `reasoning_content`, 1.43 s.
   3. Default (thinking on) -> message has `reasoning_content` (321 characters) next to `content`.
   4. Same prompt again without the flag -> 0.02 s, identical body: a gateway cache hit; the cache key ignores
      `chat_template_kwargs` (decision 11). With `cache: {"no-cache": true}` -> 1.51 s (model called).
5. Candidate for the sixth incident card (page 6, layer model/gateway): the exact-match cache returned an
   answer made with thinking on/off settings different from the request's.

### 2026-10-29 — Phases A-G (owner away, all confirmations given in advance; --auto-approve)

1. A: corpus 36 articles (case 14, sections 7, plain 15); `chunk` 73 chunks, `chunk_fixed` 94.
2. B: status views alerts, teams, signals, health; GPU price constant in `stats.py`.
3. C: agent, evaluation, routes; C.3 set written by the controller (10 blog, 6 platform); C.6 chart and
   dashboard row. C.7 deploy on spark-1 (Helm revision 9; the spark-1 clone now tracks this work branch,
   pushed to GitHub; `main` untouched). Live checks: health all `up`; one ask per tool answered.
4. Fixes found live (each with a test): reliability signal empty without 5xx series (`or vector(0)`);
   judge JSON cut at 800 tokens (now 2,000); console INFO logs dropped under uvicorn; load runs never
   recovered after a gateway pod was replaced (connect timeout was the 180 s request timeout; now 5 s, and a
   0.5 s pause after a connection error) — found by drill D.2, confirmed by an experiment in the console pod.
5. D: all six measurements in `docs/measurements/` (one script `scripts/measure.py` instead of five files).
   Gateway drill summary changed to "seconds without answers" (tokens/s is a swinging 5 s window). The
   synthetic overload snapshot was replaced by the capture of drill D.4 (KV cache 0.59, not 0.95), and the
   expected facts of P2, P3, P5, P6 follow it. Final evaluation: hit@3 9 of 10, tools 6 of 6, 157 of 158
   claims, p95 8.76 s, 0.63 USD per 1,000 questions.
6. E: templates moved from `docs/superpowers/mockups/isc2/` to `site/isc2/templates/` (the mockups folder
   is gone; git history keeps it). Build-time numbers from the measurements; evaluation dates are unix
   seconds (fixed in builder and site.js). E.5 (browser check of live widgets) not done: no browser on
   `file://` here; the routes the widgets call answer 200 through the origin with the login.
7. F.0, F.1 done; F.3 on vpn-2: clone switched to this work branch, the old tar copy of isc-1 kept as
   `deploy/origin/site.tar-copy-2026-10-29/`, `deploy/origin/.env` holds `ISC2_DOMAIN`; origin recreated.
   Checked on vpn-2 with Host headers: isc-1 `/` 200 without login, console and Grafana 401; isc-2 every
   path 401 without login, 13 of 13 paths 200 with it (pages, documents, console API, Grafana).
8. F.2 portal: branch `feat/branch-isc2-site` (commit 56a7dec) adds the block and the variable, and repairs
   the deploy tests the isc-1 change had left red (113 of 113 pass). Not merged and not deployed: this
   session may not merge or push to a master branch. Full portal suite: 663 passed, 1 failed
   (`test_explain_numbers`, unrelated data test, red before this change).
9. Owner steps left: merge the portal branch into its master and push; on vpn-2 add `ISC2_DOMAIN` to
   `~/.isuzu-secrets/web.env` and run `remote-deploy.sh edge`; merge this work branch into `main` (spark-1 and
   vpn-2 clones can then return to `main`); check https://isc-2.178-208-78-85.sslip.io:9443/ from outside.

### 2026-10-29 — Step 12 review

1. External reviewer (model-run.sh --role reviewer): NOT READY, 0 critical, 12 important, 2 minor. Each finding
   was checked in the code. 13 fixed with tests (commits 2a8eeef..f2fabc2): strict judge reply, row-level
   errors, atomic save with a log line, expected facts scored by the judge (decision taken by threshold:
   score them), sparklines, trailing outage in the drill, bounded polling, checked key delete, port-forward
   kill, corpus script exit codes, tenant limits from values.yaml, signal expressions from the console
   constants, values() split per page, builds swapped into place. Not changed: the 5-minute team window
   (plan decision B.1.3; the site labels it).
2. Tests after the fixes: console 67, site and scripts 38, all passing.
3. Evaluation after redeploy (2026-10-29 16:30): hit@3 9 of 10, tools 6 of 6, 162 of 164 claims, 8 of 8
   expected facts, 0 failed rows, p95 10.3 s, 0.67 USD per 1,000 questions.

### 2026-10-29 — Owner steps done on the owner's request; F.4

1. Portal: `master` fast-forwarded to `feat/branch-isc2-site` (ab285eb..56a7dec, no merge commit); vpn-2:
   `ISC2_DOMAIN` added to `~/.isuzu-secrets/web.env`, portal clone pulled, `remote-deploy.sh edge` (caddy
   healthy).
2. F.4 from outside: https://isc-2.178-208-78-85.sslip.io:9443/ has a valid certificate and answers 401
   without the login; with it `/`, `rag.html`, `delivery.html`, `docs/handover.html`,
   `/console/api/status?view=health`, `/console/api/agent/eval`, `/grafana/` answer 200; isc-1 still 200
   without a login.
3. This branch fast-forwarded into `main`; spark-1 and vpn-2 clones back on `main`.
