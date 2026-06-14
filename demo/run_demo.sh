#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

echo "=== GoldenMCP Demo ==="

echo "1. Unit tests"
uv run pytest packages/inspect-web3/tests packages/walrus-client/tests -v

echo "2. Contract tests"
forge test -C contracts/mcp-registry

echo "3. Web tests"
cd apps/web && bun test && cd ../..

echo "4. Marketplace (TS) tests"
cd packages/marketplace-mcp-ts && bun install && bun test tests/ && cd ../..

echo "5. Services (require .env)"
echo "   uv run python -m goldenmcp_eval_runner"
echo "   (cd packages/marketplace-mcp-ts && bun src/server.ts)"
echo "   cd apps/web && bun run dev"

echo "6. x402 nanopayments agent demo (gasless USDC on Arc)"
echo "   cd packages/marketplace-mcp-ts && DEMO_PAYER_PRIVATE_KEY=0x... bun demo/lookup_agent.ts --capability quote --min-score 0.9"

echo "=== Demo script complete ==="
