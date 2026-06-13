"""Post-eval pipeline tests for indexed Walrus inspect logs."""

from __future__ import annotations

import json
import os

import pytest

from goldenmcp_walrus.testing import InMemoryWalrusClient
from goldenmcp_inspect.pipeline import post_eval_from_inspect_log, post_eval_walrus_upload, upload_inspect_log_bytes
from goldenmcp_inspect.schemas import EvalTranscript, TranscriptEvent
from goldenmcp_inspect.walrus_paths import inspect_eval_log_path
from goldenmcp_walrus.filesystem import WalrusFileSystem
from goldenmcp_walrus.index import WalrusIndex


def _sample_inspect_log() -> dict:
    return {
        "samples": [
            {
                "events": [
                    {
                        "event": "tool",
                        "tool_call": {"function": "get-quote", "arguments": "{}"},
                    }
                ],
                "output": {"amount": 1},
            }
        ]
    }


def _sample_transcript() -> EvalTranscript:
    return EvalTranscript(
        mcp="lifi",
        capability="quote",
        events=[
            TranscriptEvent(kind="tool", tool_name="get-chains", content="{}"),
            TranscriptEvent(kind="tool", tool_name="get-quote", content='{"amount": 1}'),
        ],
        final_output={"amount": 1, "token": "USDC"},
        total_tokens=2000,
    )


def test_upload_inspect_log_bytes_registers_indexed_path():
    client = InMemoryWalrusClient()
    fs = WalrusFileSystem(client=client, index=WalrusIndex())
    path = inspect_eval_log_path("lifi", "quote", run_id="unit")
    payload = b'{"eval":"log"}'

    walrus_path, used_fs = upload_inspect_log_bytes(payload, path, filesystem=fs)

    assert walrus_path == path
    assert used_fs.cat_file(path) == payload
    assert used_fs.index.index_blob_id is not None
    listing = used_fs.ls("walrus://evals/goldenmcp", detail=False)
    assert path in listing


def test_post_eval_from_inspect_log_uploads_raw_bytes():
    client = InMemoryWalrusClient()
    fs = WalrusFileSystem(client=client, index=WalrusIndex())
    raw = json.dumps(_sample_inspect_log()).encode()

    result = post_eval_from_inspect_log(
        _sample_inspect_log(),
        "lifi",
        "quote",
        run_id="json-run",
        inspect_log_bytes=raw,
        filesystem=fs,
        walrus=client,
    )

    assert result.walrus_eval_blob_id.startswith("walrus://evals/goldenmcp/")
    assert result.walrus_index_blob_id is not None
    assert fs.cat_file(result.walrus_eval_blob_id) == raw


def test_post_eval_walrus_upload_synthesizes_log_when_bytes_missing():
    client = InMemoryWalrusClient()
    fs = WalrusFileSystem(client=client, index=WalrusIndex())

    result = post_eval_walrus_upload(
        _sample_transcript(),
        run_id="synth-run",
        filesystem=fs,
        walrus=client,
    )

    assert result.walrus_eval_blob_id.startswith("walrus://evals/goldenmcp/")
    assert result.walrus_index_blob_id is not None
    assert b'"samples"' in fs.cat_file(result.walrus_eval_blob_id)


@pytest.mark.skipif(
    not os.environ.get("WALRUS_PUBLISHER_URL") or not os.environ.get("WALRUS_AGGREGATOR_URL"),
    reason="WALRUS env required for live index integration",
)
def test_live_walrus_index_lists_uploaded_inspect_log(monkeypatch):
    from inspect_ai.log import list_eval_logs

    fs = WalrusFileSystem()
    path = inspect_eval_log_path("lifi", "quote", run_id="inspect-view-live")
    payload = b'{"status":"success","samples":[]}'

    _, used_fs = upload_inspect_log_bytes(payload, path, filesystem=fs)
    assert used_fs.index.index_blob_id
    monkeypatch.setenv("WALRUS_INDEX_BLOB_ID", used_fs.index.index_blob_id)

    logs = list_eval_logs("walrus://evals/goldenmcp")
    names = [log.name for log in logs]
    assert path in names
