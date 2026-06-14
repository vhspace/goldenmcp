"""HTTP helpers for marketplace lookup — paid settlement via ts/marketplace_x402.ts."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any

import httpx

from goldenmcp_web_agent.pricing import price_for_threshold

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LookupQuote:
    capability: str
    min_score: float
    price_usdc: float
    payee: str
    network: str


def marketplace_base_url() -> str:
    url = os.environ.get("MARKETPLACE_URL", "")
    if not url:
        raise EnvironmentError(
            "MARKETPLACE_URL is not set — point at marketplace-mcp-ts seller (no mock fallback)."
        )
    return url.rstrip("/")


def build_lookup_request(capability: str, min_score: float) -> dict[str, float | str]:
    if not capability:
        raise ValueError("capability is required")
    if not 0.0 <= min_score <= 1.0:
        raise ValueError(f"min_score must be in [0, 1], got {min_score}")
    return {"capability": capability, "min_score": min_score}


def parse_payment_required(payload: dict[str, Any]) -> LookupQuote:
    """Parse marketplace 402 JSON into a LookupQuote."""
    capability = str(payload.get("capability", ""))
    min_score = float(payload.get("min_score", 0))
    price = payload.get("price_usdc")
    payee = payload.get("payee")
    network = payload.get("network")
    if not capability or payee is None or network is None or price is None:
        raise ValueError(f"incomplete 402 payload: {payload}")
    return LookupQuote(
        capability=capability,
        min_score=min_score,
        price_usdc=float(price),
        payee=str(payee),
        network=str(network),
    )


def quote_lookup_price(capability: str, min_score: float, *, base_usdc: float | None = None) -> LookupQuote:
    """Local price quote using the same ladder as the seller (no HTTP)."""
    from goldenmcp_web_agent.pricing import BASE_USDC

    base = base_usdc if base_usdc is not None else BASE_USDC
    payee = os.environ.get("X402_PAYEE_ADDRESS", "")
    if not payee:
        raise EnvironmentError("X402_PAYEE_ADDRESS is not set — required for lookup quotes.")
    return LookupQuote(
        capability=capability,
        min_score=min_score,
        price_usdc=price_for_threshold(min_score, base),
        payee=payee,
        network="arc-testnet",
    )


async def lookup_unpaid(capability: str, min_score: float) -> dict[str, Any]:
    """POST /tools/lookup without payment — expect 402 with price details."""
    url = f"{marketplace_base_url()}/tools/lookup"
    body = build_lookup_request(capability, min_score)
    logger.info("marketplace lookup unpaid capability=%s min_score=%s url=%s", capability, min_score, url)
    async with httpx.AsyncClient(timeout=30.0) as client:
        res = await client.post(url, json=body)
        data = res.json() if res.content else {}
        if res.status_code == 402:
            return {"status": 402, "quote": parse_payment_required(data), "raw": data}
        if not res.is_success:
            raise RuntimeError(f"marketplace lookup failed HTTP {res.status_code}: {data}")
        return {"status": res.status_code, "results": data.get("results"), "raw": data}
