"""HTTP service to trigger Inspect evals — called by Chainlink CRE."""

from __future__ import annotations

import base64
import logging
import subprocess
import threading
import uuid
from pathlib import Path
from typing import Any

from fastapi import Body, Depends, FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from goldenmcp_eval_runner.auth import require_api_key, require_cai_webhook_secret
from goldenmcp_eval_runner.inspect_logs import find_inspect_log_for_task
from goldenmcp_eval_runner.jobs import EvalJob, eval_jobs, JobStatus
from goldenmcp_eval_runner.pending_runs import cai_callbacks
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


class JobAcceptedResponse(BaseModel):
    run_id: str
    status: str


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


def _fail_job(run_id: str, error: str) -> None:
    eval_jobs.update(run_id, status=JobStatus.FAILED, error=error)
    logger.error("eval job failed run_id=%s error=%s", run_id, error)


def _run_inspect_job(run_id: str, request: InspectEvalRequest, settings: RunnerSettings) -> None:
    eval_jobs.update(run_id, status=JobStatus.RUNNING)
    task_name = f"goldenmcp/{request.mcp}_{request.capability}".replace("-", "_")
    cmd = ["uv", "run", "inspect", "eval", task_name, "--model", request.model]
    cwd = _repo_root()
    logger.info(
        "background inspect cwd=%s cmd=%s timeout=%s run_id=%s",
        cwd,
        " ".join(cmd),
        settings.eval_inspect_timeout,
        run_id,
    )

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
            "inspect eval timed out after %ss mcp=%s capability=%s run_id=%s stdout=%s stderr=%s",
            settings.eval_inspect_timeout,
            request.mcp,
            request.capability,
            run_id,
            exc.stdout,
            exc.stderr,
        )
        _fail_job(
            run_id,
            f"inspect eval timed out after {settings.eval_inspect_timeout}s",
        )
        return

    if result.returncode != 0:
        logger.error(
            "inspect failed mcp=%s capability=%s run_id=%s returncode=%s stdout=%s stderr=%s",
            request.mcp,
            request.capability,
            run_id,
            result.returncode,
            result.stdout,
            result.stderr,
        )
        _fail_job(run_id, f"inspect eval failed (exit {result.returncode})")
        return

    try:
        log_path, log_data, raw = find_inspect_log_for_task(task_name)
    except FileNotFoundError as exc:
        logger.error("inspect log lookup failed task=%s run_id=%s error=%s", task_name, run_id, exc)
        _fail_job(run_id, str(exc))
        return

    transcript = transcript_from_inspect_log(log_data, request.mcp, request.capability)
    manifest = score_transcript_to_manifest(transcript, run_id=run_id)
    eval_jobs.update(
        run_id,
        status=JobStatus.SCORED,
        manifest=manifest,
        transcript=transcript,
        inspect_log_bytes=raw,
        inspect_log_path=log_path,
        error=None,
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


def _resolve_publish_job(request: PublishRequest) -> EvalJob | None:
    job = eval_jobs.get(request.run_id)
    if job is not None:
        return job

    if request.manifest is None:
        return None

    manifest = _manifest_from_dict(request.manifest)
    if manifest.run_id != request.run_id:
        raise HTTPException(
            status_code=400,
            detail="manifest.run_id must match request run_id when no job exists",
        )

    inspect_log_bytes: bytes | None = None
    if request.inspect_log_bytes_b64:
        try:
            inspect_log_bytes = base64.b64decode(request.inspect_log_bytes_b64)
        except Exception as exc:
            raise HTTPException(status_code=400, detail="invalid inspect_log_bytes_b64") from exc

    logger.warning(
        "eval/publish using client-supplied manifest run_id=%s (no job) — prefer score/inspect first",
        request.run_id,
    )
    return EvalJob(
        run_id=request.run_id,
        mcp=manifest.mcp,
        capability=manifest.capability,
        status=JobStatus.SCORED,
        manifest=manifest,
        inspect_log_bytes=inspect_log_bytes,
    )


def _run_publish_job(
    run_id: str,
    *,
    attestation_id: str | None,
    attestation_tx_hash: str | None,
    job: EvalJob,
) -> None:
    eval_jobs.update(run_id, status=JobStatus.PUBLISHING)
    cai_input = cai_callbacks.pop(run_id)

    manifest = job.manifest.model_copy(deep=True) if job.manifest is not None else None
    if manifest is None:
        _fail_job(run_id, "publish job missing manifest")
        return

    _apply_attestation(
        manifest,
        attestation_id=attestation_id,
        attestation_tx_hash=attestation_tx_hash,
        cai_input=cai_input,
    )

    try:
        result = publish_manifest_to_walrus(
            manifest,
            transcript=job.transcript,
            inspect_log_bytes=job.inspect_log_bytes,
            inspect_log_path=job.inspect_log_path,
        )
    except Exception as exc:
        logger.exception("walrus publish failed run_id=%s", run_id)
        _fail_job(run_id, f"walrus publish failed: {exc}")
        return

    eval_jobs.update(
        run_id,
        status=JobStatus.PUBLISHED,
        manifest=result.manifest,
        walrus_manifest_blob_id=result.walrus_manifest_blob_id,
        walrus_eval_blob_id=result.walrus_eval_blob_id,
        walrus_index_blob_id=result.walrus_index_blob_id,
        error=None,
    )
    logger.info(
        "eval/publish complete run_id=%s manifest_blob=%s eval_blob=%s",
        run_id,
        result.walrus_manifest_blob_id,
        result.walrus_eval_blob_id,
    )


@app.get("/health")
def health():
    return {"status": "ok", "service": "goldenmcp-eval-runner"}


@app.get("/benchmarks")
def benchmarks():
    return {"benchmarks": [{"mcp": m, "capability": c} for m, c in list_benchmarks()]}


@app.get(
    "/eval/runs/{run_id}",
    dependencies=[Depends(require_api_key)],
)
def get_eval_run(run_id: str):
    job = eval_jobs.get(run_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"no eval run for run_id={run_id!r}")
    return job.to_public_dict()


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
    eval_jobs.create(run_id, request.mcp, request.capability, status=JobStatus.SCORED)
    eval_jobs.update(
        run_id,
        manifest=manifest,
        transcript=transcript,
    )
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
    dependencies=[Depends(require_api_key)],
)
def trigger_inspect_eval(
    body: InspectEvalRequest | None = Body(None),
    mcp: str | None = Query(None),
    capability: str | None = Query(None),
    model: str | None = Query(None),
    settings: RunnerSettings = Depends(get_settings),
):
    """Queue real Inspect subprocess; poll GET /eval/runs/{run_id} until scored or failed."""
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

    run_id = str(uuid.uuid4())
    eval_jobs.create(run_id, request.mcp, request.capability, status=JobStatus.QUEUED)
    thread = threading.Thread(
        target=_run_inspect_job,
        args=(run_id, request, settings),
        name=f"inspect-{run_id}",
        daemon=True,
    )
    thread.start()
    logger.info("eval/inspect queued mcp=%s capability=%s run_id=%s", request.mcp, request.capability, run_id)
    return JSONResponse(
        status_code=202,
        content=JobAcceptedResponse(run_id=run_id, status=JobStatus.QUEUED).model_dump(),
    )


@app.post(
    "/eval/publish",
    dependencies=[Depends(require_api_key)],
)
def publish_eval(request: PublishRequest):
    """Queue Walrus upload for a scored run; poll GET /eval/runs/{run_id} until published or failed."""
    job = _resolve_publish_job(request)
    if job is None:
        raise HTTPException(
            status_code=404,
            detail=f"no eval run for run_id={request.run_id!r} — call /eval/score or /eval/inspect first",
        )

    if job.status == JobStatus.PUBLISHED:
        if job.manifest is None or job.walrus_manifest_blob_id is None or job.walrus_eval_blob_id is None:
            raise HTTPException(status_code=500, detail="published job missing walrus fields")
        return PublishResponse(
            run_id=job.run_id,
            manifest=job.manifest.to_public_dict(),
            walrus_manifest_blob_id=job.walrus_manifest_blob_id,
            walrus_eval_blob_id=job.walrus_eval_blob_id,
            walrus_index_blob_id=job.walrus_index_blob_id,
        )

    if job.status == JobStatus.PUBLISHING:
        return JSONResponse(
            status_code=202,
            content=JobAcceptedResponse(run_id=request.run_id, status=JobStatus.PUBLISHING).model_dump(),
        )

    if job.status != JobStatus.SCORED:
        raise HTTPException(
            status_code=409,
            detail=f"run_id={request.run_id!r} status={job.status} — publish requires scored run",
        )

    # Legacy client-supplied manifest: store ephemeral job before background publish.
    if eval_jobs.get(request.run_id) is None:
        eval_jobs.create(job.run_id, job.mcp, job.capability, status=JobStatus.SCORED)
        eval_jobs.update(
            request.run_id,
            manifest=job.manifest,
            transcript=job.transcript,
            inspect_log_bytes=job.inspect_log_bytes,
            inspect_log_path=job.inspect_log_path,
        )
        job = eval_jobs.get(request.run_id)
        if job is None:
            raise HTTPException(status_code=500, detail="failed to store publish job")

    thread = threading.Thread(
        target=_run_publish_job,
        args=(
            request.run_id,
        ),
        kwargs={
            "attestation_id": request.attestation_id,
            "attestation_tx_hash": request.attestation_tx_hash,
            "job": job,
        },
        name=f"publish-{request.run_id}",
        daemon=True,
    )
    thread.start()
    return JSONResponse(
        status_code=202,
        content=JobAcceptedResponse(run_id=request.run_id, status=JobStatus.PUBLISHING).model_dump(),
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
