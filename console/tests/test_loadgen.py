import json

import httpx

from app.loadgen import make_prompt, one_request, parse_sse_line


def test_parse_sse_line():
    assert parse_sse_line("data: [DONE]") == "DONE"
    assert parse_sse_line(': keep-alive') is None
    assert parse_sse_line('data: {"a": 1}') == {"a": 1}
    assert parse_sse_line("data: {broken") is None


def test_prompts_unique_vs_repeated():
    unique = {make_prompt("unique", 40) for _ in range(20)}
    repeated = {make_prompt("repeated", 40) for _ in range(40)}
    assert len(unique) == 20
    assert len(repeated) <= 8


def _sse(chunks: list[dict]) -> bytes:
    lines = [f"data: {json.dumps(c)}\n\n" for c in chunks] + ["data: [DONE]\n\n"]
    return "".join(lines).encode()


async def test_one_request_measures_ttft_and_tokens():
    chunks = [
        {"choices": [{"delta": {"role": "assistant"}}]},
        {"choices": [{"delta": {"content": "Hel"}}]},
        {"choices": [{"delta": {"content": "lo"}}]},
        {"choices": [], "usage": {"completion_tokens": 7}},
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer sk-test"
        return httpx.Response(200, content=_sse(chunks), headers={"x-litellm-cache-key": "abc"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        r = await one_request(client, "http://gw", "sk-test", "m", "hi", 16)
    assert r.ok and r.completion_tokens == 7 and r.cached
    assert r.ttft_s is not None and r.ttft_s <= r.total_s


async def test_one_request_reports_http_error_status():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": "rate limited"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        r = await one_request(client, "http://gw", "k", "m", "hi", 16)
    assert not r.ok and r.status == 429
