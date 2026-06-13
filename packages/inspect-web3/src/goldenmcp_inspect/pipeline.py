"""Post-eval pipeline: score transcript and persist manifest to Walrus."""

from __future__ import annotations

import json
import logging
from typing import Any

from goldenmcp_inspect.benchmarks import load_benchmark
from goldenmcp_inspect.manifest import build_manifest, manifest_to_json
from goldenmcp_inspect.schemas import EvalTranscript, ScoreManifest
from goldenmcp_inspect.scorers import score_transcript
from goldenmcp_walrus import WalrusClient

logger = logging.getLogger(__name__)


class WalrusUploadResult:
    def __init__(
        self,
        manifest: ScoreManifest,
        walrus_manifest_blob_id: str,
        walrus_eval_blob_id: str,
    ):
        self.manifest = manifest
        self.walrus_manifest_blob_id = walrus_manifest_blob_id
        self.walrus_eval_blob_id = walrus_eval_blob_id


def post_eval_walrus_upload(
    transcript: EvalTranscript,
    *,
    run_id: str | None = None,
    walrus: WalrusClient | None = None,
) -> WalrusUploadResult:
    """Score transcript, upload eval log + manifest JSON to Walrus."""
    benchmark = load_benchmark(transcript.mcp, transcript.capability)
    scores = score_transcript(transcript, benchmark)
    manifest = build_manifest(transcript, benchmark, run_id=run_id)
    manifest.failed = scores["failed"]
    manifest.fail_reason = scores.get("fail_reason")
    manifest.data_score = scores["data_score"]
    manifest.path_score = scores["path_score"]
    manifest.token_efficiency = scores["token_efficiency"]
    manifest.composite = scores["composite"]

    client = walrus or WalrusClient()
    eval_blob_id = client.upload(
        manifest_to_json(manifest).encode(),
        content_type="application/json",
    )
    manifest.walrus_blob_id = eval_blob_id
    manifest_blob_id = client.upload_json(manifest.to_public_dict())

    logger.info(
        "post_eval_walrus_upload mcp=%s capability=%s manifest_blob=%s eval_blob=%s composite=%.4f failed=%s",
        transcript.mcp,
        transcript.capability,
        manifest_blob_id,
        eval_blob_id,
        manifest.composite,
        manifest.failed,
    )
    return WalrusUploadResult(
        manifest=manifest,
        walrus_manifest_blob_id=manifest_blob_id,
        walrus_eval_blob_id=eval_blob_id,
    )


def post_eval_walrus_upload_via_fsspec(
    transcript: EvalTranscript,
    *,
    run_id: str | None = None,
) -> WalrusUploadResult:
    """Upload via walrus:// fsspec adapter (Inspect log path convention)."""
    import fsspec

    benchmark = load_benchmark(transcript.mcp, transcript.capability)
    scores = score_transcript(transcript, benchmark)
    manifest = build_manifest(transcript, benchmark, run_id=run_id)
    manifest.failed = scores["failed"]
    manifest.fail_reason = scores.get("fail_reason")
    manifest.data_score = scores["data_score"]
    manifest.path_score = scores["path_score"]
    manifest.token_efficiency = scores["token_efficiency"]
    manifest.composite = scores["composite"]

    logical_path = f"walrus://evals/{transcript.mcp}/{transcript.capability}/{manifest.run_id}.eval"
    with fsspec.open(logical_path, "wb") as f:
        f.write(manifest_to_json(manifest).encode())

    manifest.walrus_blob_id = manifest.run_id
    client = WalrusClient()
    manifest_blob_id = client.upload_json(manifest.to_public_dict())
    manifest.walrus_manifest_blob_id = manifest_blob_id

    logger.info(
        "post_eval_walrus_upload_via_fsspec logical_path=%s manifest_blob=%s",
        logical_path,
        manifest_blob_id,
    )
    return WalrusUploadResult(
        manifest=manifest,
        walrus_manifest_blob_id=manifest_blob_id,
        walrus_eval_blob_id=manifest.run_id,
    )


def post_eval_from_inspect_log(
    log_data: dict[str, Any],
    mcp: str,
    capability: str,
    *,
    run_id: str | None = None,
    walrus: WalrusClient | None = None,
) -> WalrusUploadResult:
    """Parse Inspect eval log JSON and upload scores to Walrus."""
    from goldenmcp_inspect.manifest import transcript_from_inspect_log

    transcript = transcript_from_inspect_log(log_data, mcp, capability)
    return post_eval_walrus_upload(transcript, run_id=run_id, walrus=walrus)


def post_eval_from_log_file(
    log_path: str,
    mcp: str,
    capability: str,
    *,
    run_id: str | None = None,
) -> WalrusUploadResult:
    """Load Inspect .eval log file and upload to Walrus."""
    with open(log_path, encoding="utf-8") as f:
        log_data = json.load(f)
    return post_eval_from_inspect_log(log_data, mcp, capability, run_id=run_id)
