"""LI.FI get-quote normalization."""

from __future__ import annotations

import pytest

from goldenmcp_web_agent.lifi_quote import (
    BASE_USDC,
    BASE_WETH,
    EVAL_FROM_ADDRESS,
    build_lifi_eth_to_usdc_quote_args,
    eth_amount_to_wei,
    normalize_lifi_get_quote_args,
)


def test_eth_amount_to_wei():
    assert eth_amount_to_wei(0.001) == "1000000000000000"
    assert eth_amount_to_wei("0.001") == "1000000000000000"


def test_normalize_fills_from_address_and_tokens():
    out = normalize_lifi_get_quote_args(
        {
            "fromChain": "base",
            "toChain": 8453,
            "fromToken": "ETH",
            "toToken": "USDC",
            "fromAmount": "0.001",
        }
    )
    assert out["fromChain"] == 8453
    assert out["toChain"] == 8453
    assert out["fromToken"] == BASE_WETH
    assert out["toToken"] == BASE_USDC
    assert out["fromAddress"] == EVAL_FROM_ADDRESS
    assert out["fromAmount"] == "1000000000000000"


def test_build_lifi_eth_to_usdc_quote_args():
    out = build_lifi_eth_to_usdc_quote_args(0.001)
    assert out["fromToken"] == BASE_WETH
    assert out["toToken"] == BASE_USDC
    assert out["fromAmount"] == "1000000000000000"


def test_normalize_rejects_bad_token():
    with pytest.raises(ValueError, match="invalid token"):
        normalize_lifi_get_quote_args(
            {"fromChain": 8453, "toChain": 8453, "fromToken": "0x4200", "toToken": "USDC", "fromAmount": "1"}
        )
