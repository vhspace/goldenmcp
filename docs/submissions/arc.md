# Arc Bounty Submission

## Integration

- MCPRegistry deployed on Arc testnet (chainId 5042002)
- Marketplace seller (`packages/marketplace-mcp-ts/`) accepts **gasless x402 USDC nanopayments**
  via Circle Gateway — buyers sign offchain authorizations, Circle's hosted facilitator
  (`https://gateway-api-testnet.circle.com`) batches and settles onchain
- Tiered pricing: `base_usdc * (1 + 4 * min_score)`
- Buyer agent demo: `packages/marketplace-mcp-ts/demo/lookup_agent.ts` (Circle `GatewayClient`)

## Demo

```bash
cd packages/marketplace-mcp-ts && bun install

# Seller (needs X402_PAYEE_ADDRESS, ARC_RPC_URL, ARC_REGISTRY_ADDRESS, WALRUS_AGGREGATOR_URL)
bun src/server.ts

# Buyer (EOA funded with Arc testnet USDC + native gas; deposits into Gateway once, then gasless)
DEMO_PAYER_PRIVATE_KEY=0x... bun demo/lookup_agent.ts --capability quote --min-score 0.9
```

The buyer deposits USDC into the Gateway Wallet once, then `client.pay()` handles the full
402 → sign → settle flow gaslessly. Settlement tx prints as a `https://testnet.arcscan.app/tx/<hash>` link.

## Code

- `contracts/mcp-registry/src/MCPRegistry.sol` — onchain MCP registry + capability scores
- `packages/marketplace-mcp-ts/src/server.ts` — Express seller with Circle Gateway middleware
- `packages/marketplace-mcp-ts/src/registry.ts` — viem reads of the registry + Walrus manifests
- `packages/marketplace-mcp-ts/demo/lookup_agent.ts` — gasless buyer agent
