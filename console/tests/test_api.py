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
