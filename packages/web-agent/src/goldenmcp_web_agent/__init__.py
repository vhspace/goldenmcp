"""GoldenMCP web concierge agent — Sonnet 4.6 + vendor MCPs + marketplace x402."""

from goldenmcp_web_agent.agent import AGENT_MODEL, CONCIERGE_SYSTEM_PROMPT
from goldenmcp_web_agent.mcp_manifest import VENDOR_NAMES, build_mcp_manifest
from goldenmcp_web_agent.pricing import BASE_USDC, price_for_threshold, price_string

__all__ = [
    "AGENT_MODEL",
    "BASE_USDC",
    "CONCIERGE_SYSTEM_PROMPT",
    "VENDOR_NAMES",
    "build_mcp_manifest",
    "price_for_threshold",
    "price_string",
]
