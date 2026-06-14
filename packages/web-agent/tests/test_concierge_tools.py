"""Concierge marketplace tool helpers."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from goldenmcp_web_agent.concierge_tools import (
    marketplace_x402_script,
    quote_lookup_price_tool,
    run_paid_lookup_subprocess,
)


def test_marketplace_x402_script_path_exists():
    path = marketplace_x402_script()
    assert path.name == "marketplace_x402.ts"
    assert path.is_file()


def test_quote_lookup_price_tool(monkeypatch):
    monkeypatch.setenv("X402_PAYEE_ADDRESS", "0xabc")
    result = quote_lookup_price_tool("quote", 0.9)
    assert result["capability"] == "quote"
    assert result["min_score"] == 0.9
    assert result["price_usdc"] == pytest.approx(0.046, abs=1e-4)
    assert result["payee"] == "0xabc"
    assert result["network"] == "arc-testnet"


def test_run_paid_lookup_subprocess_missing_key(monkeypatch):
    monkeypatch.delenv("DEMO_PAYER_PRIVATE_KEY", raising=False)
    with pytest.raises(EnvironmentError, match="DEMO_PAYER_PRIVATE_KEY"):
        run_paid_lookup_subprocess("quote", 0.9)


def test_run_paid_lookup_subprocess_contract(monkeypatch, tmp_path):
    """Subprocess invokes bun with expected args (dry-run via fake bun)."""
    monkeypatch.setenv("DEMO_PAYER_PRIVATE_KEY", "0x" + "11" * 32)
    monkeypatch.setenv("MARKETPLACE_URL", "http://localhost:8091")

    fake_bun = tmp_path / "bun"
    fake_bun.write_text(
        "#!/usr/bin/env python3\n"
        "print('status=200 paid=0.0460 USDC')\n"
        "print('best MCP: lifi.eth endpoint=https://mcp composite=0.950')\n"
    )
    fake_bun.chmod(0o755)
    monkeypatch.setenv("PATH", f"{tmp_path}:{os.environ.get('PATH', '')}")

    # Patch which executable is used
    import goldenmcp_web_agent.concierge_tools as ct

    monkeypatch.setattr(ct, "_bun_executable", lambda: str(fake_bun))
    monkeypatch.setattr(ct, "_marketplace_mcp_ts_root", lambda: tmp_path)
    (tmp_path / "node_modules").mkdir()

    out = run_paid_lookup_subprocess("quote", 0.9)
    assert out["results"][0]["ens_name"] == "lifi.eth"
    assert out["results"][0]["composite"] == 0.95