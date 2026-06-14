"""Pydantic models for scoring and manifests."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class ExpectedDataField(BaseModel):
    path: str
    tolerance: float | None = None
    required: bool = True


class GoldenBenchmark(BaseModel):
    mcp: str
    capability: str
    expected_data: dict[str, Any] = Field(default_factory=dict)
    expected_path: list[str] = Field(default_factory=list)
    baseline_tokens: int = 4096
    allowed_tools: list[str] = Field(default_factory=list)
    # Security policy (e.g. {"forbidden_actions": [...]}). Top-level in the golden
    # YAML, kept off expected_data so the security gate can read it.
    policy: dict[str, Any] = Field(default_factory=dict)
    data_fields: list[ExpectedDataField] = Field(default_factory=list)


class TranscriptEvent(BaseModel):
    kind: str
    tool_name: str | None = None
    content: str = ""
    tokens: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvalTranscript(BaseModel):
    mcp: str
    capability: str
    events: list[TranscriptEvent] = Field(default_factory=list)
    final_output: dict[str, Any] = Field(default_factory=dict)
    total_tokens: int = 0


class SecurityResult(BaseModel):
    passed: bool
    fail_reason: str | None = None


class DimensionScores(BaseModel):
    data_score: float = 0.0
    path_score: float = 0.0
    token_efficiency: float = 0.0


class CaiAttestation(BaseModel):
    """A completed Confidential AI (TEE) inference — this IS the attestation.

    The TEE inference itself is the proof: a known model ran on the manifest
    inside the enclave. The inference id is the handle; the output is the verdict.
    """

    inference_id: str
    model: str = "gemma4"
    verdict: str = ""
    # 0x-prefixed bytes32 response digest from the TEE; the onchain transcript hash.
    transcript_hash: str | None = None
    completed_at: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


class ScoreManifest(BaseModel):
    schema_version: str = "goldenmcp/score-manifest/v1"
    mcp: str
    capability: str
    run_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    failed: bool = False
    fail_reason: str | None = None
    data_score: float = 0.0
    path_score: float = 0.0
    token_efficiency: float = 0.0
    composite: float = 0.0
    walrus_blob_id: str | None = None
    walrus_manifest_blob_id: str | None = None
    # Walrus index blob that resolves walrus_blob_id's indexed path to a concrete
    # blob. Embedded so each manifest is self-resolving (frontend needs no env var).
    walrus_index_blob_id: str | None = None
    # CAI inference id, mirrored onchain via recordAttestation as the reference.
    attestation_id: str | None = None
    attestation: CaiAttestation | None = None
    ens_name: str | None = None

    def to_public_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")
