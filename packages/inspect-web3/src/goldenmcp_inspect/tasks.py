"""Inspect AI task definitions for web3 MCP evaluation."""

from __future__ import annotations

import json
import logging
import os

from inspect_ai import Task, task
from inspect_ai.dataset import Sample
from inspect_ai.model import GenerateConfig
from inspect_ai.scorer import Scorer, Score, scorer
from inspect_ai.solver import generate, system_message, use_tools

from goldenmcp_inspect.benchmarks import load_benchmark
from goldenmcp_inspect.eval_chains import (
    JUPITER_POSITIONS_PROMPT,
    JUPITER_QUOTE_PROMPT,
    KYBERSWAP_QUOTE_PROMPT,
    KYBERSWAP_ROUTE_PROMPT,
    LIFI_QUOTE_PROMPT,
    LIFI_ROUTE_PROMPT,
    ODOS_QUOTE_PROMPT,
    ODOS_SWAP_PROMPT,
    ONEINCH_QUOTE_PROMPT,
    ONEINCH_SWAP_PROMPT,
    SYSTEM_PROMPT,
    UNISWAP_QUOTE_PROMPT,
    UNISWAP_SWAP_PROMPT,
)
from goldenmcp_inspect.mcp_connectors import build_mcp_server
from goldenmcp_inspect.schemas import EvalTranscript, TranscriptEvent
from goldenmcp_inspect.scorers import score_transcript

logger = logging.getLogger(__name__)


def _parse_json(text: str):
    """Parse a tool result into a dict for DataScore matching.

    Most servers return a JSON object. Some (e.g. @iqai/mcp-odos) return a
    human-formatted text blob with an embedded JSON object — recover the largest
    top-level `{...}` substring so keys like `outAmounts` are still matchable.
    """
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except (json.JSONDecodeError, TypeError):
        pass

    if not isinstance(text, str):
        return None
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        candidate = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
    return candidate if isinstance(candidate, dict) else None


def _make_transcript_scorer(mcp: str, capability: str) -> Scorer:
    benchmark = load_benchmark(mcp, capability)

    @scorer(metrics=[])
    def goldenmcp_scorer() -> Scorer:
        async def score(state, target):
            events = []
            structured: dict = {}
            for msg in state.messages:
                if hasattr(msg, "tool_calls") and msg.tool_calls:
                    for tc in msg.tool_calls:
                        events.append(
                            TranscriptEvent(
                                kind="tool",
                                tool_name=tc.function,
                                content=json.dumps(tc.arguments) if tc.arguments else "",
                            )
                        )
                # Merge structured tool *results* so DataScore can match expected_data
                # keys against real tool output (not just the completion text).
                if getattr(msg, "role", None) == "tool":
                    parsed = _parse_json(getattr(msg, "text", "") or "")
                    if isinstance(parsed, dict):
                        structured.update(parsed)

            # Cumulative tokens for the sample live on TaskState (sample.model_usage),
            # NOT on individual messages — reading per-message usage always yielded 0.
            total_tokens = getattr(state, "token_usage", 0) or 0

            output_text = state.output.completion if state.output else ""
            transcript = EvalTranscript(
                mcp=mcp,
                capability=capability,
                events=events,
                final_output={**structured, "text": output_text},
                total_tokens=total_tokens,
            )
            result = score_transcript(transcript, benchmark)
            explanation = json.dumps(result)
            value = result["composite"]
            return Score(value=value, explanation=explanation)

        return score

    return goldenmcp_scorer()


def _build_task(
    mcp: str,
    capability: str,
    prompt: str,
    *,
    require_wallet: bool = False,
) -> Task:
    benchmark = load_benchmark(mcp, capability)
    return Task(
        dataset=[Sample(input=prompt)],
        solver=[
            system_message(SYSTEM_PROMPT),
            use_tools(build_mcp_server(mcp, require_wallet=require_wallet)),
            generate(),
        ],
        scorer=_make_transcript_scorer(mcp, capability),
        config=_generate_config(),
        metadata={"mcp": mcp, "capability": capability, "benchmark": benchmark.model_dump()},
    )


def _generate_config() -> GenerateConfig:
    # Disable Anthropic prompt caching so token_efficiency reflects real usage and
    # stays comparable across the K=3 providers (no cache-read inflation).
    cfg = GenerateConfig(cache_prompt=False)
    # extra_body cannot be set via Inspect's CLI (--model-config / -M route to the
    # provider constructor), and chat_template_kwargs is rejected (HTTP 400) by the
    # Anthropic/Mistral endpoints — so it must be applied per-model, in-task, gated
    # on an env var the runner sets only for the Qwen invocation.
    if os.environ.get("GOLDENMCP_DISABLE_THINKING") == "1":
        cfg.extra_body = {"chat_template_kwargs": {"enable_thinking": False}}
    return cfg


@task
def lifi_quote():
    return _build_task("lifi", "quote", LIFI_QUOTE_PROMPT)


@task
def lifi_route():
    return _build_task("lifi", "route", LIFI_ROUTE_PROMPT)


@task
def odos_quote():
    return _build_task("odos", "quote", ODOS_QUOTE_PROMPT)


@task
def odos_swap():
    return _build_task(
        "odos",
        "swap",
        ODOS_SWAP_PROMPT,
        require_wallet=True,
    )


@task
def uniswap_quote():
    return _build_task("uniswap", "quote", UNISWAP_QUOTE_PROMPT)


@task
def uniswap_swap():
    return _build_task("uniswap", "swap", UNISWAP_SWAP_PROMPT)


@task
def oneinch_quote():
    return _build_task("1inch", "quote", ONEINCH_QUOTE_PROMPT)


@task
def oneinch_swap():
    return _build_task("1inch", "swap", ONEINCH_SWAP_PROMPT)


@task
def kyberswap_quote():
    return _build_task("kyberswap", "quote", KYBERSWAP_QUOTE_PROMPT)


@task
def kyberswap_route():
    return _build_task("kyberswap", "route", KYBERSWAP_ROUTE_PROMPT)


@task
def jupiter_quote():
    return _build_task("jupiter", "quote", JUPITER_QUOTE_PROMPT)


@task
def jupiter_positions():
    return _build_task("jupiter", "positions", JUPITER_POSITIONS_PROMPT)
