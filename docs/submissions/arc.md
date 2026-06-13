# Arc Bounty Submission

## Integration

- MCPRegistry deployed on Arc testnet
- Marketplace MCP (`packages/marketplace-mcp/`) settles x402 USDC micropayments
- Tiered pricing: `base_usdc * (1 + 4 * min_score)`
- Agent demo: `demo/lookup_agent.py`

## Demo

```bash
uv run python -m goldenmcp_marketplace
uv run python demo/lookup_agent.py --capability quote --min-score 0.9
```

## Code

- `contracts/mcp-registry/src/MCPRegistry.sol`
- `packages/marketplace-mcp/src/goldenmcp_marketplace/app.py`
