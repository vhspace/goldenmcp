"""Vendor MCP bridge tests."""

from __future__ import annotations

import pytest

from goldenmcp_web_agent.vendor_mcp import (
    VENDOR_NAMES,
    VENDOR_SMOKE_PROBES,
    VendorProbeResult,
)


def test_all_vendors_have_smoke_probes():
    for vendor in VENDOR_NAMES:
        assert vendor in VENDOR_SMOKE_PROBES
        tool, args = VENDOR_SMOKE_PROBES[vendor]
        assert isinstance(tool, str) and tool
        assert isinstance(args, dict)


def test_vendor_probe_result_serializes():
    r = VendorProbeResult(
        vendor="lifi",
        ok=True,
        tool_count=25,
        tools=["get-chains"],
        probe_tool="get-chains",
        probe_preview='{"chains":[]}',
    )
    d = r.to_dict()
    assert d["vendor"] == "lifi"
    assert d["ok"] is True
    assert d["tool_count"] == 25


@pytest.mark.integration
@pytest.mark.asyncio
async def test_live_vendor_mcp_smoke():
    """Live probe of all vendor MCPs — requires network + env (KYBERSWAP_MCP_PATH for kyberswap)."""
    import os

    if os.environ.get("GOLDENMCP_SMOKE_MCPS") != "1":
        pytest.skip("set GOLDENMCP_SMOKE_MCPS=1 to run live vendor MCP smoke")

    from goldenmcp_web_agent.vendor_mcp import smoke_all_vendors

    results = await smoke_all_vendors()
    failed = [r for r in results if not r.ok]
    assert not failed, failed
