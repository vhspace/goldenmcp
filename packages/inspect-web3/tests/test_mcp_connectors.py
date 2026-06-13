"""Tests for vendor MCP connector configuration."""

from __future__ import annotations

import urllib.parse

import pytest

from goldenmcp_inspect import mcp_connectors
from goldenmcp_inspect.mcp_connectors import (
    ODOS_STDIO_ARGS,
    ODOS_STDIO_COMMAND,
    SSE_VENDORS,
    build_mcp_server,
    http_mcp_config,
    jupiter_stdio_config,
    jupiter_stdio_env,
    kyberswap_stdio_config,
    odos_stdio_config,
    odos_stdio_env,
)


def test_odos_stdio_uses_bash_grep_filter():
    cfg = odos_stdio_config()
    assert cfg.command == "bash"
    assert "-c" in cfg.args
    assert "npx -y @iqai/mcp-odos" in cfg.args[1]
    assert "grep --line-buffered -E '^[{[]'" in cfg.args[1]
    assert cfg.name == "odos-mcp"


def test_odos_stdio_env_requires_wallet_for_swap(monkeypatch):
    monkeypatch.delenv("WALLET_PRIVATE_KEY", raising=False)
    with pytest.raises(EnvironmentError, match="WALLET_PRIVATE_KEY"):
        odos_stdio_env(require_wallet=True)


def test_odos_stdio_env_strips_0x_prefix(monkeypatch):
    # @iqai/mcp-odos's viem parser wants the bare hex key, not 0x-prefixed.
    monkeypatch.setenv("WALLET_PRIVATE_KEY", "0xabc")
    env = odos_stdio_env(require_wallet=False)
    assert env["WALLET_PRIVATE_KEY"] == "abc"


def test_odos_stdio_env_passes_bare_wallet_unchanged(monkeypatch):
    monkeypatch.setenv("WALLET_PRIVATE_KEY", "abc")
    monkeypatch.delenv("ODOS_API_KEY", raising=False)
    env = odos_stdio_env(require_wallet=False)
    assert env["WALLET_PRIVATE_KEY"] == "abc"
    # No key set → no preload, so the package hits the public (rate-limited) API.
    assert "ODOS_API_KEY" not in env
    assert "NODE_OPTIONS" not in env


def test_odos_stdio_env_injects_api_key_via_node_import(monkeypatch):
    # @iqai/mcp-odos has no key hook, so we pass the key to the child and preload a
    # Node fetch shim (via --import) that adds the x-api-key header for api.odos.xyz.
    monkeypatch.setenv("WALLET_PRIVATE_KEY", "abc")
    monkeypatch.setenv("ODOS_API_KEY", "uuid-key-123")
    env = odos_stdio_env(require_wallet=False)
    assert env["ODOS_API_KEY"] == "uuid-key-123"
    node_options = env["NODE_OPTIONS"]
    assert node_options.startswith("--import data:text/javascript,")
    # Shim must read the key from env (never inlined) and target the Odos host.
    assert "uuid-key-123" not in node_options
    assert "ODOS_API_KEY" in urllib.parse.unquote(node_options)
    assert "api.odos.xyz" in urllib.parse.unquote(node_options)
    assert "x-api-key" in urllib.parse.unquote(node_options)


def test_lifi_http_requires_url(monkeypatch):
    monkeypatch.delenv("LIFI_MCP_URL", raising=False)
    with pytest.raises(EnvironmentError, match="LIFI_MCP_URL"):
        http_mcp_config("lifi")


def test_lifi_http_includes_api_key_header(monkeypatch):
    monkeypatch.setenv("LIFI_MCP_URL", "https://mcp.li.quest/mcp")
    monkeypatch.setenv("LIFI_API_KEY", "test-key")
    cfg = http_mcp_config("lifi")
    assert cfg.url == "https://mcp.li.quest/mcp"
    assert cfg.headers is not None
    assert cfg.headers["X-LiFi-Api-Key"] == "test-key"


def test_odos_command_constant_matches_server_config():
    assert ODOS_STDIO_COMMAND == "bash"
    assert "grep --line-buffered -E '^[{[]'" in ODOS_STDIO_ARGS[1]


def test_oneinch_http_requires_url(monkeypatch):
    monkeypatch.delenv("ONEINCH_MCP_URL", raising=False)
    with pytest.raises(EnvironmentError, match="ONEINCH_MCP_URL"):
        http_mcp_config("1inch")


def test_oneinch_http_includes_bearer_header(monkeypatch):
    # The working endpoint is the official Streamable-HTTP host
    # https://api.1inch.com/mcp/protocol, authenticated with a Bearer key.
    monkeypatch.setenv("ONEINCH_MCP_URL", "https://api.1inch.com/mcp/protocol")
    monkeypatch.setenv("ONEINCH_API_KEY", "test-key")
    cfg = http_mcp_config("1inch")
    assert cfg.url == "https://api.1inch.com/mcp/protocol"
    assert cfg.headers is not None
    assert cfg.headers["Authorization"] == "Bearer test-key"


def test_oneinch_is_not_sse_vendor():
    # 1inch's official Business MCP (api.1inch.com/mcp/protocol) is stateless
    # Streamable-HTTP, so it routes through the default HTTP path, not SSE. The
    # old api.1inch.dev/mcp/sse endpoint was a dead end (no session affinity).
    assert "1inch" not in SSE_VENDORS
    assert SSE_VENDORS == set()


def test_oneinch_build_routes_via_http_with_bearer(monkeypatch):
    monkeypatch.setenv("ONEINCH_MCP_URL", "https://api.1inch.com/mcp/protocol")
    monkeypatch.setenv("ONEINCH_API_KEY", "test-key")

    calls: dict[str, dict] = {}

    def fake_http(**kwargs):
        calls["http"] = kwargs
        return object()

    def fake_sse(**kwargs):  # pragma: no cover - asserted not called
        calls["sse"] = kwargs
        return object()

    monkeypatch.setattr(mcp_connectors, "mcp_server_http", fake_http)
    monkeypatch.setattr(mcp_connectors, "mcp_server_sse", fake_sse)

    build_mcp_server("1inch")

    assert "http" in calls
    assert "sse" not in calls
    assert calls["http"]["url"] == "https://api.1inch.com/mcp/protocol"
    assert calls["http"]["headers"]["Authorization"] == "Bearer test-key"


def test_jupiter_stdio_uses_npx_package():
    cfg = jupiter_stdio_config()
    assert cfg.command == "bash"
    assert "npx -y jupiter-mcp-server" in cfg.args[1]
    assert "grep --line-buffered -E '^[{[]'" in cfg.args[1]
    assert cfg.name == "jupiter-mcp"


def test_jupiter_stdio_env_maps_solana_rpc(monkeypatch):
    monkeypatch.setenv("JUPITER_API_KEY", "jup-key")
    monkeypatch.setenv("SOLANA_RPC_URL", "https://rpc.example/solana")
    env = jupiter_stdio_env()
    assert env["JUPITER_API_KEY"] == "jup-key"
    # Our SOLANA_RPC_URL is mapped to the server's SOLANA_RPC_ENDPOINT var.
    assert env["SOLANA_RPC_ENDPOINT"] == "https://rpc.example/solana"


def test_jupiter_stdio_env_needs_no_keypair(monkeypatch):
    # Read-only price/portfolio tools: must work with no key set at all.
    monkeypatch.delenv("JUPITER_API_KEY", raising=False)
    monkeypatch.delenv("SOLANA_RPC_URL", raising=False)
    monkeypatch.delenv("SOLANA_PRIVATE_KEY", raising=False)
    assert jupiter_stdio_env() == {}


def test_kyberswap_stdio_requires_path(monkeypatch):
    monkeypatch.delenv("KYBERSWAP_MCP_PATH", raising=False)
    with pytest.raises(EnvironmentError, match="KYBERSWAP_MCP_PATH"):
        kyberswap_stdio_config()


def test_kyberswap_stdio_launches_node_at_path(monkeypatch):
    monkeypatch.setenv("KYBERSWAP_MCP_PATH", "/opt/kyberswap-mcp/dist/index.js")
    cfg = kyberswap_stdio_config()
    assert cfg.command == "bash"
    assert 'node "/opt/kyberswap-mcp/dist/index.js"' in cfg.args[1]
    assert cfg.name == "kyberswap-mcp"
