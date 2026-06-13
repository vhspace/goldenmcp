"""HTTP service to trigger Inspect evals — called by Chainlink CRE."""

from __future__ import annotations

import base64
import logging
import subprocess
import uuid
from pathlib import Path
from typing import Any

from fastapi import Body, Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from goldenmcp_eval_runner.auth import require_api_key, require_cai_webhook_secret
from goldenmcp_eval_runner.inspect_logs import find_inspect_log_for_task
from goldenmcp_eval_runner.pending_runs import PendingRun, cai_callbacks, pending_runs
from goldenmcp_eval_runner.settings import RunnerSettings, get_settings
from goldenmcp_inspect.benchmarks import list_benchmarks, load_benchmark
from goldenmcp_inspect.manifest import transcript_from_inspect_log
from goldenmcp_inspect.pipeline import (
    post_eval_walrus_upload,
    publish_manifest_to_walrus,
    score_transcript_to_manifest,
)
from goldenmcp_inspect.schemas import EvalTranscript, ScoreManifest, TranscriptEvent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EvalRequest(BaseModel):
    mcp: str
    capability: str
    transcript: dict[str, Any] | None = None


class ScoreRequest(BaseModel):
    mcp: str
    capability: str
    transcript: dict[str, Any]
    run_id: str | None = None


class InspectEvalRequest(BaseModel):
    mcp: str
    capability: str
    model: str = "openai/gpt-4o-mini"


class ScoreResponse(BaseModel):
    run_id: str
    manifest: dict[str, Any]


class EvalResponse(BaseModel):
    run_id: str
    manifest: dict[str, Any]
    walrus_manifest_blob_id: str
    walrus_eval_blob_id: str | None = None
    walrus_index_blob_id: str | None = None


class PublishRequest(BaseModel):
    run_id: str
    attestation_id: str | None = None
    attestation_tx_hash: str | None = None
    manifest: dict[str, Any] | None = None
    inspect_log_bytes_b64: str | None = None


class PublishResponse(BaseModel):
    run_id: str
    manifest: dict[str, Any]
    walrus_manifest_blob_id: str
    walrus_eval_blob_id: str
    walrus_index_blob_id: str | None = None


class CaiWebhookBody(BaseModel):
    input: dict[str, Any] = Field(default_factory=dict)


app = FastAPI(title="GoldenMCP Eval Runner")


def _repo_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "pyproject.toml").is_file() and (parent / "packages").is_dir():
            return parent
    return Path.cwd()


def _load_benchmark_or_404(mcp: str, capability: str) -> None:
    try:
        load_benchmark(mcp, capability)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def _transcript_from_request(mcp: str, capability: str, transcript_data: dict[str, Any]) -> EvalTranscript:
    events = [TranscriptEvent(**e) for e in transcript_data.get("events", [])]
    return EvalTranscript(
        mcp=mcp,
        capability=capability,
        events=events,
        final_output=transcript_data.get("final_output", {}),
        total_tokens=transcript_data.get("total_tokens", 0),
    )


def _manifest_from_dict(data: dict[str, Any]) -> ScoreManifest:
    return ScoreManifest(**data)


def _apply_attestation(
    manifest: ScoreManifest,
    *,
    attestation_id: str | None,
    attestation_tx_hash: str | None,
    cai_input: dict[str, Any] | None,
) -> None:
    if attestation_id is not None:
        manifest.attestation_id = attestation_id or None
    elif cai_input and cai_input.get("attestation_id") is not None:
        manifest.attestation_id = cai_input.get("attestation_id")

    if attestation_tx_hash is not None:
        manifest.attestation_tx_hash = attestation_tx_hash or None
    elif cai_input and cai_input.get("attestation_tx_hash") is not None:
        manifest.attestation_tx_hash = cai_input.get("attestation_tx_hash")


def _store_pending_run(
    run_id: str,
    manifest: ScoreManifest,
    *,
    transcript: EvalTranscript | None = None,
    inspect_log_bytes: bytes | None = None,
    inspect_log_path: str | None = None,
) -> None:
    pending_runs.put(
        run_id,
        PendingRun(
            manifest=manifest,
            transcript=transcript,
            inspect_log_bytes=inspect_log_bytes,
            inspect_log_path=inspect_log_path,
        ),
    )


@app.get("/health")
def health():
    return {"status": "ok", "service": "goldenmcp-eval-runner"}


@app.get("/benchmarks")
def benchmarks():
    return {"benchmarks": [{"mcp": m, "capability": c} for m, c in list_benchmarks()]}


@app.post(
    "/eval",
    response_model=EvalResponse,
    dependencies=[Depends(require_api_key)],
    deprecated=True,
    summary="Deprecated — use /eval/score then /eval/publish",
)
def run_eval(request: EvalRequest):
    """Score transcript and upload manifest to Walrus (all-in-one, deprecated)."""
    run_id = str(uuid.uuid4())
    logger.info("eval request mcp=%s capability=%s run_id=%s", request.mcp, request.capability, run_id)

    _load_benchmark_or_404(request.mcp, request.capability)

    if not request.transcript:
        raise HTTPException(
            status_code=400,
            detail="transcript required — run Inspect eval first, POST real transcript JSON",
        )

    transcript = _transcript_from_request(request.mcp, request.capability, request.transcript)
    result = post_eval_walrus_upload(transcript, run_id=run_id)

    return EvalResponse(
        run_id=run_id,
        manifest=result.manifest.to_public_dict(),
        walrus_manifest_blob_id=result.walrus_manifest_blob_id,
        walrus_eval_blob_id=result.walrus_eval_blob_id,
        walrus_index_blob_id=result.walrus_index_blob_id,
    )


@app.post(
    "/eval/score",
    response_model=ScoreResponse,
    dependencies=[Depends(require_api_key)],
)
def score_eval(request: ScoreRequest):
    """Score an existing transcript JSON without Walrus upload."""
    _load_benchmark_or_404(request.mcp, request.capability)

    transcript = _transcript_from_request(request.mcp, request.capability, request.transcript)
    run_id = request.run_id or str(uuid.uuid4())
    manifest = score_transcript_to_manifest(transcript, run_id=run_id)
    _store_pending_run(run_id, manifest, transcript=transcript)
    logger.info(
        "eval/score mcp=%s capability=%s run_id=%s composite=%.4f",
        request.mcp,
        request.capability,
        run_id,
        manifest.composite,
    )
    return ScoreResponse(run_id=run_id, manifest=manifest.to_public_dict())


@app.post(
    "/eval/inspect",
    response_model=ScoreResponse,
    dependencies=[Depends(require_api_key)],
)
def trigger_inspect_eval(
    body: InspectEvalRequest | None = Body(None),
    mcp: str | None = Query(None),
    capability: str | None = Query(None),
    model: str | None = Query(None),
    settings: RunnerSettings = Depends(get_settings),
):
    """Run real Inspect subprocess, score transcript, return manifest without Walrus."""
    if body is not None:
        request = body
    elif mcp and capability:
        request = InspectEvalRequest(
            mcp=mcp,
            capability=capability,
            model=model or "openai/gpt-4o-mini",
        )
    else:
        raise HTTPException(
            status_code=400,
            detail="JSON body or query params mcp+capability required",
        )

    _load_benchmark_or_404(request.mcp, request.capability)

    task_name = f"goldenmcp/{request.mcp}_{request.capability}".replace("-", "_")
    cmd = ["uv", "run", "inspect", "eval", task_name, "--model", request.model]
    cwd = _repo_root()
    logger.info("running inspect cwd=%s cmd=%s timeout=%s", cwd, " ".join(cmd), settings.eval_inspect_timeout)

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=settings.eval_inspect_timeout,
        )
    except subprocess.TimeoutExpired as exc:
        logger.error(
            "inspect eval timed out after %ss mcp=%s capability=%s stdout=%s stderr=%s",
            settings.eval_inspect_timeout,
            request.mcp,
            request.capability,
            exc.stdout,
            exc.stderr,
        )
        raise HTTPException(
            status_code=500,
            detail=f"inspect eval timed out after {settings.eval_inspect_timeout}s",
        ) from exc

    if result.returncode != 0:
        logger.error(
            "inspect failed mcp=%s capability=%s returncode=%s stdout=%s stderr=%s",
            request.mcp,
            request.capability,
            result.returncode,
            result.stdout,
            result.stderr,
        )
        raise HTTPException(
            status_code=500,
            detail=f"inspect eval failed (exit {result.returncode})",
        )

    try:
        log_path, log_data, raw = find_inspect_log_for_task(task_name)
    except FileNotFoundError as exc:
        logger.error("inspect log lookup failed task=%s error=%s", task_name, exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    transcript = transcript_from_inspect_log(log_data, request.mcp, request.capability)
    run_id = str(uuid.uuid4())
    manifest = score_transcript_to_manifest(transcript, run_id=run_id)
    _store_pending_run(
        run_id,
        manifest,
        transcript=transcript,
        inspect_log_bytes=raw,
        inspect_log_path=log_path,
    )
    logger.info(
        "eval/inspect scored mcp=%s capability=%s run_id=%s log_path=%s log_bytes=%d composite=%.4f",
        request.mcp,
        request.capability,
        run_id,
        log_path,
        len(raw),
        manifest.composite,
    )
    return ScoreResponse(run_id=run_id, manifest=manifest.to_public_dict())


@app.post(
    "/eval/publish",
    response_model=PublishResponse,
    dependencies=[Depends(require_api_key)],
)
def publish_eval(request: PublishRequest):
    """Upload scored manifest to Walrus after attestation (uses pending run store)."""
    pending = pending_runs.pop(request.run_id)
    cai_input = cai_callbacks.pop(request.run_id)

    if pending is not None:
        manifest = pending.manifest.model_copy(deep=True)
        inspect_log_bytes = pending.inspect_log_bytes
        transcript = pending.transcript
        inspect_log_path = pending.inspect_log_path
    elif request.manifest is not None:
        manifest = _manifest_from_dict(request.manifest)
        if manifest.run_id != request.run_id:
            raise HTTPException(
                status_code=400,
                detail="manifest.run_id must match request run_id when no pending run exists",
            )
        transcript = None
        inspect_log_path = None
        inspect_log_bytes = None
        if request.inspect_log_bytes_b64:
            try:
                inspect_log_bytes = base64.b64decode(request.inspect_log_bytes_b64)
            except Exception as exc:
                raise HTTPException(status_code=400, detail="invalid inspect_log_bytes_b64") from exc
        logger.warning(
            "eval/publish using client-supplied manifest run_id=%s (no pending run) — prefer score/inspect first",
            request.run_id,
        )
    else:
        raise HTTPException(
            status_code=404,
            detail=f"no pending run for run_id={request.run_id!r} — call /eval/score or /eval/inspect first",
        )

    _apply_attestation(
        manifest,
        attestation_id=request.attestation_id,
        attestation_tx_hash=request.attestation_tx_hash,
        cai_input=cai_input,
    )

    result = publish_manifest_to_walrus(
        manifest,
        transcript=transcript,
        inspect_log_bytes=inspect_log_bytes,
        inspect_log_path=inspect_log_path,
    )

    return PublishResponse(
        run_id=manifest.run_id,
        manifest=result.manifest.to_public_dict(),
        walrus_manifest_blob_id=result.walrus_manifest_blob_id,
        walrus_eval_blob_id=result.walrus_eval_blob_id,
        walrus_index_blob_id=result.walrus_index_blob_id,
    )


@app.post(
    "/webhooks/cai",
    dependencies=[Depends(require_cai_webhook_secret)],
)
def cai_webhook(body: CaiWebhookBody):
    """Receive Chainlink CAI cre_callback POST; store attestation by run_id for publish."""
    run_id = cai_callbacks.put(body.input)
    if run_id:
        logger.info(
            "cai webhook stored run_id=%s callbacks_stored=%d input_keys=%s",
            run_id,
            len(cai_callbacks),
            list(body.input.keys()),
        )
    else:
        logger.warning(
            "cai webhook missing run_id in input — not stored callbacks_stored=%d keys=%s",
            len(cai_callbacks),
            list(body.input.keys()),
        )
    return {"status": "ok", "run_id": run_id, "stored": len(cai_callbacks)}


def main():
    import uvicorn

    settings = get_settings()
    uvicorn.run(app, host=settings.eval_runner_host, port=settings.eval_runner_port)


if __name__ == "__main__":
    main()
