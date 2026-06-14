"""Build Cursor/Claude MCP server manifest from inspect-web3 connectors."""

from __future__ import annotations

import os
from typing import Any

from goldenmcp_inspect.mcp_connectors import (
    http_mcp_config,
    jupiter_stdio_config,
    kyberswap_stdio_config,
    odos_stdio_config,
)

VENDOR_NAMES = ("lifi-mcp", "1inch-mcp", "odos-mcp", "jupiter-mcp", "kyberswap-mcp")


def _stdio_entry(cfg) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "type": "stdio",
        "command": cfg.command,
        "args": list(cfg.args),
    }
    if cfg.env:
        entry["env"] = dict(cfg.env)
    return entry


def _http_entry(cfg) -> dict[str, Any]:
    entry: dict[str, Any] = {"type": "http", "url": cfg.url}
    if cfg.headers:
        entry["headers"] = dict(cfg.headers)
    return entry


def build_mcp_manifest() -> dict[str, Any]:
    """Return MCP config dict for all eval vendors plus marketplace HTTP base URL."""
    marketplace_url = os.environ.get("MARKETPLACE_URL", "http://localhost:8091").rstrip("/")

    servers: dict[str, Any] = {
        "lifi-mcp": _http_entry(http_mcp_config("lifi")),
        "1inch-mcp": _http_entry(http_mcp_config("1inch")),
        "odos-mcp": _stdio_entry(odos_stdio_config(require_wallet=False)),
        "jupiter-mcp": _stdio_entry(jupiter_stdio_config()),
        "kyberswap-mcp": _stdio_entry(kyberswap_stdio_config()),
        "goldenmcp-marketplace": {
            "type": "http",
            "url": marketplace_url,
            "description": (
                "x402-gated MCP discovery. Tools: POST /tools/lookup, "
                "/tools/get_scores. Pay via ts/marketplace_x402.ts GatewayClient."
            ),
        },
    }

    return {"mcpServers": servers}
