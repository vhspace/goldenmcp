"""Marketplace tools for the concierge agent."""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import httpx

from goldenmcp_web_agent.marketplace_tools import (
    build_lookup_request,
    marketplace_base_url,
    parse_payment_required,
    quote_lookup_price,
)

logger = logging.getLogger(__name__)

_PACKAGE_ROOT = Path(__file__).resolve().parents[2]
_REPO_ROOT = _PACKAGE_ROOT.parent.parent


def _bun_executable() -> str:
    bun = shutil.which("bun")
    if not bun:
        raise EnvironmentError("bun is not on PATH — required for x402 marketplace lookup")
    return bun


def marketplace_x402_script() -> Path:
    return _PACKAGE_ROOT / "ts" / "marketplace_x402.ts"


def _marketplace_mcp_ts_root() -> Path:
    explicit = os.environ.get("MARKETPLACE_MCP_TS_ROOT", "").strip()
    if explicit:
        return Path(explicit)
    return _REPO_ROOT / "packages" / "marketplace-mcp-ts"


def quote_lookup_price_tool(capability: str, min_score: float) -> dict[str, Any]:
    quote = quote_lookup_price(capability, min_score)
    return {
        "capability": quote.capability,
        "min_score": quote.min_score,
        "price_usdc": quote.price_usdc,
        "payee": quote.payee,
        "network": quote.network,
    }


async def get_scores_http(mcp: str, capability: str) -> dict[str, Any]:
    """POST /tools/get_scores without payment — expect 402 or result."""
    url = f"{marketplace_base_url()}/tools/get_scores"
    async with httpx.AsyncClient(timeout=30.0) as client:
        res = await client.post(url, json={"mcp": mcp, "capability": capability})
        data = res.json() if res.content else {}
        if res.status_code == 402:
            quote = parse_payment_required(
                {
                    **data,
                    "capability": capability,
                    "min_score": data.get("min_score", 0),
                }
            )
            return {
                "status": 402,
                "payment_required": True,
                "price_usdc": quote.price_usdc,
                "payee": quote.payee,
                "network": quote.network,
            }
        if not res.is_success:
            raise RuntimeError(f"get_scores failed HTTP {res.status_code}: {data}")
        return {"status": res.status_code, "scores": data}


def run_paid_lookup_subprocess(capability: str, min_score: float) -> dict[str, Any]:
    """Run real x402 paid lookup via bun + GatewayClient."""
    key = os.environ.get("DEMO_PAYER_PRIVATE_KEY", "")
    if not key:
        raise EnvironmentError(
            "DEMO_PAYER_PRIVATE_KEY is not set — required for paid marketplace lookup (no mock fallback)."
        )

    script = marketplace_x402_script()
    mcp_ts_root = _marketplace_mcp_ts_root()
    if not (mcp_ts_root / "node_modules").is_dir():
        raise EnvironmentError(
            f"marketplace-mcp-ts node_modules missing at {mcp_ts_root} — run: cd {mcp_ts_root} && bun install"
        )

    cmd = [
        _bun_executable(),
        "demo/lookup_agent.ts",
        "--capability",
        capability,
        "--min-score",
        str(min_score),
    ]
    env = os.environ.copy()
    env.setdefault("MARKETPLACE_URL", os.environ.get("MARKETPLACE_URL", "http://localhost:8091"))

    logger.info("paid lookup subprocess capability=%s min_score=%s", capability, min_score)
    proc = subprocess.run(
        cmd,
        cwd=str(mcp_ts_root),
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"paid lookup failed exit={proc.returncode} stderr={proc.stderr.strip()} stdout={proc.stdout.strip()}"
        )

    return _parse_lookup_subprocess_output(proc.stdout)


def _parse_lookup_subprocess_output(stdout: str) -> dict[str, Any]:
    """Parse marketplace_x402.ts stdout into structured lookup result."""
    lines = [ln.strip() for ln in stdout.splitlines() if ln.strip()]
    result: dict[str, Any] = {"paid": True, "raw_lines": lines}

    for line in lines:
        if line.startswith("best MCP:"):
            match = re.search(
                r"best MCP: (\S+) endpoint=(\S+) composite=([\d.]+)",
                line,
            )
            if match:
                result["results"] = [
                    {
                        "ens_name": match.group(1),
                        "mcp_endpoint": match.group(2),
                        "composite": float(match.group(3)),
                    }
                ]
        if line.startswith("settlement:"):
            result["transaction"] = line.split("settlement:", 1)[1].strip()
        if line.startswith("status="):
            result["status_line"] = line

    if "results" not in result:
        raise RuntimeError(f"could not parse paid lookup output: {stdout}")

    return result


async def lookup_unpaid_tool(capability: str, min_score: float) -> dict[str, Any]:
    from goldenmcp_web_agent.marketplace_tools import lookup_unpaid

    out = await lookup_unpaid(capability, min_score)
    if out.get("status") == 402:
        quote = out["quote"]
        return {
            "payment_required": True,
            "capability": quote.capability,
            "min_score": quote.min_score,
            "price_usdc": quote.price_usdc,
            "payee": quote.payee,
            "network": quote.network,
        }
    return out


def anthropic_tool_definitions() -> list[dict[str, Any]]:
    return [
        {
            "name": "quote_lookup_price",
            "description": "Quote USDC price for marketplace lookup before paying.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "capability": {
                        "type": "string",
                        "enum": ["quote", "route", "trade", "swap"],
                    },
                    "min_score": {"type": "number", "minimum": 0, "maximum": 1},
                },
                "required": ["capability", "min_score"],
            },
        },
        {
            "name": "lookup_mcp",
            "description": (
                "Pay x402 USDC on Arc and lookup the best scored MCP for capability + min_score."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "capability": {
                        "type": "string",
                        "enum": ["quote", "route", "trade", "swap"],
                    },
                    "min_score": {"type": "number", "minimum": 0, "maximum": 1},
                },
                "required": ["capability", "min_score"],
            },
        },
        {
            "name": "get_scores",
            "description": "Fetch on-chain registry scores for a specific mcp/capability pair.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "mcp": {"type": "string"},
                    "capability": {
                        "type": "string",
                        "enum": ["quote", "route", "trade", "swap"],
                    },
                },
                "required": ["mcp", "capability"],
            },
        },
        {
            "name": "parse_user_intent",
            "description": "Parse natural language DeFi intent into capability and min_score.",
            "input_schema": {
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
            },
        },
        {
            "name": "list_vendor_mcp_tools",
            "description": (
                "List tools on a vendor MCP (lifi, 1inch, odos, jupiter, kyberswap). "
                "Use after marketplace lookup returns a vendor."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "vendor": {
                        "type": "string",
                        "enum": ["lifi", "1inch", "odos", "jupiter", "kyberswap"],
                    },
                },
                "required": ["vendor"],
            },
        },
        {
            "name": "call_vendor_mcp_tool",
            "description": (
                "Call a read-only tool on a vendor MCP. Example: lifi get-chains, "
                "odos ODOS_GET_CHAIN_ID with chain Base, jupiter jupiter_get_price."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "vendor": {
                        "type": "string",
                        "enum": ["lifi", "1inch", "odos", "jupiter", "kyberswap"],
                    },
                    "tool_name": {"type": "string"},
                    "arguments": {"type": "object"},
                },
                "required": ["vendor", "tool_name", "arguments"],
            },
        },
        {
            "name": "probe_vendor_mcp",
            "description": "Smoke-probe a vendor MCP: list_tools + configured read-only tool call.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "vendor": {
                        "type": "string",
                        "enum": ["lifi", "1inch", "odos", "jupiter", "kyberswap"],
                    },
                },
                "required": ["vendor"],
            },
        },
    ]


async def execute_tool(name: str, tool_input: dict[str, Any]) -> str:
    if name == "quote_lookup_price":
        out = quote_lookup_price_tool(tool_input["capability"], float(tool_input["min_score"]))
        return json.dumps(out)
    if name == "lookup_mcp":
        out = run_paid_lookup_subprocess(tool_input["capability"], float(tool_input["min_score"]))
        return json.dumps(out)
    if name == "get_scores":
        out = await get_scores_http(tool_input["mcp"], tool_input["capability"])
        return json.dumps(out)
    if name == "parse_user_intent":
        from goldenmcp_web_agent.intent import parse_demo_prompt

        intent = parse_demo_prompt(tool_input["text"])
        return json.dumps(
            {
                "action": intent.action,
                "assets_from": intent.assets_from,
                "assets_to": intent.assets_to,
                "amount_usd": intent.amount_usd,
                "min_reliability_score": intent.min_reliability_score,
                "marketplace_capability": intent.marketplace_capability,
                "objective": intent.objective,
            }
        )
    if name == "list_vendor_mcp_tools":
        from goldenmcp_web_agent.vendor_mcp import list_vendor_tools

        tools = await list_vendor_tools(tool_input["vendor"])
        return json.dumps({"vendor": tool_input["vendor"], "tools": tools})
    if name == "call_vendor_mcp_tool":
        from goldenmcp_web_agent.vendor_mcp import call_vendor_tool

        out = await call_vendor_tool(
            tool_input["vendor"],
            tool_input["tool_name"],
            tool_input.get("arguments") or {},
        )
        return json.dumps(
            {
                "vendor": tool_input["vendor"],
                "tool_name": tool_input["tool_name"],
                "result": out,
            }
        )
    if name == "probe_vendor_mcp":
        from goldenmcp_web_agent.vendor_mcp import probe_vendor

        result = await probe_vendor(tool_input["vendor"])
        return json.dumps(result.to_dict())
    raise ValueError(f"unknown tool: {name}")
