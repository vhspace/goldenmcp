"""MCP manifest covers all eval vendors plus marketplace."""

from __future__ import annotations

import json

import pytest

from goldenmcp_web_agent.mcp_manifest import VENDOR_NAMES, build_mcp_manifest


def test_manifest_includes_all_vendors(monkeypatch):
    monkeypatch.setenv("LIFI_MCP_URL", "https://mcp.li.quest/mcp")
    monkeypatch.setenv("ONEINCH_MCP_URL", "https://api.1inch.com/mcp/protocol")
    monkeypatch.setenv("KYBERSWAP_MCP_PATH", "/tmp/kyberswap-mcp/dist/index.js")
    monkeypatch.setenv("MARKETPLACE_URL", "http://localhost:8091")

    manifest = build_mcp_manifest()
    servers = manifest["mcpServers"]

    for name in VENDOR_NAMES:
        assert name in servers, f"missing vendor MCP: {name}"

    assert "goldenmcp-marketplace" in servers
    assert servers["goldenmcp-marketplace"]["url"] == "http://localhost:8091"


def test_manifest_http_vendor_has_url(monkeypatch):
    monkeypatch.setenv("LIFI_MCP_URL", "https://mcp.li.quest/mcp")
    monkeypatch.setenv("ONEINCH_MCP_URL", "https://api.1inch.com/mcp/protocol")
    monkeypatch.setenv("KYBERSWAP_MCP_PATH", "/tmp/kyberswap-mcp/dist/index.js")
    monkeypatch.setenv("MARKETPLACE_URL", "http://localhost:8091")

    manifest = build_mcp_manifest()
    lifi = manifest["mcpServers"]["lifi-mcp"]
    assert lifi["type"] == "http"
    assert lifi["url"] == "https://mcp.li.quest/mcp"


def test_manifest_stdio_vendor_has_command(monkeypatch):
    monkeypatch.setenv("LIFI_MCP_URL", "https://mcp.li.quest/mcp")
    monkeypatch.setenv("ONEINCH_MCP_URL", "https://api.1inch.com/mcp/protocol")
    monkeypatch.setenv("KYBERSWAP_MCP_PATH", "/tmp/kyberswap-mcp/dist/index.js")
    monkeypatch.setenv("MARKETPLACE_URL", "http://localhost:8091")

    manifest = build_mcp_manifest()
    odos = manifest["mcpServers"]["odos-mcp"]
    assert odos["type"] == "stdio"
    assert odos["command"] == "bash"
    assert any("@iqai/mcp-odos" in str(arg) for arg in odos["args"])


def test_manifest_serializes_to_json(monkeypatch):
    monkeypatch.setenv("LIFI_MCP_URL", "https://mcp.li.quest/mcp")
    monkeypatch.setenv("ONEINCH_MCP_URL", "https://api.1inch.com/mcp/protocol")
    monkeypatch.setenv("KYBERSWAP_MCP_PATH", "/tmp/kyberswap-mcp/dist/index.js")
    monkeypatch.setenv("MARKETPLACE_URL", "http://localhost:8091")

    raw = json.dumps(build_mcp_manifest())
    assert "goldenmcp-marketplace" in raw
