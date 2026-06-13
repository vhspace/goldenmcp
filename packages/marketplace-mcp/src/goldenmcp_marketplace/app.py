"""x402 marketplace MCP server for MCP discovery."""

from __future__ import annotations

import json
import logging
import math
import os
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings

from goldenmcp_identity import RegistryClient, IdentitySettings
from goldenmcp_walrus import WalrusClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_USDC = 0.01  # $0.01 base micropayment


class MarketplaceSettings(BaseSettings):
    marketplace_host: str = "0.0.0.0"
    marketplace_port: int = 8091
    base_usdc: float = BASE_USDC
    x402_payee_address: str = ""

    class Config:
        env_file = ".env"
        extra = "ignore"


class LookupRequest(BaseModel):
    capability: str
    min_score: float = Field(ge=0.0, le=1.0)


class LookupResult(BaseModel):
    ens_name: str
    mcp_endpoint: str
    data_score: float
    path_score: float
    token_efficiency: float
    composite: float
    failed: bool
    walrus_blob_id: str
    attestation_id: str | None = None
    transcript_hash: str | None = None


app = FastAPI(title="GoldenMCP Marketplace MCP")
settings = MarketplaceSettings()


def _price_for_threshold(min_score: float) -> float:
    return settings.base_usdc * (1 + 4 * min_score)


def _load_index() -> list[dict[str, Any]]:
    """Load score index from Walrus manifests listed in registry."""
    registry = RegistryClient()
    results = []
    walrus = WalrusClient()
    for agent_id in registry.list_agent_ids():
        rec = registry.get_record(agent_id)
        for cap in ["quote", "route", "trade", "swap"]:
            try:
                score = registry.contract.functions.getCapabilityScore(agent_id, cap).call()
            except Exception:
                continue
            if score[5] == "":
                continue
            composite = score[3] / 10000.0
            manifest = walrus.download_json(score[5]) if score[5] else {}
            results.append(
                {
                    "agent_id": agent_id,
                    "mcp": rec.name,
                    "capability": cap,
                    "ens_name": rec.ens_name,
                    "mcp_endpoint": rec.mcp_endpoint,
                    "data_score": score[0] / 10000.0,
                    "path_score": score[1] / 10000.0,
                    "token_efficiency": score[2] / 10000.0,
                    "composite": composite,
                    "failed": score[4],
                    "walrus_blob_id": score[5],
                    "attestation_id": rec.last_attestation_id or None,
                    "transcript_hash": rec.last_transcript_hash or None,
                    "manifest": manifest,
                }
            )
    return results


@app.get("/health")
def health():
    return {"status": "ok", "service": "goldenmcp-marketplace"}


@app.get("/tools/list_capabilities")
def list_capabilities():
    index = _load_index()
    caps = sorted({r["capability"] for r in index})
    return {"capabilities": caps}


@app.post("/tools/lookup")
async def lookup(
    request: Request,
    body: LookupRequest,
    x_payment: str | None = Header(default=None, alias="X-PAYMENT"),
):
    """x402-gated MCP lookup. Returns 402 until payment header present."""
    price = _price_for_threshold(body.min_score)
    payee = settings.x402_payee_address or os.environ.get("X402_PAYEE_ADDRESS", "")
    if not payee:
        raise HTTPException(status_code=500, detail="X402_PAYEE_ADDRESS not configured")

    if not x_payment:
        return JSONResponse(
            status_code=402,
            content={
                "error": "PaymentRequired",
                "price_usdc": price,
                "min_score": body.min_score,
                "capability": body.capability,
                "payee": payee,
                "network": "arc-testnet",
                "scheme": "exact",
            },
            headers={
                "X-Payment-Required": json.dumps(
                    {
                        "amount": str(price),
                        "currency": "USDC",
                        "network": "arc-testnet",
                        "payee": payee,
                    }
                )
            },
        )

    logger.info("lookup paid capability=%s min_score=%s payment=%s", body.capability, body.min_score, x_payment[:20])

    index = _load_index()
    matches = [
        r
        for r in index
        if r["capability"] == body.capability
        and not r["failed"]
        and r["composite"] >= body.min_score
    ]
    matches.sort(key=lambda r: r["composite"], reverse=True)

    if not matches:
        raise HTTPException(
            status_code=404,
            detail=f"No MCPs found for capability={body.capability} min_score={body.min_score}",
        )

    top = matches[0]
    result = LookupResult(
        ens_name=top["ens_name"],
        mcp_endpoint=top["mcp_endpoint"],
        data_score=top["data_score"],
        path_score=top["path_score"],
        token_efficiency=top["token_efficiency"],
        composite=top["composite"],
        failed=top["failed"],
        walrus_blob_id=top["walrus_blob_id"],
        attestation_id=top.get("attestation_id"),
        transcript_hash=top.get("transcript_hash"),
    )
    return {
        "results": [result.model_dump()],
        "payment_settled": True,
        "price_paid_usdc": price,
    }


@app.post("/tools/get_scores")
async def get_scores(mcp: str, capability: str, x_payment: str | None = Header(default=None, alias="X-PAYMENT")):
    if not x_payment:
        return JSONResponse(status_code=402, content={"error": "PaymentRequired", "price_usdc": settings.base_usdc})
    index = _load_index()
    match = next((r for r in index if r["mcp"] == mcp and r["capability"] == capability), None)
    if not match:
        raise HTTPException(status_code=404, detail=f"No scores for {mcp}/{capability}")
    return match


@app.post("/tools/register_mcp")
def register_mcp(name: str, mcp_endpoint: str, agent_uri: str, ens_name: str):
    registry = RegistryClient()
    agent_id = registry.register(name, mcp_endpoint, agent_uri, ens_name)
    return {"agent_id": agent_id, "status": "queued_for_eval"}


def main():
    import uvicorn

    uvicorn.run(app, host=settings.marketplace_host, port=settings.marketplace_port)


if __name__ == "__main__":
    main()
