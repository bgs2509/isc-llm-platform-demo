---
feature: rag-agent
risk: medium
risk_reason: "one new package of modules inside the console, two new API routes, one new scrape job; no DB, no auth change, reversible by a helm rollback"
open_questions: []
context7_verified:
  - "prometheus HTTP API /api/v1/rules and /api/v1/query (prometheus.io/docs/prometheus/latest/querying/api)"
  - "litellm proxy callbacks otel (docs.litellm.ai) — not used, recorded as the path to OpenTelemetry"
  - "vllm --runner pooling /v1/embeddings (docs.vllm.ai) — not used, recorded as the path to dense retrieval"
approved: "2026-10-29, owner, in session (variant 2; corpus = client blog; judge = qwen38-lil; company name allowed)"
---

# RAG agent in the console — design and contracts

## Goal

Answer requirement 4 of the target role ("RAG, agent workflows, evaluation sets, APIs to existing systems") with
a working agent inside the existing console, measured by an evaluation set, visible in Prometheus and Grafana
(requirement 5) and on the demo site.

## Approved decisions

1. One model (`qwen38-lil` behind the LiteLLM gateway, alias from `GATEWAY_MODEL`), called with a team key, so
   the agent's tokens and spend are accounted per team like every other request.
2. Two tools, chosen by the model through OpenAI `tools` (the server runs `--enable-auto-tool-choice
   --tool-call-parser qwen3_coder`):
   1. `search_docs(query)` — BM25 over the client firm's public blog (36 articles in `console/corpus/blog/`).
   2. `platform_status(view)` — live Prometheus: `alerts` (the 6 alerting rules: name, state, query, current
      value) or `teams` (requests/s and tokens/s per team over 5 minutes).
3. Chunking by text kind (field `kind` in each article's front matter): `case` — the whole article is one
   chunk; `sections` — one chunk per `##`/`###` section, sections under 80 words merged into the next, sections
   over 400 words split by paragraphs; `plain` — paragraphs packed to about 250 words with one paragraph of
   overlap. Every chunk starts with `<title> (<url>)`.
4. Evaluation set of 16 questions: 10 about the blog (expected article URL), 6 about the platform (expected
   tool, recorded Prometheus snapshot, expected facts). Metrics: hit@3, tool accuracy, faithfulness
   (claim-based, judge `qwen38-lil`), answer latency p95, tokens, cost.
5. No embeddings, no vector store, no new service, no new Python dependency (BM25 is about 30 lines).

## Module contracts

Each new module carries this contract in its header (PURPOSE, INPUTS, OUTPUTS, DEPENDS). Internals may evolve.

### `console/app/corpus.py` — corpus and retrieval (pure)

- PURPOSE: load the blog articles, cut them into chunks by kind, rank chunks for a query.
- INPUTS: a directory of `*.md` files with front matter `title, url, author, date, kind`; a query string.
- OUTPUTS: `load_articles(dir) -> list[Article]`; `chunk(article) -> list[Chunk]` where
  `Chunk(id, title, url, text)` and `text` starts with `"<title> (<url>)"`; `Index(chunks).search(query, k=3)
  -> list[Hit(chunk, score)]`, best first, empty for a query with no known words.
- DEPENDS: standard library only.
- Errors: an article without `title`, `url` or `kind` raises `ValueError` naming the file (fail fast at load).

### `console/app/platform_status.py` — API to the running platform

- PURPOSE: answer `alerts` and `teams` from Prometheus, or from a recorded snapshot in evaluation.
- INPUTS: `view` in `{"alerts", "teams"}`; a Prometheus base URL, or a snapshot dict with the same two keys.
- OUTPUTS: `alerts` -> `[{"name", "state": "firing"|"pending"|"inactive", "query", "value": float|None}]`,
  value = the left side of `<expr> <op> <number>` evaluated now, `None` for other rule shapes;
  `teams` -> `[{"team", "requests_per_s", "tokens_per_s"}]`.
- DEPENDS: `httpx`; Prometheus `/api/v1/rules?type=alert` and `/api/v1/query`.
- Errors: an unknown `view` returns `{"error": ...}` to the model (the model's input is untrusted); Prometheus
  unreachable returns `{"error": "prometheus unavailable"}` — the agent still answers and says so.
- Rule: the model never sends PromQL; the two team queries are the ones the dashboard uses.

### `console/app/agent.py` — the tool-calling loop

- PURPOSE: answer one question with the two tools through the gateway.
- INPUTS: `question`, team key, gateway URL and model, a `search` callable, a `status` callable.
- OUTPUTS: `AgentResult(answer, steps=[{tool, args, result}], sources=[{title, url}], prompt_tokens,
  completion_tokens, latency_s, rounds)`.
- Limits: at most 3 tool rounds, then the model must answer; `temperature 0`; thinking off
  (`chat_template_kwargs.enable_thinking=false`, verified in task 0).
- DEPENDS: `httpx`; `corpus.Index.search`; `platform_status.fetch`.
- Logs: `[Agent][ask][TOOL_CALL]` per call and `[Agent][ask][ANSWER]` with team, rounds, tokens, latency — no
  question text, no key.

### `console/app/evaluate.py` — evaluation set and scores

- PURPOSE: run the 16 questions, score them, keep the latest result, expose it as Prometheus metrics.
- INPUTS: `console/eval/questions.json`; `console/eval/snapshots/*.json`; a team key.
- OUTPUTS: `EvalResult(started, finished, team, rows=[...], summary={hit_at_3, tool_accuracy, faithfulness,
  latency_p95_s, prompt_tokens, completion_tokens, usd_per_1k_questions})` saved to `/data/eval.json`;
  `metrics_text(result) -> str` with gauges `rag_eval_hit_at_3`, `rag_eval_tool_accuracy`,
  `rag_eval_faithfulness`, `rag_eval_latency_p95_seconds`, `rag_eval_usd_per_1k_questions`,
  `rag_eval_finished_timestamp_seconds`.
- Judge: one call per answer; the judge lists the answer's claims and marks each `supported` or not against the
  retrieved text; faithfulness = supported / all claims over the set.
- Cost: GPU price per hour (the console's existing `gpu_usd_per_hour`, 0.20 USD) divided by measured tokens per
  hour of the run, the same arithmetic as `stats.cost_per_million_tokens`.
- DEPENDS: `agent`, `corpus`, `platform_status`, `stats.percentile`, `stats.cost_per_million_tokens`.

### Console API additions (`console/app/main.py`)

1. `POST /api/agent/ask` `{tenant, question}` -> `AgentResult` (404 unknown tenant, 422 question over 500 chars).
2. `POST /api/agent/eval` `{tenant}` -> `{started}`; 409 while one runs.
3. `GET /api/agent/eval` -> the latest `EvalResult` or 404 before the first run.
4. `GET /metrics` -> `metrics_text` of the latest result (empty body before the first run).

### Platform changes

1. Chart: console env `PROMETHEUS_URL=http://prometheus:9090`; Prometheus scrape job `console`
   (`console:8000/metrics`).
2. Grafana: one row "RAG agent" with the five scores (`scripts/make_dashboard.py`).
3. Corpus delivery: `console/corpus/blog/*.md` tracked in git, copied into the image; raw HTML not tracked.
   `scripts/build_blog_corpus.py` fetches and extracts it again.

## Verification

1. Unit tests (`console/tests/`): chunking per kind, BM25 ranking, front-matter errors, rule-value
   extraction, team parsing, the agent loop against a fake gateway (tool call -> answer; 3-round cap),
   scoring arithmetic, metrics text.
2. Live check on spark-1: one `ask` per tool; one full evaluation; the scrape target `console` is `up`; the
   Grafana row shows the scores.

## Honest limits

The judge is the model under test; the questions are written by us from the corpus; BM25 has no synonyms.
The paths beyond the demo are recorded above: dense retrieval through a pooling model behind the gateway,
OpenTelemetry through the gateway's `otel` callback.
