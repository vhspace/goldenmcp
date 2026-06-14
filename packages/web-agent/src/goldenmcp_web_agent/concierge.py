"""Streaming concierge chat loop (Anthropic + marketplace tools)."""

from __future__ import annotations

import json
import logging
import os
from collections.abc import AsyncIterator
from typing import Any

from anthropic import AsyncAnthropic

from goldenmcp_web_agent.agent import CONCIERGE_SYSTEM_PROMPT
from goldenmcp_web_agent.concierge_tools import anthropic_tool_definitions, execute_tool
from goldenmcp_web_agent.settings import WebAgentSettings, get_settings

logger = logging.getLogger(__name__)

MAX_TOOL_ROUNDS = 8


def _anthropic_client(settings: WebAgentSettings) -> AsyncAnthropic:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise EnvironmentError("ANTHROPIC_API_KEY is not set — required for concierge chat.")
    base_url = os.environ.get("ANTHROPIC_BASE_URL")
    if base_url and os.environ.get("DO_INFERENCE_KEY"):
        return AsyncAnthropic(api_key=os.environ["DO_INFERENCE_KEY"], base_url=base_url)
    return AsyncAnthropic(api_key=api_key)


def _model_id(settings: WebAgentSettings) -> str:
    raw = settings.web_agent_model
    if raw.startswith("anthropic/"):
        return raw.removeprefix("anthropic/")
    return raw


def _normalize_history(history: list[dict[str, str]] | None) -> list[dict[str, Any]]:
    if not history:
        return []
    out: list[dict[str, Any]] = []
    for item in history:
        role = item.get("role")
        content = item.get("content", "")
        if role in ("user", "assistant") and content:
            out.append({"role": role, "content": content})
    return out


MAX_TOOL_RESULT_CHARS = 12_000


def _truncate_tool_result(result: str) -> str:
    if len(result) <= MAX_TOOL_RESULT_CHARS:
        return result
    return result[: MAX_TOOL_RESULT_CHARS - 3] + "..."


async def stream_chat(
    message: str,
    history: list[dict[str, str]] | None = None,
    *,
    settings: WebAgentSettings | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """Yield SSE-friendly event dicts: token, tool_start, tool_end, error, done."""
    settings = settings or get_settings()
    client = _anthropic_client(settings)
    model = _model_id(settings)
    tools = anthropic_tool_definitions()

    messages: list[dict[str, Any]] = _normalize_history(history)
    messages.append({"role": "user", "content": message})

    for round_idx in range(MAX_TOOL_ROUNDS):
        logger.info("concierge round=%s model=%s", round_idx, model)

        collected_text = ""
        tool_uses: list[dict[str, Any]] = []

        async with client.messages.stream(
            model=model,
            max_tokens=4096,
            system=CONCIERGE_SYSTEM_PROMPT,
            tools=tools,
            messages=messages,
        ) as stream:
            async for event in stream:
                if event.type == "content_block_start":
                    block = event.content_block
                    if block.type == "tool_use":
                        yield {
                            "event": "tool_start",
                            "data": {"name": block.name, "id": block.id},
                        }
                elif event.type == "content_block_delta":
                    delta = event.delta
                    if delta.type == "text_delta" and delta.text:
                        collected_text += delta.text
                        yield {"event": "token", "data": {"text": delta.text}}
                elif event.type == "content_block_stop":
                    pass

            response = await stream.get_final_message()

        for block in response.content:
            if block.type == "tool_use":
                tool_uses.append(
                    {"id": block.id, "name": block.name, "input": block.input},
                )

        if not tool_uses:
            yield {"event": "done", "data": {"text": collected_text}}
            return

        assistant_content = []
        for block in response.content:
            if block.type == "text":
                assistant_content.append({"type": "text", "text": block.text})
            elif block.type == "tool_use":
                assistant_content.append(
                    {
                        "type": "tool_use",
                        "id": block.id,
                        "name": block.name,
                        "input": block.input,
                    }
                )
        messages.append({"role": "assistant", "content": assistant_content})

        tool_results = []
        for tu in tool_uses:
            try:
                result = await execute_tool(tu["name"], tu["input"])
                is_error = False
            except Exception as exc:
                logger.exception("tool %s failed", tu["name"])
                result = json.dumps({"error": str(exc)})
                is_error = True
                yield {"event": "error", "data": {"tool": tu["name"], "message": str(exc)}}

            result = _truncate_tool_result(result)
            yield {
                "event": "tool_end",
                "data": {
                    "name": tu["name"],
                    "id": tu["id"],
                    "result": result,
                    "is_error": is_error,
                },
            }
            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": tu["id"],
                    "content": result,
                    "is_error": is_error,
                }
            )

        messages.append({"role": "user", "content": tool_results})

    yield {
        "event": "error",
        "data": {"message": f"exceeded max tool rounds ({MAX_TOOL_ROUNDS})"},
    }
    yield {"event": "done", "data": {}}
