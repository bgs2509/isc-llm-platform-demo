import httpx
from fastapi.testclient import TestClient

from app import main, platform_status


def test_status_route_returns_the_view(monkeypatch):
    calls = []

    async def fake_fetch(view, base_url="", **_):
        calls.append((view, base_url))
        return [{"name": "A", "state": "firing", "query": "x > 1", "value": 2.0}]

    monkeypatch.setattr(platform_status, "fetch", fake_fetch)
    client = TestClient(main.app)  # no context manager: the 1 Hz sampler does not start
    r = client.get("/api/status", params={"view": "alerts"})
    assert r.status_code == 200
    assert isinstance(r.json(), list)
    assert calls == [("alerts", main.runner.s.prometheus_url)]


def test_status_route_rejects_unknown_view():
    client = TestClient(main.app)
    assert client.get("/api/status", params={"view": "nope"}).status_code == 422


def _with_tenant(monkeypatch):
    monkeypatch.setitem(main.runner.s.tenants, "research", "k-research")
    return TestClient(main.app)


def test_ask_unknown_tenant_404():
    r = TestClient(main.app).post("/api/agent/ask", json={"tenant": "nobody", "question": "hi"})
    assert r.status_code == 404


def test_ask_long_question_422(monkeypatch):
    client = _with_tenant(monkeypatch)
    r = client.post("/api/agent/ask", json={"tenant": "research", "question": "x" * 501})
    assert r.status_code == 422


def test_ask_returns_agent_result(monkeypatch):
    from app import agent

    seen = {}

    async def fake_run(question, **kw):
        seen.update(question=question, key=kw["key"], no_cache=kw["no_cache"])
        return agent.AgentResult(answer="42", rounds=1, prompt_tokens=3, completion_tokens=2)

    monkeypatch.setattr(agent, "run_agent", fake_run)
    real = httpx.AsyncClient  # a client without a transport loads the system CA file, not needed here
    monkeypatch.setattr(main.httpx, "AsyncClient",
                        lambda **kw: real(transport=httpx.MockTransport(lambda r: httpx.Response(200))))
    client = _with_tenant(monkeypatch)
    r = client.post("/api/agent/ask", json={"tenant": "research", "question": "why?"})
    assert r.status_code == 200
    body = r.json()
    assert body["answer"] == "42" and body["rounds"] == 1
    assert set(body) == {"answer", "steps", "sources", "prompt_tokens", "completion_tokens", "latency_s",
                         "rounds"}
    assert seen == {"question": "why?", "key": "k-research", "no_cache": False}


def test_eval_result_is_404_before_the_first_run(monkeypatch):
    monkeypatch.setitem(main.eval_state, "latest", None)
    assert TestClient(main.app).get("/api/agent/eval").status_code == 404


def test_eval_start_unknown_tenant_404():
    assert TestClient(main.app).post("/api/agent/eval", json={"tenant": "nobody"}).status_code == 404


def test_eval_start_is_409_while_one_runs(monkeypatch):
    class Running:
        def done(self):
            return False

    monkeypatch.setitem(main.eval_state, "task", Running())
    client = _with_tenant(monkeypatch)
    assert client.post("/api/agent/eval", json={"tenant": "research"}).status_code == 409


async def test_eval_start_runs_the_job_in_the_background(monkeypatch):
    monkeypatch.setitem(main.eval_state, "task", None)
    seen = []

    async def fake_job(team, key):
        seen.append((team, key))

    monkeypatch.setattr(main, "run_eval_job", fake_job)
    monkeypatch.setitem(main.runner.s.tenants, "research", "k-research")
    assert await main.agent_eval(main.EvalBody(tenant="research")) == {"started": True}
    await main.eval_state["task"]
    assert seen == [("research", "k-research")]


def test_metrics_is_empty_then_filled(monkeypatch):
    client = TestClient(main.app)
    monkeypatch.setitem(main.eval_state, "latest", None)
    r = client.get("/metrics")
    assert r.status_code == 200 and r.text == "" and r.headers["content-type"].startswith("text/plain")
    monkeypatch.setitem(main.eval_state, "latest", {"finished": 1.0, "summary": {
        "hit_at_3": 0.9, "tool_accuracy": 1.0, "faithfulness": 0.8, "latency_p95_s": 3.5,
        "usd_per_1k_questions": 0.12}})
    assert "rag_eval_hit_at_3 0.9" in client.get("/metrics").text


def test_console_modules_log_at_info():
    import logging
    assert logging.getLogger("app.agent").isEnabledFor(logging.INFO)
    assert logging.getLogger("app.evaluate").isEnabledFor(logging.INFO)
