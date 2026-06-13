"""Post-eval Walrus pipeline tests."""

from __future__ import annotations

import os

import pytest

from goldenmcp_inspect.benchmarks import load_benchmark
from goldenmcp_inspect.manifest import build_manifest
from goldenmcp_inspect.pipeline import post_eval_walrus_upload
from goldenmcp_inspect.schemas import EvalTranscript, TranscriptEvent


def _sample_transcript() -> EvalTranscript:
    return EvalTranscript(
        mcp="lifi",
        capability="quote",
        events=[
            TranscriptEvent(kind="tool", tool_name="get-chains", content="{}"),
            TranscriptEvent(kind="tool", tool_name="get-tokens", content="{}"),
            TranscriptEvent(kind="tool", tool_name="get-quote", content='{"amount": 1}'),
        ],
        final_output={"amount": 1, "token": "USDC"},
        total_tokens=2000,
    )


def test_post_eval_builds_manifest_without_walrus():
    transcript = _sample_transcript()
    benchmark = load_benchmark("lifi", "quote")
    manifest = build_manifest(transcript, benchmark, run_id="test-run")
    assert manifest.mcp == "lifi"
    assert manifest.capability == "quote"
    assert manifest.composite > 0


@pytest.mark.skipif(
    not os.environ.get("WALRUS_PUBLISHER_URL") or not os.environ.get("WALRUS_AGGREGATOR_URL"),
    reason="WALRUS_PUBLISHER_URL and WALRUS_AGGREGATOR_URL required for live upload",
)
def test_post_eval_walrus_upload_integration():
    result = post_eval_walrus_upload(_sample_transcript(), run_id="integration-test")
    assert result.walrus_manifest_blob_id
    assert result.walrus_eval_blob_id
    assert result.manifest.composite >= 0
