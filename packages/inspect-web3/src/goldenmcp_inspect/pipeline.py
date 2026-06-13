"""Post-eval pipeline: score transcript and persist manifest to Walrus."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from goldenmcp_inspect.benchmarks import load_benchmark
from goldenmcp_inspect.manifest import (
    build_manifest,
    manifest_to_json,
    synthesize_inspect_log_bytes,
    transcript_from_inspect_log,
)
from goldenmcp_inspect.schemas import EvalTranscript, ScoreManifest
from goldenmcp_inspect.walrus_paths import inspect_eval_log_path
from goldenmcp_walrus import WalrusClient, WalrusFileSystem

logger = logging.getLogger(__name__)


class WalrusUploadResult:
    def __init__(
        self,
        manifest: ScoreManifest,
        walrus_manifest_blob_id: str,
        walrus_eval_blob_id: str,
        walrus_index_blob_id: str | None = None,
    ):
        self.manifest = manifest
        self.walrus_manifest_blob_id = walrus_manifest_blob_id
        self.walrus_eval_blob_id = walrus_eval_blob_id
        self.walrus_index_blob_id = walrus_index_blob_id


def upload_inspect_log_bytes(
    payload: bytes,
    walrus_path: str,
    *,
    filesystem: WalrusFileSystem | None = None,
) -> tuple[str, WalrusFileSystem]:
    """Store raw Inspect log bytes at an indexed walrus:// path for Inspect View listing."""
    fs = filesystem or WalrusFileSystem()
    fs.pipe_file(walrus_path, payload)
    logger.info(
        "upload_inspect_log_bytes path=%s size=%d index_blob=%s",
        walrus_path,
        len(payload),
        fs.index.index_blob_id,
    )
    return walrus_path, fs


def score_transcript_to_manifest(
    transcript: EvalTranscript,
    *,
    run_id: str | None = None,
) -> ScoreManifest:
    """Score transcript and build manifest without Walrus upload."""
    benchmark = load_benchmark(transcript.mcp, transcript.capability)
    return build_manifest(transcript, benchmark, run_id=run_id)


def publish_manifest_to_walrus(
    manifest: ScoreManifest,
    *,
    transcript: EvalTranscript | None = None,
    walrus: WalrusClient | None = None,
    inspect_log_bytes: bytes | None = None,
    inspect_log_path: str | None = None,
    filesystem: WalrusFileSystem | None = None,
) -> WalrusUploadResult:
    """Upload Inspect eval log bytes and public manifest JSON to Walrus."""
    eval_walrus_path = inspect_log_path or inspect_eval_log_path(
        manifest.mcp,
        manifest.capability,
        run_id=manifest.run_id,
        created_at=manifest.created_at,
    )

    if inspect_log_bytes is not None:
        log_bytes = inspect_log_bytes
    elif transcript is not None:
        log_bytes = synthesize_inspect_log_bytes(transcript, manifest)
    else:
        log_bytes = manifest_to_json(manifest).encode()

    _, fs = upload_inspect_log_bytes(log_bytes, eval_walrus_path, filesystem=filesystem)
    manifest.walrus_blob_id = eval_walrus_path

    client = walrus or WalrusClient()
    manifest.walrus_manifest_blob_id = client.upload_json(manifest.to_public_dict())
    manifest_blob_id = manifest.walrus_manifest_blob_id

    logger.info(
        "publish_manifest_to_walrus mcp=%s capability=%s manifest_blob=%s eval_path=%s index_blob=%s composite=%.4f failed=%s",
        manifest.mcp,
        manifest.capability,
        manifest_blob_id,
        eval_walrus_path,
        fs.index.index_blob_id,
        manifest.composite,
        manifest.failed,
    )
    return WalrusUploadResult(
        manifest=manifest,
        walrus_manifest_blob_id=manifest_blob_id,
        walrus_eval_blob_id=eval_walrus_path,
        walrus_index_blob_id=fs.index.index_blob_id,
    )


def post_eval_walrus_upload(
    transcript: EvalTranscript,
    *,
    run_id: str | None = None,
    walrus: WalrusClient | None = None,
    inspect_log_bytes: bytes | None = None,
    inspect_log_path: str | None = None,
    filesystem: WalrusFileSystem | None = None,
) -> WalrusUploadResult:
    """Score transcript, upload Inspect log + score manifest to Walrus."""
    manifest = score_transcript_to_manifest(transcript, run_id=run_id)
    return publish_manifest_to_walrus(
        manifest,
        transcript=transcript,
        walrus=walrus,
        inspect_log_bytes=inspect_log_bytes,
        inspect_log_path=inspect_log_path,
        filesystem=filesystem,
    )


def post_eval_from_inspect_log(
    log_data: dict[str, Any],
    mcp: str,
    capability: str,
    *,
    run_id: str | None = None,
    walrus: WalrusClient | None = None,
    inspect_log_bytes: bytes | None = None,
    filesystem: WalrusFileSystem | None = None,
) -> WalrusUploadResult:
    """Parse Inspect eval log JSON and upload scores + raw log to Walrus."""
    transcript = transcript_from_inspect_log(log_data, mcp, capability)
    return post_eval_walrus_upload(
        transcript,
        run_id=run_id,
        walrus=walrus,
        inspect_log_bytes=inspect_log_bytes,
        filesystem=filesystem,
    )


def post_eval_from_log_file(
    log_path: str,
    mcp: str,
    capability: str,
    *,
    run_id: str | None = None,
) -> WalrusUploadResult:
    """Load Inspect log file and upload raw bytes + score manifest to Walrus."""
    raw = Path(log_path).read_bytes()
    if log_path.endswith(".json"):
        log_data = json.loads(raw.decode())
    else:
        from inspect_ai.log import read_eval_log

        eval_log = read_eval_log(log_path)
        log_data = json.loads(json.dumps(eval_log.model_dump(mode="json")))
    return post_eval_from_inspect_log(
        log_data,
        mcp,
        capability,
        run_id=run_id,
        inspect_log_bytes=raw,
    )
