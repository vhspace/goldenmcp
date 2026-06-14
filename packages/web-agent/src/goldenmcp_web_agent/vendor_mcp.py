"""Live vendor MCP probes for concierge — no evals, direct MCP list_tools + call_tool."""

from __future__ import annotations

import logging
import os
import urllib.parse
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, AsyncIterator

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.client.streamable_http import streamablehttp_client

from goldenmcp_inspect.mcp_connectors import (
    HTTP_VENDORS,
    http_mcp_config,
    jupiter_stdio_config,
    kyberswap_stdio_config,
    odos_stdio_env,
    odos_stdio_config,
)

from goldenmcp_web_agent.lifi_quote import normalize_lifi_get_quote_args

logger = logging.getLogger(__name__)

BASE_USDC = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
MAX_TOOL_RESULT_CHARS = 12_000

VENDOR_NAMES = ("lifi", "1inch", "odos", "jupiter", "kyberswap")

# Read-only probe per vendor (tool name, arguments).
VENDOR_SMOKE_PROBES: dict[str, tuple[str, dict[str, Any]]] = {
    "lifi": ("get-chains", {}),
    "1inch": ("list_examples", {}),
    "odos": ("ODOS_GET_CHAIN_ID", {"chain": "Base"}),
    "jupiter": ("jupiter_get_platforms", {}),
    "kyberswap": (
        "token-info",
        {"chain": "base", "token": "USDC"},
    ),
}


@dataclass(frozen=True)
class VendorProbeResult:
    vendor: str
    ok: bool
    tool_count: int
    tools: list[str]
    probe_tool: str | None = None
    probe_preview: str | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "vendor": self.vendor,
            "ok": self.ok,
            "tool_count": self.tool_count,
            "tools": self.tools,
            "probe_tool": self.probe_tool,
            "probe_preview": self.probe_preview,
            "error": self.error,
        }


def _odos_stdio_env() -> dict[str, str]:
    """Odos child env including optional API-key fetch shim (see mcp_connectors)."""
    env = dict(odos_stdio_env(require_wallet=False))
    api_key = os.environ.get("ODOS_API_KEY", "")
    if api_key and "NODE_OPTIONS" not in env:
        shim = (
            "const _f=globalThis.fetch;const k=process.env.ODOS_API_KEY;"
            'globalThis.fetch=(u,o={})=>{try{const s=typeof u==="string"?u:(u&&u.url)||"";'
            'if(k&&s.includes("api.odos.xyz")){o={...o,headers:{...(o.headers||{}),"x-api-key":k}};}}'
            "catch(e){}return _f(u,o);};"
        )
        env["ODOS_API_KEY"] = api_key
        env["NODE_OPTIONS"] = f"--import data:text/javascript,{urllib.parse.quote(shim)}"
    return env


def _stdio_params(vendor: str) -> StdioServerParameters:
    if vendor == "odos":
        cfg = odos_stdio_config(require_wallet=False)
        env = _odos_stdio_env()
    elif vendor == "jupiter":
        cfg = jupiter_stdio_config()
        env = dict(cfg.env or {})
    elif vendor == "kyberswap":
        cfg = kyberswap_stdio_config()
        env = dict(cfg.env or {})
    else:
        raise ValueError(f"not a stdio vendor: {vendor}")

    merged = os.environ.copy()
    merged.update(env)
    return StdioServerParameters(command=cfg.command, args=list(cfg.args), env=merged)


@asynccontextmanager
async def vendor_mcp_session(vendor: str) -> AsyncIterator[ClientSession]:
    """Open an MCP ClientSession for a eval vendor (HTTP or stdio)."""
    if vendor in HTTP_VENDORS:
        cfg = http_mcp_config(vendor)
        async with streamablehttp_client(cfg.url, headers=cfg.headers) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                yield session
        return

    params = _stdio_params(vendor)
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session


def _unwrap_exception(exc: BaseException) -> BaseException:
    """Flatten asyncio ExceptionGroup / TaskGroup wrappers from MCP HTTP teardown."""
    if isinstance(exc, BaseExceptionGroup) and exc.exceptions:
        return _unwrap_exception(exc.exceptions[0])
    return exc


def _prepare_vendor_tool_args(vendor: str, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    if vendor == "lifi" and tool_name == "get-quote":
        return normalize_lifi_get_quote_args(arguments)
    return arguments


def _truncate_text(text: str, limit: int = MAX_TOOL_RESULT_CHARS) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


async def list_vendor_tools(vendor: str) -> list[str]:
    async with vendor_mcp_session(vendor) as session:
        listed = await session.list_tools()
        return [t.name for t in listed.tools]


async def call_vendor_tool(vendor: str, tool_name: str, arguments: dict[str, Any]) -> str:
    arguments = _prepare_vendor_tool_args(vendor, tool_name, arguments)
    err: BaseException | None = None
    out: str | None = None
    try:
        async with vendor_mcp_session(vendor) as session:
            result = await session.call_tool(tool_name, arguments)
            if getattr(result, "isError", False):
                preview = _content_preview(result.content, limit=500)
                err = RuntimeError(f"{vendor} tool {tool_name} failed: {preview}")
            else:
                parts = []
                for block in result.content:
                    text = getattr(block, "text", None)
                    parts.append(str(text) if text is not None else str(block))
                if not parts:
                    err = RuntimeError(f"{vendor} tool {tool_name} returned empty content")
                else:
                    out = _truncate_text("\n".join(parts))
    except BaseException as exc:
        err = _unwrap_exception(exc)

    if err is not None:
        raise err
    assert out is not None
    return out


async def probe_vendor(vendor: str, *, run_call: bool = True) -> VendorProbeResult:
    probe = VENDOR_SMOKE_PROBES.get(vendor)
    if probe is None:
        raise ValueError(f"no smoke probe configured for vendor={vendor}")

    try:
        async with vendor_mcp_session(vendor) as session:
            listed = await session.list_tools()
            names = [t.name for t in listed.tools]
            if not names:
                return VendorProbeResult(
                    vendor=vendor,
                    ok=False,
                    tool_count=0,
                    tools=[],
                    error="list_tools returned zero tools",
                )

            probe_tool, probe_args = probe
            if probe_tool not in names:
                return VendorProbeResult(
                    vendor=vendor,
                    ok=False,
                    tool_count=len(names),
                    tools=names[:12],
                    probe_tool=probe_tool,
                    error=f"probe tool {probe_tool!r} not in listing",
                )

            preview = None
            if run_call:
                res = await session.call_tool(probe_tool, probe_args)
                if getattr(res, "isError", False):
                    preview = _content_preview(res.content)
                    return VendorProbeResult(
                        vendor=vendor,
                        ok=False,
                        tool_count=len(names),
                        tools=names[:12],
                        probe_tool=probe_tool,
                        probe_preview=preview,
                        error=f"probe tool {probe_tool!r} returned isError=true",
                    )
                preview = _content_preview(res.content)

            return VendorProbeResult(
                vendor=vendor,
                ok=True,
                tool_count=len(names),
                tools=names[:12],
                probe_tool=probe_tool,
                probe_preview=preview,
            )
    except BaseException as exc:
        logger.exception("vendor probe failed vendor=%s", vendor)
        unwrapped = _unwrap_exception(exc)
        return VendorProbeResult(
            vendor=vendor,
            ok=False,
            tool_count=0,
            tools=[],
            error=str(unwrapped),
        )


def _content_preview(content: Any, limit: int = 240) -> str:
    parts: list[str] = []
    for block in content:
        text = getattr(block, "text", None)
        parts.append(str(text) if text is not None else str(block))
    joined = "\n".join(parts)
    return joined if len(joined) <= limit else joined[: limit - 3] + "..."


async def smoke_all_vendors(*, vendors: tuple[str, ...] = VENDOR_NAMES) -> list[VendorProbeResult]:
    results: list[VendorProbeResult] = []
    for vendor in vendors:
        logger.info("smoke probe vendor=%s", vendor)
        results.append(await probe_vendor(vendor))
    return results
