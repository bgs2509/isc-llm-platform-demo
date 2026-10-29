"""The tool-calling loop: answer one question with two tools through the gateway.

PURPOSE: answer one question with the tools `search_docs` and `platform_status` through the gateway.
INPUTS: `question`, an `httpx.AsyncClient`, gateway URL, model, team key, team name (for the log), a `search`
    callable (query -> list of {title, url, text}), an async `status` callable (view -> list | dict),
    `no_cache` (True in evaluation: every request carries `"cache": {"no-cache": true}`; `ask` sends no
    `cache` field and keeps the gateway cache).
OUTPUTS: `AgentResult(answer, steps=[{tool, args, result}], sources=[{title, url}] deduplicated from search
    hits, prompt_tokens, completion_tokens summed over all replies, latency_s, rounds)`.
Limits: at most MAX_ROUNDS tool rounds, then the request goes without `tools` so the model must answer;
    `temperature 0`; thinking off (`chat_template_kwargs.enable_thinking=false`, verified in task 0).
    The model's tool arguments are untrusted: bad JSON or a wrong view becomes {"error": ...} as the tool result.
DEPENDS: `httpx`; the caller supplies `search` (`corpus.Index.search`) and `status` (`platform_status.fetch`).
Logs: `[Agent][ask][TOOL_CALL]` per call (tool name only) and `[Agent][ask][ANSWER]` with team, rounds, tokens,
    latency - no question text, no key.
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass, field
from typing import Awaitable, Callable

import httpx

log = logging.getLogger(__name__)

MAX_ROUNDS = 3
MAX_TOKENS = 600
SYSTEM_PROMPT = (
    "You answer questions about the blog of the company (search_docs) and about the running LLM platform "
    "(platform_status). Call a tool to get facts, then answer briefly from the tool results only. "
    "If a tool result has an error or does not contain the answer, say so."
)
TOOLS = [
    {"type": "function", "function": {
        "name": "search_docs", "description": "Search the company blog; returns the 3 best passages.",
        "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
    {"type": "function", "function": {
        "name": "platform_status",
        "description": "Current state of the platform: alerts (rule, state, value) or teams (traffic per team).",
        "parameters": {"type": "object", "properties": {"view": {"type": "string", "enum": ["alerts", "teams"]}},
                       "required": ["view"]}}},
]
STATUS_VIEWS = ("alerts", "teams")


@dataclass
class AgentResult:
    answer: str
    steps: list[dict] = field(default_factory=list)
    sources: list[dict] = field(default_factory=list)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_s: float = 0.0
    rounds: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


async def _call_tool(name: str, raw_args: str, search: Callable, status: Callable[[str], Awaitable]):
    """Run one tool; returns (parsed args, result). Never raises on model input."""
    try:
        args = json.loads(raw_args or "{}")
        if not isinstance(args, dict):
            raise ValueError("arguments must be an object")
    except ValueError:
        return {}, {"error": "arguments are not valid JSON"}
    if name == "search_docs":
        query = args.get("query")
        if not isinstance(query, str) or not query.strip():
            return args, {"error": "query must be a non-empty string"}
        return args, search(query)
    if name == "platform_status":
        if args.get("view") not in STATUS_VIEWS:
            return args, {"error": f"view must be one of {', '.join(STATUS_VIEWS)}"}
        return args, await status(args["view"])
    return args, {"error": f"unknown tool {name!r}"}


async def run_agent(question: str, *, client: httpx.AsyncClient, gateway_url: str, model: str, key: str,
                    team: str, search: Callable, status: Callable[[str], Awaitable],
                    no_cache: bool = False) -> AgentResult:
    started = time.monotonic()
    messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": question}]
    result = AgentResult(answer="")
    seen_urls: set[str] = set()
    while True:
        body: dict = {"model": model, "messages": messages, "temperature": 0, "max_tokens": MAX_TOKENS,
                      "chat_template_kwargs": {"enable_thinking": False}}
        if result.rounds < MAX_ROUNDS:
            body["tools"] = TOOLS
        if no_cache:
            body["cache"] = {"no-cache": True}
        r = await client.post(f"{gateway_url.rstrip('/')}/v1/chat/completions", json=body,
                              headers={"Authorization": f"Bearer {key}"})
        r.raise_for_status()
        data = r.json()
        usage = data.get("usage") or {}
        result.prompt_tokens += usage.get("prompt_tokens", 0)
        result.completion_tokens += usage.get("completion_tokens", 0)
        message = data["choices"][0]["message"]
        calls = message.get("tool_calls") or []
        if not calls or "tools" not in body:
            result.answer = message.get("content") or ""
            break
        result.rounds += 1
        messages.append({"role": "assistant", "content": message.get("content") or "", "tool_calls": calls})
        for call in calls:
            name = call["function"]["name"]
            log.info("[Agent][ask][TOOL_CALL] tool=%s", name)
            args, out = await _call_tool(name, call["function"].get("arguments", ""), search, status)
            result.steps.append({"tool": name, "args": args, "result": out})
            if name == "search_docs" and isinstance(out, list):
                for hit in out:
                    if hit["url"] not in seen_urls:
                        seen_urls.add(hit["url"])
                        result.sources.append({"title": hit["title"], "url": hit["url"]})
            messages.append({"role": "tool", "tool_call_id": call["id"], "content": json.dumps(out)})
    result.latency_s = time.monotonic() - started
    log.info("[Agent][ask][ANSWER] team=%s rounds=%d prompt_tokens=%d completion_tokens=%d latency_s=%.2f",
             team, result.rounds, result.prompt_tokens, result.completion_tokens, result.latency_s)
    return result
