"""Natural-language demo prompt → orchestration intent (parity with apps/web intent.ts)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

Capability = Literal["quote", "route", "trade", "swap"]

_TOKEN = r"[A-Z]{2,10}"


@dataclass(frozen=True)
class ParsedIntent:
    action: str
    assets_from: str | None
    assets_to: str | None
    amount_usd: float | None
    min_reliability_score: float
    marketplace_capability: Capability
    objective: str
    raw_prompt: str


def _parse_explicit_min_score(text: str) -> float | None:
    patterns = [
        r"(?:≥|>=|at least|min(?:imum)?(?: reliability)?)\s*(0\.\d+|1(?:\.0)?)",
        r"reliability\s*(?:≥|>=)\s*(0\.\d+|1(?:\.0)?)",
        r"min[_\s-]?score\s*(?:of|:)?\s*(0\.\d+|1(?:\.0)?)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            return min(1.0, max(0.0, float(match.group(1))))
    return None


def _infer_min_score(text: str) -> float:
    explicit = _parse_explicit_min_score(text)
    if explicit is not None:
        return explicit
    lower = text.lower()
    if re.search(r"lowest execution time|fastest|lowest latency|optimize portfolio", lower):
        return 0.9
    if re.search(r"best quote|reliable|trust", lower):
        return 0.85
    return 0.8


def _parse_action(text: str) -> tuple[str, Capability]:
    lower = text.lower()
    if re.search(r"\bswap\b", lower):
        return "DeFi Swap", "swap"
    if re.search(r"\btrade\b", lower):
        return "DeFi Trade", "trade"
    if re.search(r"\broute\b", lower):
        return "DeFi Route", "route"
    if re.search(r"\bquote\b", lower):
        return "DeFi Quote", "quote"
    return "DeFi Operation", "quote"


def _parse_asset_pair(text: str) -> tuple[str, str] | None:
    slash = re.search(rf"\b({_TOKEN})\s*/\s*({_TOKEN})\b", text)
    if slash:
        return slash.group(1), slash.group(2)

    for_pattern = re.search(
        rf"\$?\d+(?:\.\d+)?\s*({_TOKEN})\s+(?:for|to|→)\s+({_TOKEN})\b",
        text,
        re.I,
    )
    if for_pattern:
        return for_pattern.group(1), for_pattern.group(2)

    to_pattern = re.search(rf"\b({_TOKEN})\s+(?:to|→)\s+({_TOKEN})\b", text, re.I)
    if to_pattern:
        return to_pattern.group(1), to_pattern.group(2)

    return None


def _parse_amount_usd(text: str) -> float | None:
    match = re.search(r"\$\s*(\d+(?:\.\d+)?)", text)
    if match:
        return float(match.group(1))
    bare = re.search(rf"\b(\d+(?:\.\d+)?)\s+({_TOKEN})\s+(?:to|for|→)", text, re.I)
    if bare:
        return float(bare.group(1))
    return None


def _parse_objective(text: str) -> str:
    lower = text.lower()
    if re.search(r"lowest execution time|fastest", lower):
        return "Minimize execution time"
    if re.search(r"best quote", lower):
        return "Maximize quote quality"
    if re.search(r"route.*l2", lower):
        return "Optimal L2 routing"
    if re.search(r"optimize portfolio", lower):
        return "Portfolio optimization"
    return "Match capability to intent"


def parse_demo_prompt(text: str) -> ParsedIntent:
    trimmed = text.strip()
    if not trimmed:
        raise ValueError("Prompt text is empty")

    action, capability = _parse_action(trimmed)
    pair = _parse_asset_pair(trimmed)
    assets_from, assets_to = (pair if pair else (None, None))

    return ParsedIntent(
        action=action,
        assets_from=assets_from,
        assets_to=assets_to,
        amount_usd=_parse_amount_usd(trimmed),
        min_reliability_score=_infer_min_score(trimmed),
        marketplace_capability=capability,
        objective=_parse_objective(trimmed),
        raw_prompt=trimmed,
    )
