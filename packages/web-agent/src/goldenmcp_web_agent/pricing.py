"""USDC lookup pricing — parity with marketplace-mcp-ts/src/pricing.ts."""

from __future__ import annotations

import os

BASE_USDC = float(os.environ.get("BASE_USDC", "0.01"))


def price_for_threshold(min_score: float, base_usdc: float = BASE_USDC) -> float:
    """Tiered price: base * (1 + 4 * min_score), min_score clamped to [0, 1]."""
    clamped = max(0.0, min(1.0, min_score))
    return base_usdc * (1.0 + 4.0 * clamped)


def price_string(min_score: float, base_usdc: float = BASE_USDC) -> str:
    return f"${price_for_threshold(min_score, base_usdc):.4f}"
