"""Vendor-specific MCP server connectors for Inspect eval tasks."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

from inspect_ai.tool import mcp_server_http, mcp_server_stdio

logger = logging.getLogger(__name__)

def _stdio_wrapper(inner: str) -> tuple[str, ...]:
    """Wrap a stdio MCP launch so only JSON-RPC lines reach the client on stdout.

    MCP stdio framing is newline-delimited JSON, so keeping only lines beginning
    with `{`/`[` strips any banner a misbehaving server prints to stdout. stderr is
    deliberately left intact (servers are told to log there) for debuggability.
    """
    return ("-c", f"{inner} | grep --line-buffered -E '^[{{[]'")


ODOS_STDIO_COMMAND = "bash"
ODOS_STDIO_ARGS = _stdio_wrapper("npx -y @iqai/mcp-odos")

# Jupiter (Solana) — read-only price/portfolio MCP, npm-published.
JUPITER_STDIO_COMMAND = "bash"
JUPITER_STDIO_ARGS = _stdio_wrapper("npx -y jupiter-mcp-server")

# KyberSwap is not published to npm; clone github.com/KyberNetwork/kyberswap-mcp,
# `npm install && npm run build`, then point KYBERSWAP_MCP_PATH at dist/index.js.
KYBERSWAP_STDIO_COMMAND = "bash"

HTTP_VENDORS = {
    "lifi": "LIFI_MCP_URL",
    "uniswap": "UNISWAP_MCP_URL",
    "1inch": "ONEINCH_MCP_URL",
}


@dataclass(frozen=True)
class HttpMcpConfig:
    url: str
    name: str
    headers: dict[str, str] | None = None


@dataclass(frozen=True)
class StdioMcpConfig:
    command: str
    args: list[str]
    name: str
    env: dict[str, str] | None = None


def _require_env(name: str) -> str:
    value = os.environ.get(name, "")
    if not value:
        raise EnvironmentError(
            f"{name} is not set. Set the live MCP endpoint in .env — no mock fallback."
        )
    return value


def _optional_env(mapping: dict[str, str]) -> dict[str, str]:
    """Build a child-process env from {source_var: target_var}, skipping unset sources."""
    out: dict[str, str] = {}
    for source, target in mapping.items():
        value = os.environ.get(source, "")
        if value:
            out[target] = value
    return out


def odos_stdio_env(*, require_wallet: bool) -> dict[str, str]:
    wallet = os.environ.get("WALLET_PRIVATE_KEY", "")
    if require_wallet and not wallet:
        raise EnvironmentError(
            "WALLET_PRIVATE_KEY is not set. Required for Odos swap evals — no mock fallback."
        )
    if wallet:
        return {"WALLET_PRIVATE_KEY": wallet}
    return {}


def odos_stdio_config(*, require_wallet: bool = False) -> StdioMcpConfig:
    return StdioMcpConfig(
        command=ODOS_STDIO_COMMAND,
        args=list(ODOS_STDIO_ARGS),
        name="odos-mcp",
        env=odos_stdio_env(require_wallet=require_wallet) or None,
    )


def jupiter_stdio_env() -> dict[str, str]:
    """Env for the read-only Jupiter price/portfolio MCP (no keypair needed).

    Our convention is SOLANA_RPC_URL; the server reads SOLANA_RPC_ENDPOINT.
    """
    return _optional_env(
        {"JUPITER_API_KEY": "JUPITER_API_KEY", "SOLANA_RPC_URL": "SOLANA_RPC_ENDPOINT"}
    )


def jupiter_stdio_config() -> StdioMcpConfig:
    return StdioMcpConfig(
        command=JUPITER_STDIO_COMMAND,
        args=list(JUPITER_STDIO_ARGS),
        name="jupiter-mcp",
        env=jupiter_stdio_env() or None,
    )


def kyberswap_stdio_config() -> StdioMcpConfig:
    """KyberSwap MCP launched from a locally built dist (KYBERSWAP_MCP_PATH)."""
    path = _require_env("KYBERSWAP_MCP_PATH")
    env = _optional_env({"KYBERSWAP_RPC_URL": "RPC_URL"})
    return StdioMcpConfig(
        command=KYBERSWAP_STDIO_COMMAND,
        args=list(_stdio_wrapper(f'node "{path}"')),
        name="kyberswap-mcp",
        env=env or None,
    )


def http_mcp_config(vendor: str) -> HttpMcpConfig:
    env_var = HTTP_VENDORS.get(vendor)
    if not env_var:
        raise ValueError(f"unknown HTTP MCP vendor: {vendor}")

    url = _require_env(env_var)
    headers: dict[str, str] | None = None
    if vendor == "lifi":
        api_key = os.environ.get("LIFI_API_KEY", "")
        if api_key:
            headers = {"X-LiFi-Api-Key": api_key}
    elif vendor == "1inch":
        api_key = os.environ.get("ONEINCH_API_KEY", "")
        if api_key:
            headers = {"Authorization": f"Bearer {api_key}"}

    return HttpMcpConfig(url=url, name=f"{vendor}-mcp", headers=headers)


def build_mcp_server(vendor: str, *, require_wallet: bool = False):
    """Return an Inspect MCP server config for the given eval vendor."""
    stdio_builders = {
        "odos": lambda: odos_stdio_config(require_wallet=require_wallet),
        "jupiter": jupiter_stdio_config,
        "kyberswap": kyberswap_stdio_config,
    }
    builder = stdio_builders.get(vendor)
    if builder is not None:
        cfg = builder()
        logger.info("%s stdio connector command=%s", vendor, cfg.command)
        return mcp_server_stdio(
            name=cfg.name,
            command=cfg.command,
            args=cfg.args,
            env=cfg.env,
        )

    cfg = http_mcp_config(vendor)
    logger.info("%s http connector url=%s", vendor, cfg.url)
    return mcp_server_http(url=cfg.url, name=cfg.name, headers=cfg.headers)
