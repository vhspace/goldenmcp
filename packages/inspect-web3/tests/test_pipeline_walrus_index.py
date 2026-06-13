"""Post-eval pipeline tests for indexed Walrus inspect logs."""

from __future__ import annotations

import json
import os

import pytest

from goldenmcp_inspect.pipeline import post_eval_from_inspect_log, upload_inspect_log_bytes
from goldenmcp_inspect.schemas import EvalTranscript, TranscriptEvent
from goldenmcp_inspect.walrus_paths import inspect_eval_log_path
from goldenmcp_walrus import WalrusClient, WalrusFileSystem
from goldenmcp_walrus.index import WalrusIndex


class InMemoryWalrusClient(WalrusClient):
    def __init__(self) -> None:
        super().__init__(publisher_url="http://memory", aggregator_url="http://memory")
        self.blobs: dict[str, bytes] = {}

    def upload(self, data: bytes, *, content_type: str = "application/octet-stream") -> str:
        blob_id = f"mem-{len(self.blobs)}"
        self.blobs[blob_id] = data
        return blob_id

    def download(self, blob_id: str) -> bytes:
        return self.blobs[blob_id]


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


def test_upload_inspect_log_bytes_registers_indexed_path():
    client = InMemoryWalrusClient()
    fs = WalrusFileSystem(client=client, index=WalrusIndex())
    path = inspect_eval_log_path("lifi", "quote", run_id="unit")
    payload = b'{"eval":"log"}'

    walrus_path = upload_inspect_log_bytes(payload, path, filesystem=fs)

    assert walrus_path == path
    assert fs.cat_file(path) == payload
    listing = fs.ls("walrus://evals/goldenmcp", detail=False)
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
    assert fs.cat_file(result.walrus_eval_blob_id) == raw


@pytest.mark.skipif(
    not os.environ.get("WALRUS_PUBLISHER_URL") or not os.environ.get("WALRUS_AGGREGATOR_URL"),
    reason="WALRUS env required for live index integration",
)
def test_live_walrus_index_lists_uploaded_inspect_log():
    from inspect_ai.log import list_eval_logs

    fs = WalrusFileSystem()
    path = inspect_eval_log_path("lifi", "quote", run_id="inspect-view-live")
    payload = b'{"status":"success","samples":[]}'

    upload_inspect_log_bytes(payload, path, filesystem=fs)
    assert fs.index.index_blob_id
    os.environ["WALRUS_INDEX_BLOB_ID"] = fs.index.index_blob_id

    logs = list_eval_logs("walrus://evals/goldenmcp")
    names = [log.name for log in logs]
    assert path in names
