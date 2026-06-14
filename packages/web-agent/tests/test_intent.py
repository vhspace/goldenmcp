"""Intent parsing — parity with apps/web/src/lib/intent.ts."""

from __future__ import annotations

import pytest

from goldenmcp_web_agent.intent import parse_demo_prompt


def test_parse_eth_quote_prompt():
    intent = parse_demo_prompt("Get best ETH/USDC quote with min reliability ≥ 0.85")
    assert intent.marketplace_capability == "quote"
    assert intent.assets_from == "ETH"
    assert intent.assets_to == "USDC"
    assert intent.min_reliability_score == pytest.approx(0.85)


def test_parse_swap_prompt():
    intent = parse_demo_prompt(
        "Optimize portfolio: Swap $100 USDC for GHO at the absolute lowest execution time."
    )
    assert intent.marketplace_capability == "swap"
    assert intent.assets_from == "USDC"
    assert intent.assets_to == "GHO"
    assert intent.amount_usd == 100.0
    assert intent.min_reliability_score == pytest.approx(0.9)


def test_parse_generic_capability_without_assets():
    intent = parse_demo_prompt("Find the best quote MCP with reliability at least 0.92")
    assert intent.marketplace_capability == "quote"
    assert intent.min_reliability_score == pytest.approx(0.92)
    assert intent.assets_from is None
    assert intent.assets_to is None
