#!/usr/bin/env bash
# Copy a filtered subset of repo-root .env to the eval-runner droplet.
# Never commits secrets; only keys on the allowlist are synced.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ROOT}/.env"
REMOTE_ENV="/etc/goldenmcp/.env"
SSH_USER="${SSH_USER:-root}"

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <droplet_ip> [ssh_user]" >&2
  echo "  droplet_ip from: terraform -chdir=infra/terraform/eval-runner output -raw droplet_ip" >&2
  exit 1
fi

DROPLET_IP="$1"
if [[ $# -ge 2 ]]; then
  SSH_USER="$2"
fi

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "ERROR: missing ${ENV_FILE}" >&2
  exit 1
fi

# Allowlist: application secrets only (no DO_API_KEY / Terraform tokens).
ALLOWLIST=(
  ANTHROPIC_API_KEY
  TOGETHER_API_KEY
  OPENAI_API_KEY
  EVAL_CHAIN_QUOTE
  EVAL_CHAIN_QUOTE_ID
  EVAL_CHAIN_ODOS_SWAP
  EVAL_CHAIN_ODOS_SWAP_ID
  WALLET_PRIVATE_KEY
  EVM_EVAL_ADDRESS
  LIFI_MCP_URL
  LIFI_API_KEY
  UNISWAP_MCP_URL
  ONEINCH_MCP_URL
  ONEINCH_API_KEY
  KYBERSWAP_MCP_PATH
  KYBERSWAP_RPC_URL
  SOLANA_RPC_URL
  JUPITER_API_KEY
  INFURA_KEY
  WALRUS_PUBLISHER_URL
  WALRUS_AGGREGATOR_URL
  WALRUS_EPOCHS
  WALRUS_INDEX_BLOB_ID
  ARC_RPC_URL
  ARC_REGISTRY_ADDRESS
  ARC_USDC_ADDRESS
  MARKETPLACE_WALLET_PRIVATE_KEY
  X402_FACILITATOR_URL
  X402_PAYEE_ADDRESS
  MARKETPLACE_URL
  ENS_RPC_URL
  ENS_PARENT_NAME
  CHAINLINK_CAI_API_KEY
  CHAINLINK_CAI_URL
  EVAL_RUNNER_HOST
  EVAL_RUNNER_PORT
  EVAL_RUNNER_API_KEY
  EVAL_RUNNER_PUBLIC_URL
)

TMP="$(mktemp)"
trap 'rm -f "${TMP}"' EXIT

{
  echo "# Synced from local .env on $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "EVAL_RUNNER_HOST=0.0.0.0"
  echo "EVAL_RUNNER_PORT=8090"
} > "${TMP}"

# shellcheck disable=SC1090
set -a
source "${ENV_FILE}"
set +a

for key in "${ALLOWLIST[@]}"; do
  if [[ "${key}" == "EVAL_RUNNER_HOST" || "${key}" == "EVAL_RUNNER_PORT" ]]; then
    continue
  fi
  val="${!key-}"
  if [[ -n "${val}" ]]; then
    printf '%s=%q\n' "${key}" "${val}" >> "${TMP}"
  fi
done

if [[ -z "${EVAL_RUNNER_API_KEY:-}" ]]; then
  NEW_KEY="$(openssl rand -hex 32)"
  echo "EVAL_RUNNER_API_KEY=${NEW_KEY}" >> "${TMP}"
  echo "Generated EVAL_RUNNER_API_KEY — add to local .env for CRE bearer auth (GH #23):"
  echo "  EVAL_RUNNER_API_KEY=${NEW_KEY}"
fi

if [[ -z "${EVAL_RUNNER_PUBLIC_URL:-}" ]]; then
  echo "EVAL_RUNNER_PUBLIC_URL=https://${DROPLET_IP}" >> "${TMP}"
fi

echo "Uploading secrets to ${SSH_USER}@${DROPLET_IP}:${REMOTE_ENV} ..."
scp -o StrictHostKeyChecking=accept-new "${TMP}" "${SSH_USER}@${DROPLET_IP}:/tmp/goldenmcp.env"
ssh "${SSH_USER}@${DROPLET_IP}" bash -s <<EOF
set -euo pipefail
install -d -m 700 -o goldenmcp -g goldenmcp /etc/goldenmcp
install -m 600 -o goldenmcp -g goldenmcp /tmp/goldenmcp.env ${REMOTE_ENV}
rm -f /tmp/goldenmcp.env
systemctl restart goldenmcp-eval-runner.service
systemctl is-active goldenmcp-eval-runner.service
EOF

echo "Done. Health check:"
echo "  curl -k https://${DROPLET_IP}/health"
