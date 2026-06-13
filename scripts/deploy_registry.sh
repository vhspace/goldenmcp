scripts/deploy_registry.sh
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [ -z "${ARC_RPC_URL:-}" ]; then
  echo "ARC_RPC_URL required" >&2
  exit 1
fi
forge script contracts/mcp-registry/script/Deploy.s.sol \
  --rpc-url "$ARC_RPC_URL" \
  --broadcast \
  -C contracts/mcp-registry
