"""HTTP service to trigger Inspect evals — called by Chainlink CRE."""

from __future__ import annotations

import logging
import os
import subprocess
import uuid
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from pydantic_settings import BaseSettings

from goldenmcp_inspect.benchmarks import list_benchmarks, load_benchmark
from goldenmcp_inspect.pipeline import post_eval_walrus_upload
from goldenmcp_inspect.schemas import EvalTranscript, TranscriptEvent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RunnerSettings(BaseSettings):
    eval_runner_host: str = "0.0.0.0"
    eval_runner_port: int = 8090

    class Config:
        env_file = ".env"
        extra = "ignore"


class EvalRequest(BaseModel):
    mcp: str
    capability: str
    transcript: dict[str, Any] | None = None


class EvalResponse(BaseModel):
    run_id: str
    manifest: dict[str, Any]
    walrus_manifest_blob_id: str
    walrus_eval_blob_id: str | None = None
    walrus_index_blob_id: str | None = None


app = FastAPI(title="GoldenMCP Eval Runner")
settings = RunnerSettings()


@app.get("/health")
def health():
    return {"status": "ok", "service": "goldenmcp-eval-runner"}


@app.get("/benchmarks")
def benchmarks():
    return {"benchmarks": [{"mcp": m, "capability": c} for m, c in list_benchmarks()]}


@app.post("/eval", response_model=EvalResponse)
def run_eval(request: EvalRequest):
    """Score transcript and upload manifest to Walrus. CRE calls this endpoint."""
    run_id = str(uuid.uuid4())
    logger.info("eval request mcp=%s capability=%s run_id=%s", request.mcp, request.capability, run_id)

    try:
        benchmark = load_benchmark(request.mcp, request.capability)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    if request.transcript:
        events = [TranscriptEvent(**e) for e in request.transcript.get("events", [])]
        transcript = EvalTranscript(
            mcp=request.mcp,
            capability=request.capability,
            events=events,
            final_output=request.transcript.get("final_output", {}),
            total_tokens=request.transcript.get("total_tokens", 0),
        )
    else:
        raise HTTPException(
            status_code=400,
            detail="transcript required — run Inspect eval first, POST real transcript JSON",
        )

    result = post_eval_walrus_upload(transcript, run_id=run_id)

    return EvalResponse(
        run_id=run_id,
        manifest=result.manifest.to_public_dict(),
        walrus_manifest_blob_id=result.walrus_manifest_blob_id,
        walrus_eval_blob_id=result.walrus_eval_blob_id,
        walrus_index_blob_id=result.walrus_index_blob_id,
    )


@app.post("/eval/inspect")
def trigger_inspect_eval(mcp: str, capability: str, model: str = "openai/gpt-4o-mini"):
    """Trigger real Inspect CLI eval subprocess."""
    task_name = f"goldenmcp/{mcp}_{capability}".replace("-", "_")
    cmd = ["uv", "run", "inspect", "eval", task_name, "--model", model]
    logger.info("running inspect: %s", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=os.getcwd())
    if result.returncode != 0:
        logger.error("inspect failed stdout=%s stderr=%s", result.stdout, result.stderr)
        raise HTTPException(
            status_code=500,
            detail=f"inspect eval failed: {result.stderr}",
        )
    return {"status": "completed", "task": task_name, "stdout": result.stdout}


def main():
    import uvicorn

    uvicorn.run(app, host=settings.eval_runner_host, port=settings.eval_runner_port)


if __name__ == "__main__":
    main()
