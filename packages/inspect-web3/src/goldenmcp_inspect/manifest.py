"""Build and persist score manifests."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from goldenmcp_inspect.schemas import EvalTranscript, GoldenBenchmark, ScoreManifest
from goldenmcp_inspect.scorers import score_transcript

logger = logging.getLogger(__name__)


def build_manifest(
    transcript: EvalTranscript,
    benchmark: GoldenBenchmark,
    *,
    run_id: str | None = None,
    walrus_blob_id: str | None = None,
    walrus_manifest_blob_id: str | None = None,
) -> ScoreManifest:
    scores = score_transcript(transcript, benchmark)
    return ScoreManifest(
        mcp=benchmark.mcp,
        capability=benchmark.capability,
        run_id=run_id or str(uuid.uuid4()),
        created_at=datetime.now(timezone.utc),
        failed=scores["failed"],
        fail_reason=scores.get("fail_reason"),
        data_score=scores["data_score"],
        path_score=scores["path_score"],
        token_efficiency=scores["token_efficiency"],
        composite=scores["composite"],
        walrus_blob_id=walrus_blob_id,
        walrus_manifest_blob_id=walrus_manifest_blob_id,
    )


def manifest_to_json(manifest: ScoreManifest) -> str:
    return json.dumps(manifest.to_public_dict(), indent=2)


def synthesize_inspect_log_bytes(transcript: EvalTranscript, manifest: ScoreManifest) -> bytes:
    """Build minimal Inspect-compatible JSON log bytes when only a transcript is available."""
    events: list[dict[str, Any]] = []
    for event in transcript.events:
        if event.kind == "tool":
            events.append(
                {
                    "event": "tool",
                    "tool_call": {
                        "function": event.tool_name,
                        "arguments": event.content,
                    },
                }
            )
    if transcript.total_tokens:
        events.append({"event": "model", "usage": {"total_tokens": transcript.total_tokens}})

    payload = {
        "status": "success",
        "eval": {
            "task": f"goldenmcp/{transcript.mcp}_{transcript.capability}",
            "task_id": manifest.run_id,
        },
        "samples": [{"events": events, "output": transcript.final_output}],
    }
    return json.dumps(payload, indent=2).encode()


def transcript_from_inspect_log(log_data: dict[str, Any], mcp: str, capability: str) -> EvalTranscript:
    """Parse Inspect eval log JSON into EvalTranscript."""
    events = []
    total_tokens = 0
    final_output: dict[str, Any] = {}

    samples = log_data.get("samples", [])
    for sample in samples:
        for event in sample.get("events", []):
            event_type = event.get("event", "")
            if event_type == "tool":
                events.append(
                    {
                        "kind": "tool",
                        "tool_name": event.get("tool_call", {}).get("function", ""),
                        "content": json.dumps(event.get("tool_call", {})),
                        "tokens": 0,
                    }
                )
            elif event_type == "model":
                usage = event.get("usage", {})
                total_tokens += usage.get("total_tokens", 0)
        output = sample.get("output", {})
        if output:
            final_output = output if isinstance(output, dict) else {"text": str(output)}

    from goldenmcp_inspect.schemas import TranscriptEvent

    return EvalTranscript(
        mcp=mcp,
        capability=capability,
        events=[TranscriptEvent(**e) for e in events],
        final_output=final_output,
        total_tokens=total_tokens,
    )
