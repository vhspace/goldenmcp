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
        "name": "odos",
        "mcp_endpoint": "stdio:npx/@iqai/mcp-odos",
        "agent_uri": "walrus://manifests/odos",
        "ens_name": "odos-quote.goldenmcp.eth",
    },
    {
        "name": "1inch",
        "mcp_endpoint": os.environ.get("ONEINCH_MCP_URL", ""),
        "agent_uri": "walrus://manifests/1inch",
        "ens_name": "1inch-quote.goldenmcp.eth",
    },
    {
        "name": "kyberswap",
        "mcp_endpoint": "stdio:node/kyberswap-mcp",
        "agent_uri": "walrus://manifests/kyberswap",
        "ens_name": "kyberswap-quote.goldenmcp.eth",
    },
    {
        "name": "jupiter",
        "mcp_endpoint": "stdio:npx/jupiter-mcp-server",
        "agent_uri": "walrus://manifests/jupiter",
        "ens_name": "jupiter-quote.goldenmcp.eth",
    },
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Register MCPs on Arc registry")
    parser.add_argument("--dry-run", action="store_true", help="Validate env only")
    args = parser.parse_args()

    url_missing = [m["name"] for m in DEFAULT_MCPS if not m["mcp_endpoint"]]
    if url_missing:
        logger.error(
            "Missing MCP endpoints for: %s — set LIFI_MCP_URL, ONEINCH_MCP_URL (odos/kyberswap/jupiter are stdio)",
            url_missing,
        )
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
