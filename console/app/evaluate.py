"""Evaluation set and scores of the RAG agent.

PURPOSE: run the 16 questions one at a time, score them, keep the latest result, expose it as Prometheus metrics.
INPUTS: (the judge call also gets the row's `expected_facts` and says which the answer states; one call per row)
    `console/eval/questions.json` (kind `blog`: `expected_url`; kind `platform`: `expected_tool`,
    `snapshot`, `expected_facts`) and `console/eval/snapshots/*.json`; an `ask(question, snapshot)` coroutine
    returning `agent.AgentResult`; a `judge(context, answer)` coroutine returning the claims; the corpus index.
OUTPUTS: `run_evaluation(...) -> EvalResult` as a dict
    `{started, finished, team, rows=[{id, kind, question, answer, steps, sources, latency_s, prompt_tokens,
    completion_tokens, first_tool, hit, tool_ok, claims_supported, claims_total, facts_stated, facts_total,
    judge_error, error}],
    summary={hit_at_3, tool_accuracy, faithfulness (shares 0..1), hits, blog_total, tool_ok, platform_total,
    claims_supported, claims_total, facts_stated, facts_total (counts), rows_failed (rows with `error` or
    `judge_error`), latency_p95_s, prompt_tokens, completion_tokens, usd_per_1k_questions},
    chunking}`, saved to `<data_dir>/eval.json`; `metrics_text(result) -> str` with the gauges
    `rag_eval_hit_at_3`, `rag_eval_tool_accuracy`, `rag_eval_faithfulness`, `rag_eval_latency_p95_seconds`,
    `rag_eval_usd_per_1k_questions`, `rag_eval_finished_timestamp_seconds` ("" before the first run).
Scores:
    hit@3     - blog rows whose `expected_url` is among `Index.search(question, k=3)`; a retrieval metric,
                independent of the agent;
    tool      - platform rows whose first tool call is `expected_tool`;
    faithfulness - the judge lists the claims of the answer and marks each `supported` or not against the
                retrieved text (all tool results of the row); supported / all claims over the set.
    A failed agent call or an unparsable judge reply is recorded on the row (`error`, `judge_error`) and counts
    as a miss and as 0 claims; the run continues.
Cost: GPU price per hour x run time / questions x 1000. The design divides the GPU price by measured tokens
    per hour; when the run owns the GPU the two are the same number, so the run time is used directly.
DEPENDS: `agent` (via `ask`), `corpus`, `stats.percentile`, `stats.GPU_USD_PER_HOUR`, `httpx`.
"""
from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Awaitable, Callable

import httpx

from . import corpus
from .stats import GPU_USD_PER_HOUR, percentile

log = logging.getLogger(__name__)

EVAL_DIR = Path(__file__).resolve().parent.parent / "eval"
JUDGE_SYSTEM = (
    "You check an answer against source text. List every factual claim the answer makes. Mark a claim "
    'supported only if the source text states it. Reply with JSON only: {"claims": [{"claim": "...", '
    '"supported": true}]}'
)
FACTS_SYSTEM = (
    ' Expected facts are also given. For each, say whether the answer states it. Add to the JSON: '
    '"facts": [{"fact": "<the expected fact, verbatim>", "stated": true}]')
# A long answer has 20+ claims; 800 tokens cut the JSON of one in the first run (2026-10-29, row B10).
JUDGE_MAX_TOKENS = 2000

Ask = Callable[[str, dict], Awaitable]
Judge = Callable[[str, str, list[str]], Awaitable[tuple[list[dict], list[dict]]]]


def load_eval_set(directory: Path = EVAL_DIR) -> tuple[list[dict], dict[str, dict]]:
    questions = json.loads((directory / "questions.json").read_text(encoding="utf8"))
    snapshots = {p.stem: json.loads(p.read_text(encoding="utf8")) for p in sorted((directory / "snapshots").glob("*.json"))}
    return questions, snapshots


def _reply_json(raw: str) -> dict:
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0]
    if not text.lstrip().startswith("{"):
        raise ValueError("judge reply is not the claims JSON")
    return json.loads(text)


def _valid(items, name_key: str, flag_key: str) -> bool:
    return isinstance(items, list) and all(
        isinstance(i, dict) and isinstance(i.get(flag_key), bool)
        and isinstance(i.get(name_key), str) and i[name_key].strip() for i in items)


def parse_verdict(raw: str, with_facts: bool = False) -> tuple[list[dict], list[dict]]:
    """(claims, facts) from the judge's reply; tolerates a ```json fence; raises ValueError otherwise.

    `facts` is required, and checked, only when `with_facts`; otherwise it is `[]`."""
    reply = _reply_json(raw)
    claims = reply.get("claims")
    facts = reply.get("facts") if with_facts else []
    if not _valid(claims, "claim", "supported") or not _valid(facts, "fact", "stated"):
        raise ValueError("judge reply is not the claims JSON")
    return claims, facts


def parse_claims(raw: str) -> list[dict]:
    return parse_verdict(raw)[0]


async def judge_answer(client: httpx.AsyncClient, gateway_url: str, model: str, key: str,
                       context: str, answer: str, facts: list[str] = ()) -> tuple[list[dict], list[dict]]:
    system, user = JUDGE_SYSTEM, f"Source text:\n{context}\n\nAnswer:\n{answer}"
    if facts:
        system += FACTS_SYSTEM
        user += "\n\nExpected facts:\n" + "\n".join(f"- {f}" for f in facts)
    body = {"model": model, "temperature": 0, "max_tokens": JUDGE_MAX_TOKENS, "cache": {"no-cache": True},
            "chat_template_kwargs": {"enable_thinking": False},
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    r = await client.post(f"{gateway_url.rstrip('/')}/v1/chat/completions", json=body,
                          headers={"Authorization": f"Bearer {key}"})
    r.raise_for_status()
    return parse_verdict(r.json()["choices"][0]["message"].get("content") or "", with_facts=bool(facts))


def _share(part: int, whole: int) -> float:
    return part / whole if whole else 0.0


async def _run_row(q: dict, snapshots: dict, index: corpus.Index, ask: Ask, judge: Judge) -> dict:
    row = {"id": q["id"], "kind": q["kind"], "question": q["question"], "answer": "", "steps": [],
           "sources": [], "latency_s": 0.0, "prompt_tokens": 0, "completion_tokens": 0, "first_tool": None,
           "hit": None, "tool_ok": None, "claims_supported": 0, "claims_total": 0,
           "facts_stated": 0, "facts_total": len(q.get("expected_facts") or [])}
    if q["kind"] == "blog":
        row["hit"] = q["expected_url"] in [h.chunk.url for h in index.search(q["question"], k=3)]
    try:
        res = await ask(q["question"], snapshots[q.get("snapshot", "idle")])
    except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError) as exc:
        row["error"] = type(exc).__name__
        log.warning("[Evaluate][row][ASK_ERROR] id=%s %s", q["id"], type(exc).__name__)
        res = None
    if res:
        row.update(answer=res.answer, steps=res.steps, sources=res.sources, latency_s=res.latency_s,
                   prompt_tokens=res.prompt_tokens, completion_tokens=res.completion_tokens)
        row["first_tool"] = res.steps[0]["tool"] if res.steps else None
        context = json.dumps([s["result"] for s in res.steps])
        try:
            claims, facts = await judge(context, res.answer, q.get("expected_facts") or [])
            row["claims_total"] = len(claims)
            row["claims_supported"] = sum(1 for c in claims if c["supported"])
            row["facts_stated"] = min(sum(1 for f in facts if f["stated"]), row["facts_total"])
        except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError) as exc:
            row["judge_error"] = str(exc) or type(exc).__name__
    if q["kind"] == "platform":
        row["tool_ok"] = row["first_tool"] == q["expected_tool"]
    return row


def chunking_comparison(articles: list[corpus.Article], questions: list[dict]) -> dict:
    """hit@3 of the per-kind chunking and of fixed windows on the blog questions; search only, no model."""
    blog = [q for q in questions if q["kind"] == "blog"]
    out: dict = {"blog_total": len(blog)}
    for name, cut in (("kind", corpus.chunk), ("fixed", corpus.chunk_fixed)):
        chunks = [c for a in articles for c in cut(a)]
        index = corpus.Index(chunks)
        out[name] = {"chunks": len(chunks), "hits": sum(
            q["expected_url"] in [h.chunk.url for h in index.search(q["question"], k=3)] for q in blog)}
    return out


async def run_evaluation(questions: list[dict], snapshots: dict, index: corpus.Index, ask: Ask, judge: Judge,
                         *, team: str, chunking: dict | None = None) -> dict:
    started = time.time()
    rows = [await _run_row(q, snapshots, index, ask, judge) for q in questions]
    seconds = time.time() - started
    blog = [r for r in rows if r["kind"] == "blog"]
    platform = [r for r in rows if r["kind"] == "platform"]
    supported = sum(r["claims_supported"] for r in rows)
    total = sum(r["claims_total"] for r in rows)
    hits, tool_ok = sum(bool(r["hit"]) for r in blog), sum(bool(r["tool_ok"]) for r in platform)
    summary = {
        "hit_at_3": _share(hits, len(blog)), "tool_accuracy": _share(tool_ok, len(platform)),
        "faithfulness": _share(supported, total),
        "hits": hits, "blog_total": len(blog), "tool_ok": tool_ok, "platform_total": len(platform),
        "claims_supported": supported, "claims_total": total,
        "facts_stated": sum(r["facts_stated"] for r in rows), "facts_total": sum(r["facts_total"] for r in rows),
        "rows_failed": sum(1 for r in rows if r.get("error") or r.get("judge_error")),
        "latency_p95_s": percentile([r["latency_s"] for r in rows], 95),  # agent time, judge excluded
        "prompt_tokens": sum(r["prompt_tokens"] for r in rows),
        "completion_tokens": sum(r["completion_tokens"] for r in rows),
        "usd_per_1k_questions": GPU_USD_PER_HOUR * seconds / 3600 / len(rows) * 1000 if rows else 0.0,
    }
    return {"started": started, "finished": time.time(), "team": team, "rows": rows, "summary": summary,
            "chunking": chunking}


_GAUGES = (("rag_eval_hit_at_3", "hit_at_3"), ("rag_eval_tool_accuracy", "tool_accuracy"),
           ("rag_eval_faithfulness", "faithfulness"), ("rag_eval_latency_p95_seconds", "latency_p95_s"),
           ("rag_eval_usd_per_1k_questions", "usd_per_1k_questions"))


def metrics_text(result: dict | None) -> str:
    if result is None:
        return ""
    pairs = [(name, result["summary"][key]) for name, key in _GAUGES]
    pairs.append(("rag_eval_finished_timestamp_seconds", result["finished"]))
    return "".join(f"# TYPE {name} gauge\n{name} {value}\n" for name, value in pairs)


def load_result(data_dir: str) -> dict | None:
    try:
        with open(os.path.join(data_dir, "eval.json"), encoding="utf8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def save_result(data_dir: str, result: dict) -> None:
    """Atomic write (temp file + rename); a failure is logged, the console keeps the result in memory."""
    try:
        os.makedirs(data_dir, exist_ok=True)
        tmp = os.path.join(data_dir, "eval.json.tmp")
        with open(tmp, "w", encoding="utf8") as f:
            json.dump(result, f)
        os.replace(tmp, os.path.join(data_dir, "eval.json"))
    except OSError as exc:
        log.warning("[Evaluate][save][SAVE_FAILED] %s", type(exc).__name__)
