"""HTTP service to trigger Inspect evals — called by Chainlink CRE."""

from __future__ import annotations

import json
import logging
import subprocess
import uuid
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field

from goldenmcp_eval_runner.auth import require_api_key, require_cai_webhook_secret
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

# In-memory CAI callback store for publish flow polling (minimal viable).
_cai_callbacks: list[dict[str, Any]] = []


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
    manifest: dict[str, Any]
    attestation_id: str | None = None
    attestation_tx_hash: str | None = None


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


def _read_latest_inspect_log(task_name: str) -> tuple[dict[str, Any], bytes]:
    from inspect_ai.log import list_eval_logs, read_eval_log

    logs = list_eval_logs()
    if not logs:
        raise HTTPException(status_code=500, detail="inspect eval produced no log files")

    task_slug = task_name.replace("/", "_")
    matching = [log for log in logs if task_slug in log.name]
    log_info = matching[0] if matching else logs[0]
    log_path = log_info.name

    logger.info("reading inspect log path=%s task=%s", log_path, task_name)

    if log_path.endswith(".json"):
        raw = Path(log_path).read_bytes()
        log_data = json.loads(raw.decode())
    else:
        eval_log = read_eval_log(log_path)
        log_data = json.loads(json.dumps(eval_log.model_dump(mode="json")))
        raw = Path(log_path).read_bytes()

    return log_data, raw


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

    try:
        load_benchmark(request.mcp, request.capability)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

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
    try:
        load_benchmark(request.mcp, request.capability)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    transcript = _transcript_from_request(request.mcp, request.capability, request.transcript)
    run_id = request.run_id or str(uuid.uuid4())
    manifest = score_transcript_to_manifest(transcript, run_id=run_id)
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
def trigger_inspect_eval(request: InspectEvalRequest, settings: RunnerSettings = Depends(get_settings)):
    """Run real Inspect subprocess, score transcript, return manifest without Walrus."""
    try:
        load_benchmark(request.mcp, request.capability)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

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
            detail=f"inspect eval failed (exit {result.returncode}): {result.stderr}",
        )

    log_data, _ = _read_latest_inspect_log(task_name)
    transcript = transcript_from_inspect_log(log_data, request.mcp, request.capability)
    run_id = str(uuid.uuid4())
    manifest = score_transcript_to_manifest(transcript, run_id=run_id)
    logger.info(
        "eval/inspect scored mcp=%s capability=%s run_id=%s composite=%.4f",
        request.mcp,
        request.capability,
        run_id,
        manifest.composite,
    )
    return ScoreResponse(run_id=run_id, manifest=manifest.to_public_dict())


@app.post(
    "/eval/publish",
    response_model=PublishResponse,
    dependencies=[Depends(require_api_key)],
)
def publish_eval(request: PublishRequest):
    """Upload scored manifest to Walrus after attestation."""
    manifest = _manifest_from_dict(request.manifest)
    if request.attestation_id:
        manifest.attestation_id = request.attestation_id
    if request.attestation_tx_hash:
        manifest.attestation_tx_hash = request.attestation_tx_hash

    transcript = EvalTranscript(mcp=manifest.mcp, capability=manifest.capability)
    result = publish_manifest_to_walrus(manifest, transcript=transcript)

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
    """Receive Chainlink CAI cre_callback POST and store for publish flow."""
    payload = {"input": body.input}
    _cai_callbacks.append(payload)
    logger.info("cai webhook received callbacks_stored=%d input_keys=%s", len(_cai_callbacks), list(body.input.keys()))
    return {"status": "ok", "stored": len(_cai_callbacks)}


def main():
    import uvicorn

    settings = get_settings()
    uvicorn.run(app, host=settings.eval_runner_host, port=settings.eval_runner_port)


if __name__ == "__main__":
    main()
