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

echo "4. Services (require .env)"
echo "   uv run python -m goldenmcp_eval_runner"
echo "   uv run python -m goldenmcp_marketplace"
echo "   cd apps/web && bun run dev"

echo "5. x402 agent demo"
echo "   uv run python demo/lookup_agent.py --capability quote --min-score 0.9"

echo "=== Demo script complete ==="
