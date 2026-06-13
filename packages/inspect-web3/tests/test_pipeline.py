"""Post-eval Walrus pipeline tests."""

from __future__ import annotations

import os

import pytest

from goldenmcp_inspect.benchmarks import load_benchmark
from goldenmcp_inspect.manifest import build_manifest
from goldenmcp_walrus.testing import InMemoryWalrusClient
from goldenmcp_walrus.filesystem import WalrusFileSystem
from goldenmcp_walrus.index import WalrusIndex

from goldenmcp_inspect.pipeline import (
    post_eval_walrus_upload,
    publish_manifest_to_walrus,
    score_transcript_to_manifest,
)
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


def test_score_transcript_to_manifest_has_no_walrus_ids():
    manifest = score_transcript_to_manifest(_sample_transcript(), run_id="score-only")
    assert manifest.mcp == "lifi"
    assert manifest.capability == "quote"
    assert manifest.run_id == "score-only"
    assert manifest.composite > 0
    assert manifest.walrus_blob_id is None
    assert manifest.walrus_manifest_blob_id is None


def test_publish_manifest_to_walrus_sets_blob_ids():
    transcript = _sample_transcript()
    manifest = score_transcript_to_manifest(transcript, run_id="publish-unit")
    client = InMemoryWalrusClient()
    fs = WalrusFileSystem(client=client, index=WalrusIndex())

    result = publish_manifest_to_walrus(
        manifest,
        transcript=transcript,
        walrus=client,
        filesystem=fs,
    )

    assert result.manifest.walrus_blob_id
    assert result.manifest.walrus_manifest_blob_id
    assert result.walrus_manifest_blob_id == result.manifest.walrus_manifest_blob_id
    assert result.walrus_eval_blob_id == result.manifest.walrus_blob_id


def test_post_eval_walrus_upload_delegates_to_score_and_publish():
    client = InMemoryWalrusClient()
    fs = WalrusFileSystem(client=client, index=WalrusIndex())
    result = post_eval_walrus_upload(
        _sample_transcript(),
        run_id="compat-run",
        walrus=client,
        filesystem=fs,
    )
    assert result.walrus_manifest_blob_id
    assert result.manifest.walrus_blob_id


@pytest.mark.skipif(
    not os.environ.get("WALRUS_PUBLISHER_URL") or not os.environ.get("WALRUS_AGGREGATOR_URL"),
    reason="WALRUS_PUBLISHER_URL and WALRUS_AGGREGATOR_URL required for live upload",
)
def test_post_eval_walrus_upload_integration():
    result = post_eval_walrus_upload(_sample_transcript(), run_id="integration-test")
    assert result.walrus_manifest_blob_id
    assert result.walrus_eval_blob_id
    assert result.manifest.composite >= 0
