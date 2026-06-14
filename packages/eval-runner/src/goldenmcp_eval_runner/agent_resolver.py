"""Resolve an MCP name to its onchain agent id via the Arc registry.

The CRE rotation needs each benchmark's score to write to ITS MCP's agent id
(not a fixed default). The registry exposes a public `nameToAgentId(string)`
mapping; this reads it over Arc RPC and caches the result. Best-effort: any
failure (no RPC configured, unregistered name, RPC error) returns 0, and the
caller falls back to the workflow's defaultAgentId.
"""

from __future__ import annotations

from functools import lru_cache

from web3 import Web3

# Minimal ABI: just the public nameToAgentId getter.
_REGISTRY_ABI = [
    {
        "inputs": [{"name": "", "type": "string"}],
        "name": "nameToAgentId",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    }
]


@lru_cache(maxsize=1)
def _contract(rpc_url: str, registry_address: str):
    w3 = Web3(Web3.HTTPProvider(rpc_url))
    return w3.eth.contract(address=Web3.to_checksum_address(registry_address), abi=_REGISTRY_ABI)


@lru_cache(maxsize=64)
def resolve_agent_id(mcp: str, rpc_url: str, registry_address: str) -> int:
    """Return the agent id registered for `mcp`, or 0 if unresolved/unconfigured."""
    if not rpc_url or not registry_address:
        return 0
    try:
        return int(_contract(rpc_url, registry_address).functions.nameToAgentId(mcp).call())
    except Exception:  # noqa: BLE001 — best-effort; caller falls back to default
        return 0
