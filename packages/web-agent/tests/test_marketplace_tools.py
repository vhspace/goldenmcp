"""Marketplace HTTP tool helpers."""

from __future__ import annotations

from goldenmcp_web_agent.marketplace_tools import (
    LookupQuote,
    build_lookup_request,
    parse_payment_required,
)


def test_build_lookup_request():
    body = build_lookup_request("quote", 0.9)
    assert body == {"capability": "quote", "min_score": 0.9}


def test_parse_payment_required_402():
    payload = {
        "error": "PaymentRequired",
        "price_usdc": 0.046,
        "payee": "0xabc",
        "network": "arc-testnet",
        "capability": "quote",
        "min_score": 0.9,
    }
    quote = parse_payment_required(payload)
    assert quote == LookupQuote(
        capability="quote",
        min_score=0.9,
        price_usdc=0.046,
        payee="0xabc",
        network="arc-testnet",
    )


def test_lookup_quote_matches_pricing_formula():
    from goldenmcp_web_agent.pricing import price_for_threshold

    min_score = 0.9
    expected = price_for_threshold(min_score)
    quote = parse_payment_required(
        {
            "price_usdc": expected,
            "payee": "0x1",
            "network": "arc-testnet",
            "capability": "swap",
            "min_score": min_score,
        }
    )
    assert quote.price_usdc == expected
