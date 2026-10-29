# RAG agent — implementation plan

Status (2026-10-29): design approved; plan NOT yet approved — the owner asked for page mockups of the isc-2 site
first, then a detailed execution plan. No task started. The extracted corpus (36 articles with front matter;
20,569 words; kinds: case 14, sections 7, plain 15) is in `corpus/blog/md/` of the main checkout, git-ignored and
NOT committed; raw HTML in `corpus/blog/html/`; the one-off fetch and extract scripts in `corpus/_scripts/`
(task 1.1 turns them into `scripts/build_blog_corpus.py`).

Design and contracts: `docs/superpowers/specs/2026-10-29-rag-agent-design.md`. Tracking: no `bd` in this
project (no `.beads`); this file is the execution SSoT. Tests run with `cd console && python -m pytest`.

Every task: write the failing test (RED), run it, write the least code that passes (GREEN), run all console
tests, commit `feat(console): ...` / `test(console): ...`. Phases fit one context window each (the console is
about 900 lines today).

## Phase 0 — gateway spike (no code kept)

0.1 Through the gateway, with the `research` key, from the console pod on spark-1: one request with `tools`
    (expect `tool_calls` in the reply), one with `chat_template_kwargs: {"enable_thinking": false}` (expect no
    reasoning text). Record the two replies' shapes in the plan's log below. Stop and ask if either fails.

## Phase 1 — corpus and retrieval (`console/app/corpus.py`)

1.1 Move the corpus: `corpus/blog/md/*.md` -> `console/corpus/blog/*.md` (tracked); keep `corpus/` (raw HTML)
    git-ignored; `scripts/build_blog_corpus.py` = the fetch and extract scripts used on 2026-10-29, writing to
    `console/corpus/blog/`; Dockerfile `COPY corpus ./corpus`.
1.2 Tests `test_corpus.py`:
    1. `load_articles` reads front matter; a file without `url` raises `ValueError` with the file name.
    2. `case` article -> exactly 1 chunk; the chunk text starts with `"<title> (<url>)"`.
    3. `sections` article: a 50-word section is merged into the next; a 900-word section gives >= 2 chunks.
    4. `plain` article of 600 words -> 3 chunks of <= ~300 words, neighbours share one paragraph.
    5. `Index.search("cloud migration manufacturing")` ranks the cloud-migration case first (fixture of 3
       short articles); a query of unknown words returns `[]`.
    6. On the real corpus: 36 articles load; chunk count between 60 and 120; every chunk has a URL.
1.3 Implement `corpus.py` (front matter parser for the five `key: "json string"` lines, chunkers, BM25 with
    k1 = 1.5, b = 0.75, lower-case word tokens).

## Phase 2 — platform status (`console/app/platform_status.py`)

2.1 Tests `test_platform_status.py` (fake HTTP via `httpx.MockTransport`):
    1. `/api/v1/rules` with one firing and one inactive rule -> two rows with states `firing`, `inactive`.
    2. `value` for `sum(vllm:num_requests_waiting) > 4` = the instant value of `sum(vllm:num_requests_waiting)`;
       for a rule with `and` -> `None`.
    3. `teams` parses `api_key_alias` series into rows per team.
    4. Unknown view -> `{"error": ...}`; connection error -> `{"error": "prometheus unavailable"}`.
    5. Snapshot source returns the snapshot's `alerts` / `teams` unchanged.
2.2 Implement; chart value `PROMETHEUS_URL` in `templates/console.yaml`.

## Phase 3 — agent loop (`console/app/agent.py`) and `POST /api/agent/ask`

3.1 Tests `test_agent.py` with a fake gateway (`httpx.MockTransport` returning scripted replies):
    1. Reply 1 asks `search_docs`, reply 2 answers -> one step, sources = the hits' title and URL, tokens summed
       over both replies.
    2. Reply asks `platform_status(view="alerts")` -> the status callable gets `"alerts"`.
    3. Model keeps asking for tools -> after 3 rounds the request is sent without `tools`; `rounds == 3`.
    4. Malformed tool arguments -> the tool result is `{"error": ...}`, loop continues.
3.2 Implement; then `main.py` route with tenant check and 500-character limit; test via FastAPI `TestClient`
    (unknown tenant 404, long question 422).
3.3 Live check on spark-1 after deploy: one blog question, one platform question (Phase 5).

## Phase 4 — evaluation (`console/app/evaluate.py`), routes and `/metrics`

4.1 Write `console/eval/questions.json` (16 questions; 10 blog with `expected_url`; 6 platform with
    `expected_tool`, `snapshot`, `expected_facts`) and 2 snapshots: `idle.json` (all inactive) and
    `overload.json` (from the c=16 benchmark state: queue > 4, KV cache > 0.9 firing). The owner reviews the
    questions before the first scored run.
4.2 Tests `test_evaluate.py`:
    1. hit@3 = share of blog rows whose `expected_url` is among the first 3 search hits.
    2. tool accuracy = share of rows whose first tool call matches `expected_tool`.
    3. faithfulness = supported claims / all claims, from a fake judge reply in JSON.
    4. `metrics_text` prints the six gauges with the expected names and values.
    5. Result saved to and loaded from `data_dir/eval.json`.
4.3 Implement the runner (sequential, one question at a time) and the routes `POST/GET /api/agent/eval`,
    `GET /metrics`; 409 while a run is active.

## Phase 5 — platform wiring, deploy, first run, docs

5.1 `prometheus-config.yaml`: scrape job `console`; `make_dashboard.py`: row "RAG agent" (5 stat panels);
    regenerate the dashboard; `helm lint`.
5.2 Deploy on spark-1 (git pull, `scripts/install.sh` builds the console image and upgrades the release with
    `-f deploy/values-site.yaml`); check target `console` is `up`.
5.3 Run the evaluation once with the `research` key; record the summary.
5.4 Docs: `docs/architecture.md` (component "RAG agent"), `docs/handover.md` (how to run the evaluation),
    `README.md` measured numbers; `python -m pytest site`, `cd console && python -m pytest`, `helm lint`.

## Traceability

- Requirement 4 "RAG" -> Phase 1; "agent workflows" -> Phase 3; "evaluation sets" -> Phase 4; "APIs to
  existing systems" -> Phase 2.
- Requirement 5 "observability" -> Phase 4 (`/metrics`) and 5.1 (scrape, dashboard).
- Contract items without a task: none. Tasks without a contract item: none.

## Deviations from the standard procedure

1. No `bd` issue: the project has no beads database; `bd init` would add infrastructure the project never used.
2. No GRACE artifacts (`knowledge-graph.xml`, `verification-plan.xml`): the project is not a GRACE project;
   contracts live in the design document and the module headers.
3. Tasks list test cases and assertions instead of full code: the plan is executed in this session by the
   author of the design.

## Log

(filled during execution)
