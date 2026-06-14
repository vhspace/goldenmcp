"""CLI helpers for web-agent."""

from __future__ import annotations

import json
import sys

from goldenmcp_web_agent.mcp_manifest import build_mcp_manifest


def emit_manifest() -> None:
    """Print MCP manifest JSON to stdout."""
    json.dump(build_mcp_manifest(), sys.stdout, indent=2)
    sys.stdout.write("\n")
