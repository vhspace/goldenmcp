#!/usr/bin/env python3
"""Standalone CAI (TEE) judge + attested Walrus re-publish, no CRE runtime.

Mirrors workflows/eval-pipeline/src/pipeline.ts (submitCaiInference / caiAttest /
parseCaiAttestation) but runs on a laptop against the live Confidential AI dev
endpoint, then attaches the attestation to each model's manifest and republishes
to Walrus via the existing Python pipeline.

Per capability: score the K model .eval logs -> manifests, submit ALL of them to
ONE CAI inference as an ensemble (manifest_1.json ...), poll to completion, parse
the attestation, attach it to every model manifest in the ensemble, and publish
each (manifest + raw .eval bytes) to Walrus.

Usage:
  uv run --project packages/inspect-web3 python scripts/cai_judge_and_publish.py \
    --mcp kyberswap --capability quote --log <a.eval> --log <b.eval> --log <c.eval>

Env (from .env): CHAINLINK_CAI_API_KEY, optionally CHAINLINK_CAI_URL,
WALRUS_PUBLISHER_URL, WALRUS_AGGREGATOR_URL, WALRUS_EPOCHS.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import logging
import os
import sys
import time
from pathlib import Path

import requests

from goldenmcp_inspect.benchmarks import load_benchmark
from goldenmcp_inspect.manifest import (
    extract_scores_from_inspect_log,
    manifest_from_scores,
)
from goldenmcp_inspect.pipeline import publish_manifest_to_walrus
from goldenmcp_inspect.schemas import CaiAttestation, ScoreManifest

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger("cai_judge")

DEFAULT_CAI_URL = "https://confidential-ai-dev-preview.cldev.cloud"
CAI_MODEL = "gemma4"
POLL_MAX_ATTEMPTS = 60
POLL_INTERVAL_S = 3


def _load_inspect_log(log_path: str) -> tuple[dict, bytes]:
    """Return (parsed log dict, raw .eval bytes) — same load logic as the pipeline."""
    raw = Path(log_path).read_bytes()
    if log_path.endswith(".json"):
        return json.loads(raw.decode()), raw
    from inspect_ai.log import read_eval_log

    eval_log = read_eval_log(log_path)
    return json.loads(json.dumps(eval_log.model_dump(mode="json"))), raw


def _manifest_for_log(log_path: str, mcp: str, capability: str) -> tuple[ScoreManifest, bytes]:
    """Build a manifest from a .eval, preferring the embedded goldenmcp_scorer score."""
    log_data, raw = _load_inspect_log(log_path)
    scores = extract_scores_from_inspect_log(log_data)
    if scores is None:
        raise SystemExit(f"{log_path}: no embedded goldenmcp_scorer score — re-run the eval")
    manifest = manifest_from_scores(scores, load_benchmark(mcp, capability))
    return manifest, raw


def _to_bytes32(hex_digest: str | None) -> str | None:
    if not hex_digest:
        return None
    h = hex_digest[2:] if hex_digest[:2].lower() == "0x" else hex_digest
    if len(h) != 64 or any(c not in "0123456789abcdefABCDEF" for c in h):
        return None
    return f"0x{h.lower()}"


def _cai_review_prompt(manifest_count: int) -> str:
    if manifest_count > 1:
        return "\n".join(
            [
                f"You are reviewing {manifest_count} GoldenMCP eval score manifests for the SAME MCP server,",
                "each produced by a different open-weight model (the attached manifest_*.json files).",
                "Combine them into one ensemble verdict: sum (then average) the per-model composite scores,",
                "and check the models broadly agree.",
                "Reply with a short verdict: state PASS or FAIL, the combined composite, and one sentence of reasoning.",
            ]
        )
    return "\n".join(
        [
            "You are reviewing a GoldenMCP eval score manifest produced for an MCP server.",
            "Assess whether the scores in manifest.json are internally consistent and the composite is plausible.",
            "Reply with a short verdict: state PASS or FAIL and one sentence of reasoning.",
        ]
    )


def _parse_attestation(status: dict, fallback_model: str = CAI_MODEL) -> CaiAttestation:
    """Mirror pipeline.ts parseCaiAttestation: the TEE inference IS the attestation."""
    output = status.get("output") if isinstance(status.get("output"), str) else ""
    resources = status.get("resources") or []
    response_digest = resources[0].get("response_digest") if resources else None
    transcript_hash = _to_bytes32(response_digest)
    if transcript_hash is None and output:
        transcript_hash = "0x" + hashlib.sha256(output.encode()).hexdigest()
    usage = status.get("usage") or {}
    return CaiAttestation(
        inference_id=str(status.get("id") or ""),
        model=str(status.get("model") or fallback_model),
        verdict=output or "",
        transcript_hash=transcript_hash,
        completed_at=status.get("completed_at"),
        prompt_tokens=usage.get("prompt_tokens"),
        completion_tokens=usage.get("completion_tokens"),
    )


def _submit_cai(base: str, api_key: str, manifests: list[ScoreManifest]) -> str:
    resources = []
    for i, m in enumerate(manifests):
        fname = "manifest.json" if len(manifests) == 1 else f"manifest_{i + 1}.json"
        content = json.dumps(m.to_public_dict()).encode()
        resources.append(
            {
                "filename": fname,
                "content_type": "application/json",
                "content_base64": base64.b64encode(content).decode(),
            }
        )
    body = {
        "model": CAI_MODEL,
        "prompt": _cai_review_prompt(len(manifests)),
        "resources": resources,
    }
    logger.info("CAI POST /v1/inference model=%s manifests=%d", CAI_MODEL, len(manifests))
    resp = requests.post(
        f"{base}/v1/inference",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json=body,
        timeout=30,
    )
    if resp.status_code not in (200, 202):
        raise SystemExit(f"CAI submit failed: HTTP {resp.status_code} — {resp.text[:500]}")
    inference_id = resp.json().get("id")
    if not inference_id:
        raise SystemExit(f"CAI submit missing inference id: {resp.text[:500]}")
    logger.info("CAI inference queued id=%s", inference_id)
    return inference_id


def _poll_cai(base: str, api_key: str, inference_id: str) -> dict:
    for attempt in range(1, POLL_MAX_ATTEMPTS + 1):
        time.sleep(POLL_INTERVAL_S)
        resp = requests.get(
            f"{base}/v1/inference/{inference_id}",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=20,
        )
        if resp.status_code != 200:
            raise SystemExit(f"CAI poll failed: HTTP {resp.status_code} — {resp.text[:300]}")
        status = resp.json()
        st = status.get("status")
        logger.info("CAI poll %d/%d -> status=%s", attempt, POLL_MAX_ATTEMPTS, st)
        if st == "completed":
            return status
        if st == "failed":
            raise SystemExit(f"CAI inference failed: {status.get('error', 'unknown')}")
    raise SystemExit(f"CAI inference did not complete after {POLL_MAX_ATTEMPTS} polls")


def _ensemble_scores(manifests: list[ScoreManifest]) -> dict:
    """Average the per-model dimensions; failed = any model failed.

    Matches the CAI judge's 'combined composite' (mean across models). The
    contract stores ONE CapabilityScore per (agentId, capability), so the
    ensemble collapses to a single averaged record.
    """
    n = len(manifests)
    return {
        "data_score": sum(m.data_score for m in manifests) / n,
        "path_score": sum(m.path_score for m in manifests) / n,
        "token_efficiency": sum(m.token_efficiency for m in manifests) / n,
        "composite": sum(m.composite for m in manifests) / n,
        "failed": any(m.failed for m in manifests),
    }


def _write_to_arc(
    mcp: str,
    capability: str,
    attestation: CaiAttestation,
    ensemble: dict,
    walrus_blob_id: str,
) -> dict:
    """Write recordAttestation + updateCapabilityScore to the Arc registry.

    Attestation is written first (depends on nothing from Walrus), then the
    averaged ensemble score with the representative manifest's blob pointer.
    """
    from goldenmcp_identity.registry import RegistryClient

    client = RegistryClient()
    agent_id = client.get_agent_id(mcp)
    if agent_id == 0:
        raise SystemExit(f"{mcp} is not registered on Arc (nameToAgentId=0)")
    logger.info("Arc agentId=%d for mcp=%s", agent_id, mcp)

    attest_tx = client.record_attestation(
        agent_id, attestation.inference_id, attestation.transcript_hash or ""
    )
    logger.info("Arc recordAttestation tx=%s", attest_tx)

    score_tx = client.update_score(
        agent_id,
        capability,
        data_score=ensemble["data_score"],
        path_score=ensemble["path_score"],
        token_efficiency=ensemble["token_efficiency"],
        composite=ensemble["composite"],
        failed=ensemble["failed"],
        walrus_blob_id=walrus_blob_id,
    )
    logger.info("Arc updateCapabilityScore tx=%s", score_tx)
    return {"agent_id": agent_id, "attestation_tx": attest_tx, "score_tx": score_tx}


def main() -> int:
    parser = argparse.ArgumentParser(description="CAI ensemble judge + attested Walrus publish")
    parser.add_argument("--mcp", required=True)
    parser.add_argument("--capability", required=True)
    parser.add_argument("--log", action="append", required=True, help="Inspect .eval log (repeatable)")
    parser.add_argument(
        "--arc",
        action="store_true",
        help="After publishing, write the ensemble score + attestation to the Arc registry",
    )
    args = parser.parse_args()

    api_key = os.environ.get("CHAINLINK_CAI_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("CHAINLINK_CAI_API_KEY required (source .env)")
    base = (os.environ.get("CHAINLINK_CAI_URL", "").strip() or DEFAULT_CAI_URL).rstrip("/")

    # 1) Score every model log into a manifest (+ keep raw bytes for the Walrus log).
    manifests: list[ScoreManifest] = []
    raw_bytes: list[bytes] = []
    for log in args.log:
        m, raw = _manifest_for_log(log, args.mcp, args.capability)
        logger.info("scored %s composite=%.4f failed=%s", Path(log).name, m.composite, m.failed)
        manifests.append(m)
        raw_bytes.append(raw)

    # 2) One CAI ensemble inference across all model manifests.
    inference_id = _submit_cai(base, api_key, manifests)
    status = _poll_cai(base, api_key, inference_id)
    attestation = _parse_attestation(status)
    if not attestation.inference_id:
        raise SystemExit("CAI completed but returned no inference id")
    logger.info(
        "CAI completed inference_id=%s verdict=%r transcript_hash=%s",
        attestation.inference_id,
        attestation.verdict[:120],
        attestation.transcript_hash,
    )

    # 3) Attach the shared attestation to each model manifest and re-publish to Walrus.
    results = []
    representative_blob = None
    best_composite = -1.0
    for m, raw in zip(manifests, raw_bytes):
        m.attestation = attestation
        m.attestation_id = attestation.inference_id
        res = publish_manifest_to_walrus(m, inspect_log_bytes=raw)
        results.append(
            {
                "composite": m.composite,
                "failed": m.failed,
                "attestation_id": m.attestation_id,
                "walrus_manifest_blob_id": res.walrus_manifest_blob_id,
                "walrus_eval_blob_id": res.walrus_eval_blob_id,
            }
        )
        if m.composite > best_composite:
            best_composite = m.composite
            representative_blob = res.walrus_manifest_blob_id

    out = {
        "mcp": args.mcp,
        "capability": args.capability,
        "inference_id": attestation.inference_id,
        "verdict": attestation.verdict,
        "transcript_hash": attestation.transcript_hash,
        "manifests": results,
    }

    # 4) Optional: write the averaged ensemble score + attestation to Arc.
    if args.arc:
        ensemble = _ensemble_scores(manifests)
        out["ensemble"] = ensemble
        out["arc"] = _write_to_arc(
            args.mcp, args.capability, attestation, ensemble, representative_blob
        )

    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
