"""Streaming load generator for an OpenAI-compatible gateway."""
from __future__ import annotations

import itertools
import json
import time
import uuid

import httpx

from .stats import RequestResult

BASE_TEXT = ("Explain in detail how a message queue works, which problems it solves and when "
             "it should not be used. ")
FIXED_TOPICS = [
    "message queues", "database indexes", "HTTP caching", "container orchestration",
    "rate limiting", "load balancing", "event sourcing", "circuit breakers",
]


def parse_sse_line(line: str) -> dict | str | None:
    """Parse one server-sent-events line: dict for a JSON chunk, 'DONE' for [DONE], else None."""
    if not line.startswith("data:"):
        return None
    payload = line[5:].strip()
    if payload == "[DONE]":
        return "DONE"
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        return None


_counter = itertools.count()


def make_prompt(shape: str, approx_words: int) -> str:
    """'unique' never repeats (gateway cache cannot hit); 'repeated' cycles over fixed prompts."""
    n = next(_counter)
    if shape == "repeated":
        topic = FIXED_TOPICS[n % len(FIXED_TOPICS)]
        return f"Explain {topic} in a short paragraph for a new engineer."
    filler = (BASE_TEXT * max(1, approx_words // 20)).strip()
    return f"[{uuid.uuid4().hex[:10]}] {filler}"


async def one_request(client: httpx.AsyncClient, base_url: str, key: str, model: str,
                      prompt: str, max_tokens: int) -> RequestResult:
    body = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0,
        "stream": True,
        "stream_options": {"include_usage": True},
    }
    t0 = time.perf_counter()
    first: float | None = None
    chunks = 0
    tokens = 0
    try:
        async with client.stream("POST", f"{base_url}/v1/chat/completions",
                                 headers={"Authorization": f"Bearer {key}"}, json=body) as resp:
            status = resp.status_code
            cached = "x-litellm-cache-key" in resp.headers
            if status != 200:
                await resp.aread()
                return RequestResult(False, status, time.perf_counter() - t0)
            async for line in resp.aiter_lines():
                obj = parse_sse_line(line)
                if obj is None or obj == "DONE":
                    continue
                choices = obj.get("choices") or []
                if choices:
                    delta = choices[0].get("delta") or {}
                    if first is None and (delta.get("content") or delta.get("reasoning_content")
                                          or delta.get("reasoning")):
                        first = time.perf_counter() - t0
                    chunks += 1
                usage = obj.get("usage")
                if usage and usage.get("completion_tokens") is not None:
                    tokens = int(usage["completion_tokens"])
            return RequestResult(True, 200, time.perf_counter() - t0, first, tokens or chunks, cached)
    except httpx.HTTPError:
        return RequestResult(False, 0, time.perf_counter() - t0)
