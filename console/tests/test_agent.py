import json

import httpx

from app.agent import run_agent


def _tool_reply(name, arguments, tokens=(10, 5)):
    args = arguments if isinstance(arguments, str) else json.dumps(arguments)
    return {"choices": [{"finish_reason": "tool_calls", "message": {"content": "", "tool_calls": [
        {"id": "c1", "type": "function", "function": {"name": name, "arguments": args}}]}}],
        "usage": {"prompt_tokens": tokens[0], "completion_tokens": tokens[1]}}


def _answer(text="done", tokens=(20, 7)):
    return {"choices": [{"finish_reason": "stop", "message": {"content": text}}],
            "usage": {"prompt_tokens": tokens[0], "completion_tokens": tokens[1]}}


class Gateway:
    """Scripted gateway: replays replies in order (the last one repeats) and records every request body."""

    def __init__(self, replies):
        self.replies, self.bodies = list(replies), []

    def client(self):
        def handler(request: httpx.Request) -> httpx.Response:
            self.bodies.append(json.loads(request.content))
            return httpx.Response(200, json=self.replies.pop(0) if len(self.replies) > 1 else self.replies[0])
        return httpx.AsyncClient(transport=httpx.MockTransport(handler))


HITS = [{"title": "A", "url": "https://x/a", "text": "t1"}, {"title": "A", "url": "https://x/a", "text": "t2"},
        {"title": "B", "url": "https://x/b", "text": "t3"}]


async def _run(gw, status=None, **kw):
    async def no_status(view):
        return []
    return await run_agent("q?", client=gw.client(), gateway_url="http://gw", model="m", key="k",
                           team="research", search=lambda q: HITS, status=status or no_status, **kw)


async def test_search_then_answer():
    gw = Gateway([_tool_reply("search_docs", {"query": "cost"}), _answer("final")])
    r = await _run(gw)
    assert r.answer == "final"
    assert [s["tool"] for s in r.steps] == ["search_docs"]
    assert r.steps[0]["args"] == {"query": "cost"}
    assert r.sources == [{"title": "A", "url": "https://x/a"}, {"title": "B", "url": "https://x/b"}]
    assert (r.prompt_tokens, r.completion_tokens, r.rounds) == (30, 12, 1)


async def test_status_tool_receives_the_view():
    seen = []

    async def status(view):
        seen.append(view)
        return [{"name": "A"}]

    gw = Gateway([_tool_reply("platform_status", {"view": "alerts"}), _answer()])
    r = await _run(gw, status=status)
    assert seen == ["alerts"]
    assert r.steps[0]["result"] == [{"name": "A"}]


async def test_three_rounds_then_no_tools():
    gw = Gateway([_tool_reply("search_docs", {"query": "x"})] * 3 + [_answer("forced")])
    r = await _run(gw)
    assert r.rounds == 3 and r.answer == "forced"
    assert all("tools" in b for b in gw.bodies[:3])
    assert "tools" not in gw.bodies[3]


async def test_malformed_arguments_become_error_results():
    gw = Gateway([_tool_reply("search_docs", "{broken"), _tool_reply("platform_status", {"view": "nope"}),
                  _answer()])
    r = await _run(gw)
    assert "error" in r.steps[0]["result"] and "error" in r.steps[1]["result"]
    assert r.answer == "done"


async def test_every_request_is_deterministic_without_thinking():
    gw = Gateway([_tool_reply("search_docs", {"query": "x"}), _answer()])
    await _run(gw)
    for b in gw.bodies:
        assert b["temperature"] == 0
        assert b["chat_template_kwargs"] == {"enable_thinking": False}


async def test_no_cache_flag_controls_the_cache_field():
    gw = Gateway([_tool_reply("search_docs", {"query": "x"}), _answer()])
    await _run(gw, no_cache=True)
    assert all(b["cache"] == {"no-cache": True} for b in gw.bodies)
    gw = Gateway([_answer()])
    await _run(gw)
    assert all("cache" not in b for b in gw.bodies)
