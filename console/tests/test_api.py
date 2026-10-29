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
    client = _with_tenant(monkeypatch)
    r = client.post("/api/agent/ask", json={"tenant": "research", "question": "why?"})
    assert r.status_code == 200
    body = r.json()
    assert body["answer"] == "42" and body["rounds"] == 1
    assert set(body) == {"answer", "steps", "sources", "prompt_tokens", "completion_tokens", "latency_s",
                         "rounds"}
    assert seen == {"question": "why?", "key": "k-research", "no_cache": False}
