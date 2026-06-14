"""Pricing ladder parity with marketplace-mcp-ts/src/pricing.ts."""

from __future__ import annotations

import pytest

from goldenmcp_web_agent.pricing import BASE_USDC, price_for_threshold, price_string


def test_price_for_threshold_tiers_from_base():
    assert price_for_threshold(0, BASE_USDC) == pytest.approx(0.01, abs=1e-6)
    assert price_for_threshold(0.5, BASE_USDC) == pytest.approx(0.03, abs=1e-6)
    assert price_for_threshold(1, BASE_USDC) == pytest.approx(0.05, abs=1e-6)


def test_price_for_threshold_clamps_out_of_range():
    assert price_for_threshold(-1, BASE_USDC) == pytest.approx(0.01, abs=1e-6)
    assert price_for_threshold(2, BASE_USDC) == pytest.approx(0.05, abs=1e-6)


def test_price_string_formats_dollars():
    assert price_string(0, BASE_USDC) == "$0.0100"
    assert price_string(1, BASE_USDC) == "$0.0500"
