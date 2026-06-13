#!/usr/bin/env python3
"""Register eval MCPs on Arc registry with Walrus agent URIs."""

from __future__ import annotations

import argparse
import logging
import os
import sys

from goldenmcp_identity import RegistryClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DEFAULT_MCPS = [
    {
        "name": "lifi",
        "mcp_endpoint": os.environ.get("LIFI_MCP_URL", ""),
        "agent_uri": "walrus://manifests/lifi",
        "ens_name": "lifi-quote.goldenmcp.eth",
    },
    {
        "name": "0x",
        "mcp_endpoint": os.environ.get("ZEROX_MCP_URL", ""),
        "agent_uri": "walrus://manifests/0x",
        "ens_name": "0x-quote.goldenmcp.eth",
    },
    {
        "name": "uniswap",
        "mcp_endpoint": os.environ.get("UNISWAP_MCP_URL", ""),
        "agent_uri": "walrus://manifests/uniswap",
        "ens_name": "uniswap-quote.goldenmcp.eth",
    },
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Register MCPs on Arc registry")
    parser.add_argument("--dry-run", action="store_true", help="Validate env only")
    args = parser.parse_args()

    missing = [m["name"] for m in DEFAULT_MCPS if not m["mcp_endpoint"]]
    if missing:
        logger.error("Missing MCP URLs for: %s — set LIFI_MCP_URL, ZEROX_MCP_URL, UNISWAP_MCP_URL", missing)
        return 1

    if args.dry_run:
        logger.info("dry-run ok — %d MCPs ready to register", len(DEFAULT_MCPS))
        return 0

    client = RegistryClient()
    for mcp in DEFAULT_MCPS:
        agent_id = client.register(
            mcp["name"],
            mcp["mcp_endpoint"],
            mcp["agent_uri"],
            mcp["ens_name"],
        )
        logger.info("registered %s agent_id=%s ens=%s", mcp["name"], agent_id, mcp["ens_name"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
