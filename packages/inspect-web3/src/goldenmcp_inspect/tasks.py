"""Inspect AI task definitions for web3 MCP evaluation."""

from __future__ import annotations

import json
import logging

from inspect_ai import Task, task
from inspect_ai.dataset import Sample
from inspect_ai.scorer import Scorer, Score, scorer
from inspect_ai.solver import generate, use_tools

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
    UNISWAP_QUOTE_PROMPT,
    UNISWAP_SWAP_PROMPT,
)
from goldenmcp_inspect.mcp_connectors import build_mcp_server
from goldenmcp_inspect.schemas import EvalTranscript, TranscriptEvent
from goldenmcp_inspect.scorers import score_transcript

logger = logging.getLogger(__name__)


def _make_transcript_scorer(mcp: str, capability: str) -> Scorer:
    benchmark = load_benchmark(mcp, capability)

    @scorer(metrics=[])
    def goldenmcp_scorer() -> Scorer:
        async def score(state, target):
            events = []
            total_tokens = 0
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
                if hasattr(msg, "usage") and msg.usage:
                    total_tokens += getattr(msg.usage, "total_tokens", 0) or 0

            output_text = state.output.completion if state.output else ""
            transcript = EvalTranscript(
                mcp=mcp,
                capability=capability,
                events=events,
                final_output={"text": output_text},
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
            use_tools(build_mcp_server(mcp, require_wallet=require_wallet)),
            generate(),
        ],
        scorer=_make_transcript_scorer(mcp, capability),
        metadata={"mcp": mcp, "capability": capability, "benchmark": benchmark.model_dump()},
    )


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
