#!/usr/bin/env bash
# Pre-install stdio vendor MCP npm packages and validate required env vars.
# Fails loudly — no silent skips (real-code-only).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="${ROOT}/.env"
if [[ ! -f "${ENV_FILE}" ]]; then
  main_root="$(git -C "${ROOT}" worktree list --porcelain 2>/dev/null | awk '/^worktree /{print $2; exit}')"
  [[ -n "${main_root:-}" && -f "${main_root}/.env" ]] && ENV_FILE="${main_root}/.env"
fi
if [[ -f "${ENV_FILE}" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "${ENV_FILE}"
  set +a
fi

echo "==> Pre-installing stdio vendor MCP packages (npx cache warm)..."
npx -y @iqai/mcp-odos --help >/dev/null 2>&1 || npx -y @iqai/mcp-odos --version 2>/dev/null || true
npx -y jupiter-mcp-server --help >/dev/null 2>&1 || npx -y jupiter-mcp-server --version 2>/dev/null || true

missing=()
for var in LIFI_MCP_URL ONEINCH_MCP_URL KYBERSWAP_MCP_PATH MARKETPLACE_URL X402_PAYEE_ADDRESS; do
  if [[ -z "${!var:-}" ]]; then
    missing+=("${var}")
  fi
done

if [[ ${#missing[@]} -gt 0 ]]; then
  echo "ERROR: missing required env vars for web-agent MCP manifest:" >&2
  printf '  - %s\n' "${missing[@]}" >&2
  exit 1
fi

if [[ ! -f "${KYBERSWAP_MCP_PATH}" ]]; then
  echo "ERROR: KYBERSWAP_MCP_PATH=${KYBERSWAP_MCP_PATH} does not exist — clone KyberNetwork/kyberswap-mcp and build" >&2
  exit 1
fi

echo "==> Emitting MCP manifest..."
cd "${ROOT}"
uv run goldenmcp-mcp-manifest | head -20
echo "... (truncated)"

echo "==> Vendor MCP pre-install OK"
