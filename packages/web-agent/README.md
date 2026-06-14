# goldenmcp-web-agent

Sonnet 4.6 concierge agent for the embedded Web3 chat. Pre-wires all eval vendor MCPs
and the GoldenMCP marketplace with x402 USDC pricing.

## Quick start

```bash
# From repo root (worktree)
uv sync --all-packages
chmod +x packages/web-agent/scripts/install-mcps.sh
./packages/web-agent/scripts/install-mcps.sh

# Emit MCP manifest for Cursor / Claude Code
uv run goldenmcp-mcp-manifest > .cursor/mcp-goldenmcp.json
```

## Paid marketplace lookup

```bash
cd packages/web-agent
# Reuses marketplace-mcp-ts deps via path import
DEMO_PAYER_PRIVATE_KEY=0x... MARKETPLACE_URL=http://localhost:8091 \
  bun ts/marketplace_x402.ts --capability quote --min-score 0.9
```

Requires `packages/marketplace-mcp-ts` `node_modules` (`bun install` there first).

## Model

`WEB_AGENT_MODEL` defaults to `anthropic/claude-sonnet-4-20250514`.

## Vendor MCP smoke (no evals)

Direct CLI probe (`list_tools` + read-only call per vendor):

```bash
# From repo root (worktree), with .env sourced
uv run goldenmcp-smoke-mcps
```

Requires `LIFI_MCP_URL`, `ONEINCH_MCP_URL`, `WALLET_PRIVATE_KEY` (odos), and a built
`KYBERSWAP_MCP_PATH` (see `scripts/install-mcps.sh`).

Concierge chat smoke (Sonnet calls `probe_vendor_mcp` for each vendor):

```bash
curl -sN -X POST http://127.0.0.1:8092/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"Smoke: probe_vendor_mcp for lifi, 1inch, odos, jupiter, kyberswap."}'
```

## See also

- Plan: `docs/plans/2026-06-13-web-concierge-agent.md`
- Vendor connectors: `packages/inspect-web3/src/goldenmcp_inspect/mcp_connectors.py`
- Marketplace seller: `packages/marketplace-mcp-ts/`
