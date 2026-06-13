"""Inspect AI task definitions for web3 MCP evaluation."""

from __future__ import annotations

import json
import logging
import os
import uuid

from inspect_ai import Task, task
from inspect_ai.dataset import Sample
from inspect_ai.scorer import Scorer, Score, scorer
from inspect_ai.solver import generate, use_tools
from inspect_ai.tool import mcp_server_http

from goldenmcp_inspect.benchmarks import load_benchmark
from goldenmcp_inspect.manifest import build_manifest, manifest_to_json
from goldenmcp_inspect.schemas import EvalTranscript, TranscriptEvent
from goldenmcp_inspect.scorers import score_transcript

logger = logging.getLogger(__name__)

MCP_URLS = {
    "lifi": os.environ.get("LIFI_MCP_URL", ""),
    "0x": os.environ.get("ZEROX_MCP_URL", ""),
    "uniswap": os.environ.get("UNISWAP_MCP_URL", ""),
}


def _require_mcp_url(vendor: str) -> str:
    url = MCP_URLS.get(vendor, "")
    if not url:
        raise EnvironmentError(
            f"{vendor.upper()}_MCP_URL is not set. "
            f"Set the live MCP endpoint in .env — no mock fallback."
        )
    return url


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


def _build_task(mcp: str, capability: str, prompt: str) -> Task:
    benchmark = load_benchmark(mcp, capability)
    url = _require_mcp_url(mcp)
    return Task(
        dataset=[Sample(input=prompt)],
        solver=[
            use_tools(mcp_server_http(url=url, name=f"{mcp}-mcp")),
            generate(),
        ],
        scorer=_make_transcript_scorer(mcp, capability),
        metadata={"mcp": mcp, "capability": capability, "benchmark": benchmark.model_dump()},
    )


@task
def lifi_quote():
    return _build_task(
        "lifi",
        "quote",
        "Use the LI.FI MCP to get a quote for swapping 1 ETH to USDC on Ethereum mainnet. "
        "Follow: get_chains, get_tokens, get_quote. Return the quote details.",
    )


@task
def lifi_route():
    return _build_task(
        "lifi",
        "route",
        "Use the LI.FI MCP to find the best route for 1 ETH to USDC. "
        "Follow: get_chains, get_routes, get_best_route.",
    )


@task
def zerox_quote():
    return _build_task("0x", "quote", "Use the 0x MCP to get a price quote for ETH to USDC.")


@task
def zerox_trade():
    return _build_task(
        "0x",
        "trade",
        "Use the 0x MCP to get a quote and submit a trade for a small ETH to USDC swap on testnet.",
    )


@task
def uniswap_quote():
    return _build_task("uniswap", "quote", "Use the Uniswap MCP to quote ETH to USDC.")


@task
def uniswap_swap():
    return _build_task(
        "uniswap",
        "swap",
        "Use the Uniswap MCP to quote and execute a small ETH to USDC swap on testnet.",
    )
