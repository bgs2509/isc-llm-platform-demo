import json

import httpx
import pytest

from app import evaluate
from app.agent import AgentResult
from app.corpus import Article, Index, chunk

URL_A, URL_B = "https://x/alpha", "https://x/beta"


def _article(slug, url, body):
    return Article(slug, slug.title(), url, "", "", "plain", body)


ARTICLES = [_article("alpha", URL_A, "quantum annealing reduces cost of optimisation problems"),
            _article("beta", URL_B, "personalised recommendations raise marketplace revenue")]
INDEX = Index([c for a in ARTICLES for c in chunk(a)])
SNAPSHOTS = {"idle": {"alerts": []}, "overload": {"alerts": [{"name": "X"}]}}
QUESTIONS = [
    {"id": "B1", "kind": "blog", "question": "quantum annealing cost", "expected_url": URL_A},
    {"id": "B2", "kind": "blog", "question": "marketplace revenue", "expected_url": URL_A},  # wrong url: miss
    {"id": "P1", "kind": "platform", "question": "any alert?", "expected_tool": "platform_status",
     "snapshot": "idle", "expected_facts": []},
    {"id": "P2", "kind": "platform", "question": "which alerts?", "expected_tool": "platform_status",
     "snapshot": "overload", "expected_facts": []},
]


async def fake_ask(question, snapshot):
    tool = "search_docs" if question == "any alert?" else "platform_status"  # P1 picks the wrong tool
    return AgentResult(answer="a", steps=[{"tool": tool, "args": {}, "result": [{"text": "t"}]}],
                       prompt_tokens=10, completion_tokens=4, latency_s=2.0, rounds=1)


async def fake_judge(context, answer, facts=()):
    return ([{"claim": "c1", "supported": True}, {"claim": "c2", "supported": False}],
            [{"fact": f, "stated": f != "missing fact"} for f in facts])


async def _run(**kw):
    return await evaluate.run_evaluation(kw.get("questions", QUESTIONS), SNAPSHOTS, INDEX, kw.get("ask", fake_ask),
                                         kw.get("judge", fake_judge), team="research")


async def test_hit_at_3_counts_blog_rows():
    s = (await _run())["summary"]
    assert (s["hits"], s["blog_total"], s["hit_at_3"]) == (1, 2, 0.5)


async def test_tool_accuracy_counts_first_tool():
    result = await _run()
    s = result["summary"]
    assert (s["tool_ok"], s["platform_total"], s["tool_accuracy"]) == (1, 2, 0.5)
    assert [r["first_tool"] for r in result["rows"]] == ["platform_status", "platform_status", "search_docs",
                                                         "platform_status"]


async def test_faithfulness_from_judge_claims():
    s = (await _run())["summary"]
    assert (s["claims_supported"], s["claims_total"], s["faithfulness"]) == (4, 8, 0.5)


async def test_judge_reply_is_parsed_from_json_even_in_a_fence():
    reply = {"choices": [{"message": {"content": '```json\n{"claims": [{"claim": "c", "supported": true}]}\n```'}}]}
    seen = []

    def handler(request):
        seen.append(json.loads(request.content))
        return httpx.Response(200, json=reply)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    claims, facts = await evaluate.judge_answer(client, "http://gw", "m", "k", "source text", "the answer")
    assert claims == [{"claim": "c", "supported": True}] and facts == []
    body = seen[0]
    assert body["temperature"] == 0 and body["cache"] == {"no-cache": True}
    assert body["chat_template_kwargs"] == {"enable_thinking": False}
    assert "source text" in body["messages"][-1]["content"] and "the answer" in body["messages"][-1]["content"]


async def test_unparsable_judge_reply_counts_zero_claims_and_is_recorded():
    async def bad_judge(context, answer, facts=()):
        raise ValueError("judge reply is not JSON")

    result = await _run(judge=bad_judge)
    assert result["rows"][0]["judge_error"] == "judge reply is not JSON"
    assert result["summary"]["claims_total"] == 0


async def test_summary_latency_tokens_and_cost():
    s = (await _run())["summary"]
    assert s["latency_p95_s"] == 2.0
    assert (s["prompt_tokens"], s["completion_tokens"]) == (40, 16)
    assert s["usd_per_1k_questions"] >= 0


def test_chunking_comparison_runs_search_only():
    cmp = evaluate.chunking_comparison(ARTICLES, QUESTIONS)
    assert cmp == {"kind": {"chunks": 2, "hits": 1}, "fixed": {"chunks": 2, "hits": 1}, "blog_total": 2}


def test_metrics_text_has_the_six_gauges():
    assert evaluate.metrics_text(None) == ""
    result = {"finished": 1700000000.0, "summary": {
        "hit_at_3": 0.9, "tool_accuracy": 1.0, "faithfulness": 0.8, "latency_p95_s": 3.5,
        "usd_per_1k_questions": 0.12}}
    text = evaluate.metrics_text(result)
    for name, value in [("rag_eval_hit_at_3", "0.9"), ("rag_eval_tool_accuracy", "1.0"),
                        ("rag_eval_faithfulness", "0.8"), ("rag_eval_latency_p95_seconds", "3.5"),
                        ("rag_eval_usd_per_1k_questions", "0.12"),
                        ("rag_eval_finished_timestamp_seconds", "1700000000.0")]:
        assert f"# TYPE {name} gauge" in text
        assert f"\n{name} {value}\n" in "\n" + text


def test_result_is_saved_and_loaded(tmp_path):
    assert evaluate.load_result(str(tmp_path)) is None
    evaluate.save_result(str(tmp_path), {"team": "research", "rows": []})
    assert evaluate.load_result(str(tmp_path)) == {"team": "research", "rows": []}
    assert (tmp_path / "eval.json").exists()


def test_question_files_load():
    questions, snapshots = evaluate.load_eval_set()
    assert len(questions) == 16 and set(snapshots) == {"idle", "overload"}


@pytest.mark.parametrize("raw", [
    "not json", '{"claims": "x"}', '{"claims": [{"claim": "c"}]}',
    '{"claims": [{"supported": true}]}', '{"claims": [{"claim": "", "supported": true}]}',
    '{"claims": [{"claim": 5, "supported": true}]}'])
def test_bad_judge_shapes_raise(raw):
    with pytest.raises(ValueError):
        evaluate.parse_claims(raw)


async def test_empty_choices_gives_row_error_not_abort():
    async def ask_empty(question, snapshot):
        raise IndexError("choices")

    async def judge_type(context, answer, facts=()):
        raise TypeError("x")

    result = await _run(ask=ask_empty)
    assert all(r["error"] == "IndexError" for r in result["rows"])
    assert result["summary"]["rows_failed"] == 4
    result = await _run(judge=judge_type)
    assert result["summary"]["rows_failed"] == 4 and "judge_error" in result["rows"][0]


async def test_expected_facts_are_judged_in_the_same_call():
    questions = [dict(QUESTIONS[2], expected_facts=["a fact", "missing fact"]), QUESTIONS[0]]
    seen = []

    async def judge(context, answer, facts=()):
        seen.append(list(facts))
        return await fake_judge(context, answer, facts)

    result = await _run(questions=questions, judge=judge)
    assert seen == [["a fact", "missing fact"], []]
    row, blog = result["rows"]
    assert (row["facts_stated"], row["facts_total"]) == (1, 2)
    assert (blog["facts_stated"], blog["facts_total"]) == (0, 0)
    assert (result["summary"]["facts_stated"], result["summary"]["facts_total"]) == (1, 2)


async def test_judge_request_asks_for_facts_only_when_given():
    reply = {"choices": [{"message": {"content":
             '{"claims": [{"claim": "c", "supported": true}], "facts": [{"fact": "f", "stated": true}]}'}}]}
    seen = []

    def handler(request):
        seen.append(json.loads(request.content))
        return httpx.Response(200, json=reply)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    claims, facts = await evaluate.judge_answer(client, "http://gw", "m", "k", "src", "ans", ["f"])
    assert facts == [{"fact": "f", "stated": True}]
    assert "f" in seen[0]["messages"][-1]["content"] and "facts" in seen[0]["messages"][0]["content"]


def test_parse_verdict_requires_facts_when_asked():
    with pytest.raises(ValueError):
        evaluate.parse_verdict('{"claims": []}', with_facts=True)
    with pytest.raises(ValueError):
        evaluate.parse_verdict('{"claims": [], "facts": [{"fact": "f"}]}', with_facts=True)


async def test_rows_failed_counts_only_failed_rows():
    assert (await _run())["summary"]["rows_failed"] == 0


def test_save_is_atomic_and_failure_is_logged(tmp_path, caplog):
    evaluate.save_result(str(tmp_path), {"a": 1})
    assert [p.name for p in tmp_path.iterdir()] == ["eval.json"]
    blocker = tmp_path / "file"
    blocker.write_text("x")
    with caplog.at_level("WARNING"):
        evaluate.save_result(str(blocker), {"a": 1})
    assert "[Evaluate][save][SAVE_FAILED]" in caplog.text
