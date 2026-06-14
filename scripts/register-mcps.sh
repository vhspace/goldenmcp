#!/usr/bin/env bash
# Register the GoldenMCP MCP servers in the Arc MCPRegistry so each has its own
# agent id. Idempotent: skips any MCP whose name already resolves (nameToAgentId).
# The eval-runner resolves a benchmark's MCP name -> agent id at run time, so a
# newly registered MCP is picked up automatically (see docs/registering-mcps.md).
#
# Requires repo-root .env: MARKETPLACE_WALLET_PRIVATE_KEY, ARC_RPC_URL,
# ARC_REGISTRY_ADDRESS. Arc gas is USDC.
#
# Usage: ./scripts/register-mcps.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ROOT}/.env"
# In a git worktree the gitignored .env lives in the main checkout; fall back to it.
if [[ ! -f "${ENV_FILE}" ]]; then
  main_root="$(git -C "${ROOT}" worktree list --porcelain 2>/dev/null | awk '/^worktree /{print $2; exit}')"
  [[ -n "${main_root:-}" && -f "${main_root}/.env" ]] && ENV_FILE="${main_root}/.env"
fi
[[ -f "${ENV_FILE}" ]] || { echo "ERROR: missing .env (looked at ${ROOT}/.env and main worktree)" >&2; exit 1; }
# shellcheck disable=SC1090
set -a; source "${ENV_FILE}"; set +a
: "${MARKETPLACE_WALLET_PRIVATE_KEY:?required}" "${ARC_RPC_URL:?required}" "${ARC_REGISTRY_ADDRESS:?required}"

REG="${ARC_REGISTRY_ADDRESS}"
PK="${MARKETPLACE_WALLET_PRIVATE_KEY}"
RPC="${ARC_RPC_URL}"

# name | mcpEndpoint | agentUri | ensName  (endpoint/uri are descriptive metadata).
MCPS=(
  "lifi|https://mcp.li.fi/mcp|walrus://goldenmcp/lifi|lifi.goldenmcp.eth"
  "1inch|https://api.1inch.com/mcp/protocol|walrus://goldenmcp/1inch|1inch.goldenmcp.eth"
  "odos|stdio:npx -y @iqai/mcp-odos|walrus://goldenmcp/odos|odos.goldenmcp.eth"
  "jupiter|stdio:npx -y jupiter-mcp-server|walrus://goldenmcp/jupiter|jupiter.goldenmcp.eth"
  "kyberswap|github:KyberNetwork/kyberswap-mcp|walrus://goldenmcp/kyberswap|kyberswap.goldenmcp.eth"
)

for entry in "${MCPS[@]}"; do
  IFS='|' read -r name endpoint uri ens <<<"${entry}"
  existing="$(cast call "${REG}" "nameToAgentId(string)(uint256)" "${name}" --rpc-url "${RPC}" 2>/dev/null | head -1 || echo 0)"
  existing="${existing%% *}"
  if [[ "${existing}" != "0" && -n "${existing}" ]]; then
    echo "skip ${name} — already agent ${existing}"
    continue
  fi
  echo "register ${name} ..."
  cast send "${REG}" "register(string,string,string,string)" "${name}" "${endpoint}" "${uri}" "${ens}" \
    --private-key "${PK}" --rpc-url "${RPC}" >/dev/null
  id="$(cast call "${REG}" "nameToAgentId(string)(uint256)" "${name}" --rpc-url "${RPC}" 2>/dev/null | head -1)"
  echo "  ${name} -> agent ${id%% *}"
done

echo
echo "Registered agents:"
for entry in "${MCPS[@]}"; do
  name="${entry%%|*}"
  id="$(cast call "${REG}" "nameToAgentId(string)(uint256)" "${name}" --rpc-url "${RPC}" 2>/dev/null | head -1)"
  printf '  %-12s agent %s\n' "${name}" "${id%% *}"
done
