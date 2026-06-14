"""LI.FI get-quote argument normalization for the concierge."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

BASE_CHAIN_ID = 8453
BASE_WETH = "0x4200000000000000000000000000000000000006"
BASE_USDC = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
# Read-only quote sender used in evals — never signs.
EVAL_FROM_ADDRESS = "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"

_CHAIN_ALIASES: dict[str, int] = {
    "base": BASE_CHAIN_ID,
    "ethereum": 1,
    "eth": 1,
}

_TOKEN_ALIASES: dict[str, str] = {
    "eth": BASE_WETH,
    "weth": BASE_WETH,
    "usdc": BASE_USDC,
}


def _normalize_chain(value: Any) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.isdigit():
            return int(stripped)
        lowered = stripped.lower()
        if lowered in _CHAIN_ALIASES:
            return _CHAIN_ALIASES[lowered]
    raise ValueError(f"unsupported chain value: {value!r}")


def _normalize_token(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError(f"token must be a string address or symbol, got {type(value).__name__}")
    stripped = value.strip()
    if stripped.lower() in _TOKEN_ALIASES:
        return _TOKEN_ALIASES[stripped.lower()]
    if stripped.startswith("0x") and len(stripped) == 42:
        return stripped
    raise ValueError(f"invalid token value: {value!r} — use full 0x address or ETH/WETH/USDC")


def eth_amount_to_wei(amount_eth: float | str) -> str:
    try:
        wei = int(Decimal(str(amount_eth)) * Decimal(10**18))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"invalid ETH amount: {amount_eth!r}") from exc
    if wei <= 0:
        raise ValueError(f"ETH amount must be positive, got {amount_eth!r}")
    return str(wei)


def normalize_lifi_get_quote_args(arguments: dict[str, Any]) -> dict[str, Any]:
    """Fill LI.FI get-quote required fields with eval canonical defaults."""
    raw = dict(arguments)

    from_chain = raw.get("fromChain", raw.get("fromChainId", BASE_CHAIN_ID))
    to_chain = raw.get("toChain", raw.get("toChainId", from_chain))
    from_token = raw.get("fromToken", raw.get("fromTokenAddress", BASE_WETH))
    to_token = raw.get("toToken", raw.get("toTokenAddress", BASE_USDC))
    from_amount = raw.get("fromAmount")
    if from_amount is None:
        raise ValueError("fromAmount is required (wei string or decimal ETH e.g. 0.001)")

    out: dict[str, Any] = {
        "fromChain": _normalize_chain(from_chain),
        "toChain": _normalize_chain(to_chain),
        "fromToken": _normalize_token(from_token),
        "toToken": _normalize_token(to_token),
        "fromAddress": str(raw.get("fromAddress") or EVAL_FROM_ADDRESS),
    }

    amount_str = str(from_amount).strip()
    if "." in amount_str:
        out["fromAmount"] = eth_amount_to_wei(amount_str)
    else:
        out["fromAmount"] = amount_str

    return out


def build_lifi_eth_to_usdc_quote_args(amount_eth: float, *, chain_id: int = BASE_CHAIN_ID) -> dict[str, Any]:
    return normalize_lifi_get_quote_args(
        {
            "fromChain": chain_id,
            "toChain": chain_id,
            "fromToken": BASE_WETH,
            "toToken": BASE_USDC,
            "fromAmount": amount_eth,
            "fromAddress": EVAL_FROM_ADDRESS,
        }
    )
