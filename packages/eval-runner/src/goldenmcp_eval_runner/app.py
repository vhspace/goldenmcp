"""HTTP service to trigger Inspect evals — called by Chainlink CRE."""

from __future__ import annotations

import base64
import json
import logging
import subprocess
import sys
import threading
import uuid
from pathlib import Path
from typing import Any

from fastapi import Body, Depends, FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from goldenmcp_eval_runner.auth import require_api_key, require_cai_webhook_secret
from goldenmcp_eval_runner.inspect_logs import read_inspect_log_file
from goldenmcp_eval_runner.jobs import EvalJob, eval_jobs, JobStatus
from goldenmcp_eval_runner.pending_runs import (
    benchmark_cursor,
    cai_callbacks,
    inference_index,
    manifest_pairs,
)
from goldenmcp_eval_runner.settings import RunnerSettings, get_settings
from goldenmcp_inspect.benchmarks import list_benchmarks, load_benchmark
from goldenmcp_inspect.manifest import transcript_from_inspect_log
from goldenmcp_inspect.pipeline import (
    post_eval_walrus_upload,
    publish_manifest_to_walrus,
    score_transcript_to_manifest,
)
from goldenmcp_inspect.schemas import CaiAttestation, EvalTranscript, ScoreManifest, TranscriptEvent

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
    model: str | None = None


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
    # Identify the run by run_id, or by the CAI inference_id (resolved via the index).
    run_id: str | None = None
    inference_id: str | None = None
    attestation: dict[str, Any] | None = None
    manifest: dict[str, Any] | None = None
    inspect_log_bytes_b64: str | None = None


class PublishResponse(BaseModel):
    run_id: str
    mcp: str
    capability: str
    manifest: dict[str, Any]
    walrus_manifest_blob_id: str
    walrus_eval_blob_id: str
    walrus_index_blob_id: str | None = None


class CaiSubmittedRequest(BaseModel):
    """Handler A registers the CAI inference_id -> run_id mapping after submitting."""

    inference_id: str
    run_id: str


class PairRequest(BaseModel):
    """Handler A records one model's scored run for a benchmark; the pair of
    open-weight model runs is submitted to one CAI judge once both arrive."""

    mcp: str
    capability: str
    model: str
    run_id: str
    models_total: int = 2


class PairResponse(BaseModel):
    complete: bool
    # When complete: {model -> run_id} for all models of this benchmark.
    runs: dict[str, str] = Field(default_factory=dict)


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


def _to_bytes32(hex_digest: str | None) -> str | None:
    """Normalize a 32-byte hex digest (with/without 0x) to a 0x bytes32 string."""
    if not hex_digest:
        return None
    h = hex_digest[2:] if hex_digest[:2].lower() == "0x" else hex_digest
    if len(h) != 64 or any(c not in "0123456789abcdefABCDEF" for c in h):
        return None
    return f"0x{h.lower()}"


def _attestation_from_cai_status(status: dict[str, Any]) -> CaiAttestation | None:
    """Map a raw CAI inference status (from the cre_callback) to a CaiAttestation.

    The TEE inference is the attestation: `id` is the handle, `output` the verdict.
    """
    inference_id = status.get("id") or status.get("inference_id")
    if not inference_id:
        return None
    usage = status.get("usage") or {}
    resources = status.get("resources") or []
    response_digest = resources[0].get("response_digest") if resources else None
    transcript_hash = status.get("transcript_hash") or _to_bytes32(response_digest)
    return CaiAttestation(
        inference_id=str(inference_id),
        model=str(status.get("model") or "gemma4"),
        verdict=str(status.get("output") or status.get("verdict") or ""),
        transcript_hash=transcript_hash,
        completed_at=status.get("completed_at"),
        prompt_tokens=usage.get("prompt_tokens"),
        completion_tokens=usage.get("completion_tokens"),
    )


def _apply_attestation(
    manifest: ScoreManifest,
    *,
    attestation: dict[str, Any] | None,
    cai_input: dict[str, Any] | None,
) -> None:
    """Populate the manifest attestation from the workflow payload or a CAI callback.

    The workflow-supplied `attestation` (already a CaiAttestation shape) wins; a raw
    CAI callback `input` status is the async fallback.
    """
    record: CaiAttestation | None = None
    if attestation:
        try:
            record = CaiAttestation(**attestation)
        except Exception:  # noqa: BLE001 — tolerate a raw CAI status shape too
            record = _attestation_from_cai_status(attestation)
    elif cai_input:
        record = _attestation_from_cai_status(cai_input)

    if record is not None:
        manifest.attestation = record
        manifest.attestation_id = record.inference_id


def _fail_job(run_id: str, error: str) -> None:
    eval_jobs.update(run_id, status=JobStatus.FAILED, error=error)
    logger.error("eval job failed run_id=%s error=%s", run_id, error)


def _parse_log_path(stdout: str) -> str:
    """Extract the log path from the inspect_runner subprocess stdout.

    The child prints {"log_path": ...} as its last line, but scan lines in reverse
    for the first valid JSON object carrying `log_path` so a stray trailing print
    (atexit/thread) can't break parsing. Raises ValueError if none found.
    """
    for line in reversed((stdout or "").strip().splitlines()):
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and obj.get("log_path"):
            return obj["log_path"]
    raise ValueError("no log_path JSON line in subprocess stdout")


def _run_inspect_job(run_id: str, request: InspectEvalRequest, settings: RunnerSettings) -> None:
    eval_jobs.update(run_id, status=JobStatus.RUNNING)
    model = request.model or settings.eval_inspect_model
    repo_root = _repo_root()
    log_dir = repo_root / "logs"
    logger.info(
        "background subprocess inspect mcp=%s capability=%s model=%s timeout=%s run_id=%s",
        request.mcp,
        request.capability,
        model,
        settings.eval_inspect_timeout,
        run_id,
    )

    # Run each eval in its OWN subprocess. Inspect's eval() sets up process-global
    # anyio/display/async-fs state (eval.py: run_task_app -> anyio.run); a second
    # in-process call in the long-lived uvicorn worker hangs at startup. A fresh
    # process per eval (also fresh MCP client + HTTP pool) sidesteps that entirely.
    cmd = [
        sys.executable,
        "-m",
        "goldenmcp_eval_runner.inspect_runner",
        "--mcp",
        request.mcp,
        "--capability",
        request.capability,
        "--model",
        model,
        "--repo-root",
        str(repo_root),
        "--log-dir",
        str(log_dir),
        "--time-limit",
        str(settings.eval_inspect_time_limit),
    ]
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=settings.eval_inspect_timeout,
        )
    except subprocess.TimeoutExpired:
        logger.error(
            "inspect eval timed out after %ss mcp=%s capability=%s run_id=%s",
            settings.eval_inspect_timeout,
            request.mcp,
            request.capability,
            run_id,
        )
        _fail_job(run_id, f"inspect eval timed out after {settings.eval_inspect_timeout}s")
        return

    if proc.returncode != 0:
        stderr_tail = (proc.stderr or "").strip()[-2000:]
        logger.error(
            "inspect eval subprocess failed rc=%s mcp=%s capability=%s run_id=%s stderr=%s",
            proc.returncode,
            request.mcp,
            request.capability,
            run_id,
            stderr_tail,
        )
        _fail_job(run_id, f"inspect eval failed (rc={proc.returncode}): {stderr_tail or 'no stderr'}")
        return

    try:
        log_path = _parse_log_path(proc.stdout)
        log_data, raw = read_inspect_log_file(log_path)
    except Exception as exc:
        logger.exception(
            "inspect eval output unparseable mcp=%s capability=%s run_id=%s stdout=%s",
            request.mcp,
            request.capability,
            run_id,
            (proc.stdout or "")[-500:],
        )
        _fail_job(run_id, f"inspect eval produced no readable log: {exc}")
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
    attestation: dict[str, Any] | None,
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
        attestation=attestation,
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


@app.get("/benchmarks/next")
def benchmarks_next():
    """Return the next (benchmark × model) pair in the round-robin and advance.

    The CRE cron handler runs ONE (benchmark, model) per fire (one live Inspect
    eval ~ the per-execution HTTP cap); calling this each fire cycles through all
    benchmarks across both open-weight models, emitting a benchmark's two models
    back-to-back so the eval-runner can pair their manifests for one CAI judge.
    """
    items = list_benchmarks()
    if not items:
        raise HTTPException(status_code=404, detail="no benchmarks available")
    return benchmark_cursor.next_pair(items)


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
    """Queue a subprocess Inspect eval; poll GET /eval/runs/{run_id} until scored or failed."""
    if body is not None:
        request = body
    elif mcp and capability:
        request = InspectEvalRequest(
            mcp=mcp,
            capability=capability,
            model=model,
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
    """Queue Walrus upload for a scored run; poll GET /eval/runs/{run_id} until published or failed.

    The run is identified by run_id, or by the CAI inference_id (resolved via the
    inference index — handler B only has the CAI status, not the run_id).
    """
    if not request.run_id and request.inference_id:
        resolved = inference_index.get(request.inference_id)
        if resolved is None:
            raise HTTPException(
                status_code=404,
                detail=f"no run mapped to inference_id={request.inference_id!r} — was /eval/cai-submitted called?",
            )
        request.run_id = resolved
    if not request.run_id:
        raise HTTPException(status_code=400, detail="run_id or inference_id required")

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
            mcp=job.mcp,
            capability=job.capability,
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
            "attestation": request.attestation,
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
    "/eval/pair",
    response_model=PairResponse,
    dependencies=[Depends(require_api_key)],
)
def eval_pair(request: PairRequest):
    """Record one model's scored run for a benchmark; report when the pair is complete.

    Handler A calls this after each (benchmark, model) score. The first model parks
    and gets complete=false; the second returns complete=true with {model: run_id}
    for both, which handler A then submits as a two-manifest CAI inference.
    """
    manifest_pairs.record(request.mcp, request.capability, request.model, request.run_id)
    runs = manifest_pairs.complete_and_clear(request.mcp, request.capability, request.models_total)
    if runs is None:
        return PairResponse(complete=False)
    logger.info(
        "eval/pair complete %s/%s models=%s", request.mcp, request.capability, list(runs.keys())
    )
    return PairResponse(complete=True, runs=runs)


@app.post(
    "/eval/cai-submitted",
    dependencies=[Depends(require_api_key)],
)
def cai_submitted(request: CaiSubmittedRequest):
    """Record a CAI inference_id -> run_id mapping (handler A, right after submit).

    The CRE HTTP-trigger payload carries only the CAI status, so the inference id
    in that status is the only handle back to the run. /eval/publish resolves it.
    """
    inference_index.put(request.inference_id, request.run_id)
    logger.info(
        "cai-submitted inference_id=%s run_id=%s mapped=%d",
        request.inference_id,
        request.run_id,
        len(inference_index),
    )
    return {"status": "ok", "inference_id": request.inference_id, "run_id": request.run_id}


@app.post(
    "/webhooks/cai",
    dependencies=[Depends(require_cai_webhook_secret)],
)
def cai_webhook(body: CaiWebhookBody, run_id: str | None = Query(None)):
    """Receive Chainlink CAI cre_callback POST; store attestation by run_id for publish.

    CAI posts ``{"input": <inference status>}``. The status has no run_id, so the
    workflow carries it in the callback URL query string; inject it here so the
    callback store can key it for a later /eval/publish.
    """
    payload = dict(body.input)
    if run_id and "run_id" not in payload:
        payload["run_id"] = run_id
    run_id = cai_callbacks.put(payload)
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
