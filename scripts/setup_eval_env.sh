#!/usr/bin/env bash
# Bootstrap .env for live MCP evals on a fresh demo machine.
#
# Usage:
#   ./scripts/setup_eval_env.sh           # create/update .env (generates wallet if missing)
#   ./scripts/setup_eval_env.sh --check   # verify prerequisites only
#   ./scripts/setup_eval_env.sh --verify-walrus  # live Walrus testnet upload/read
#
# Chain strategy (see packages/inspect-web3/src/goldenmcp_inspect/eval_chains.py):
#   - Quote evals: Base mainnet (8453) for LI.FI, Odos, Uniswap
#   - odos_swap:   Fraxtal (252) — Odos MCP default execution chain
#   - ENS identity stays on Sepolia (separate from swap evals)
#
# After running, fund the printed address:
#   - Base (8453):     https://docs.base.org/base-chain/tools/network-faucets
#   - Fraxtal (252):   https://docs.frax.com/fraxtal/welcome/faucet (for odos_swap)
#
# Walrus eval storage (testnet HTTP publisher — no Sui wallet required):
#   - Publisher: https://publisher.walrus-testnet.walrus.space
#   - Aggregator: https://aggregator.walrus-testnet.walrus.space
#   - Docs: https://docs.wal.app/docs/http-api/storing-blobs

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ROOT}/.env"
EXAMPLE="${ROOT}/.env.example"
CHECK_ONLY=false
VERIFY_WALRUS=false

for arg in "$@"; do
  case "$arg" in
    --check) CHECK_ONLY=true ;;
    --verify-walrus) VERIFY_WALRUS=true ;;
  esac
done

log() { printf '[setup_eval_env] %s\n' "$*"; }
err() { printf '[setup_eval_env] ERROR: %s\n' "$*" >&2; }

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    err "Missing required command: $1"
    exit 1
  fi
}

check_prerequisites() {
  require_cmd uv
  require_cmd node
  require_cmd npx
  require_cmd cast
  if $VERIFY_WALRUS; then
    require_cmd curl
  fi
  log "Prerequisites OK: uv, node, npx, cast"
}

env_get() {
  local key="$1"
  if [[ ! -f "$ENV_FILE" ]]; then
    return 1
  fi
  grep -E "^${key}=" "$ENV_FILE" 2>/dev/null | head -1 | cut -d= -f2- || true
}

env_set() {
  local key="$1"
  local value="$2"
  if [[ ! -f "$ENV_FILE" ]]; then
    touch "$ENV_FILE"
  fi
  if grep -qE "^${key}=" "$ENV_FILE"; then
    if [[ "$(uname)" == "Darwin" ]]; then
      sed -i '' "s|^${key}=.*|${key}=${value}|" "$ENV_FILE"
    else
      sed -i "s|^${key}=.*|${key}=${value}|" "$ENV_FILE"
    fi
  else
    printf '%s=%s\n' "$key" "$value" >>"$ENV_FILE"
  fi
}

ensure_env_file() {
  if [[ ! -f "$ENV_FILE" ]]; then
    log "Creating ${ENV_FILE} from .env.example"
    cp "$EXAMPLE" "$ENV_FILE"
  fi
}

remove_stale_env_keys() {
  local stale=(ZEROX_MCP_URL ZEROX_API_KEY ZERO_EX_API_KEY ONEINCH_API_KEY Y0_API_KEY)
  for key in "${stale[@]}"; do
    if grep -qE "^${key}=" "$ENV_FILE" 2>/dev/null; then
      if [[ "$(uname)" == "Darwin" ]]; then
        sed -i '' "/^${key}=/d" "$ENV_FILE"
      else
        sed -i "/^${key}=/d" "$ENV_FILE"
      fi
      log "Removed stale ${key} (0x/y0 eval path replaced by Odos stdio)"
    fi
  done
}

ensure_default_urls() {
  if [[ -z "$(env_get LIFI_MCP_URL)" ]]; then
    env_set LIFI_MCP_URL "https://mcp.li.quest/mcp"
  fi
  if [[ -z "$(env_get LIFI_API_KEY)" ]]; then
    env_set LIFI_API_KEY "test-api-key"
    log "Set LIFI_API_KEY=test-api-key (public dev key; replace with li.fi key for higher limits)"
  fi
  if [[ -z "$(env_get UNISWAP_MCP_URL)" ]]; then
    env_set UNISWAP_MCP_URL "https://uniswap.mcp.junct.dev/mcp"
  fi
  if [[ -z "$(env_get EVAL_CHAIN_QUOTE)" ]]; then
    env_set EVAL_CHAIN_QUOTE "base"
  fi
  if [[ -z "$(env_get EVAL_CHAIN_QUOTE_ID)" ]]; then
    env_set EVAL_CHAIN_QUOTE_ID "8453"
  fi
  if [[ -z "$(env_get EVAL_CHAIN_ODOS_SWAP)" ]]; then
    env_set EVAL_CHAIN_ODOS_SWAP "fraxtal"
  fi
  if [[ -z "$(env_get EVAL_CHAIN_ODOS_SWAP_ID)" ]]; then
    env_set EVAL_CHAIN_ODOS_SWAP_ID "252"
  fi
}

ensure_walrus_defaults() {
  local publisher="https://publisher.walrus-testnet.walrus.space"
  local aggregator="https://aggregator.walrus-testnet.walrus.space"

  if [[ -z "$(env_get WALRUS_PUBLISHER_URL)" ]]; then
    env_set WALRUS_PUBLISHER_URL "$publisher"
    log "Set WALRUS_PUBLISHER_URL=${publisher}"
  fi
  if [[ -z "$(env_get WALRUS_AGGREGATOR_URL)" ]]; then
    env_set WALRUS_AGGREGATOR_URL "$aggregator"
    log "Set WALRUS_AGGREGATOR_URL=${aggregator}"
  fi
  if [[ -z "$(env_get WALRUS_EPOCHS)" ]]; then
    env_set WALRUS_EPOCHS "1"
    log "Set WALRUS_EPOCHS=1 (testnet epoch = 1 day; increase for longer retention)"
  fi
  if [[ -z "$(env_get NEXT_PUBLIC_WALRUS_AGGREGATOR_URL)" ]]; then
    env_set NEXT_PUBLIC_WALRUS_AGGREGATOR_URL "$aggregator"
    log "Set NEXT_PUBLIC_WALRUS_AGGREGATOR_URL=${aggregator}"
  fi
}

verify_walrus_reachable() {
  local aggregator
  aggregator="$(env_get WALRUS_AGGREGATOR_URL)"
  if [[ -z "$aggregator" ]]; then
    err "WALRUS_AGGREGATOR_URL is not set"
    exit 1
  fi

  log "Checking Walrus aggregator API at ${aggregator}/v1/api"
  if ! curl -fsS "${aggregator}/v1/api" >/dev/null; then
    err "Walrus aggregator unreachable: ${aggregator}/v1/api"
    exit 1
  fi
  log "Walrus aggregator reachable"
}

generate_eval_wallet() {
  local existing
  existing="$(env_get WALLET_PRIVATE_KEY)"
  if [[ -n "$existing" ]]; then
    log "WALLET_PRIVATE_KEY already set — skipping wallet generation"
    if [[ -z "$(env_get EVM_EVAL_ADDRESS)" ]]; then
      local addr
      addr="$(cast wallet address --private-key "$existing")"
      env_set EVM_EVAL_ADDRESS "$addr"
      log "Derived EVM_EVAL_ADDRESS=${addr}"
    fi
    return 0
  fi

  log "Generating dedicated eval wallet with cast (never commit this key)"
  local wallet_out address private_key
  wallet_out="$(cast wallet new)"
  address="$(printf '%s\n' "$wallet_out" | awk '/^Address:/ { print $2 }')"
  private_key="$(printf '%s\n' "$wallet_out" | awk '/^Private key:/ { print $3 }')"

  if [[ -z "$address" || -z "$private_key" ]]; then
    err "Failed to parse cast wallet new output"
    printf '%s\n' "$wallet_out" >&2
    exit 1
  fi

  env_set WALLET_PRIVATE_KEY "$private_key"
  env_set EVM_EVAL_ADDRESS "$address"

  log "Created eval wallet address: ${address}"
  log "Fund this address before swap evals:"
  log "  Base (8453)   — LI.FI / Odos quote / Uniswap: https://docs.base.org/base-chain/tools/network-faucets"
  log "  Fraxtal (252) — odos_swap only: https://docs.frax.com/fraxtal/welcome/faucet"
}

sync_python_deps() {
  log "Syncing Python packages (includes inspect-ai + mcp)"
  (cd "$ROOT" && uv sync --all-packages)
}

print_next_steps() {
  local addr llm
  addr="$(env_get EVM_EVAL_ADDRESS)"
  llm="unset"
  if [[ -n "$(env_get ANTHROPIC_API_KEY)" ]]; then
    llm="anthropic"
  elif [[ -n "$(env_get TOGETHER_API_KEY)" ]]; then
    llm="together"
  elif [[ -n "$(env_get OPENAI_API_KEY)" ]]; then
    llm="openai"
  fi

  cat <<EOF

--- Eval environment ready ---

Wallet:  ${addr:-<set WALLET_PRIVATE_KEY>}
LLM key: ${llm} (set ANTHROPIC_API_KEY, TOGETHER_API_KEY, or OPENAI_API_KEY if unset)

Run unit tests:
  cd ${ROOT} && uv run pytest packages/inspect-web3/tests/ -q

Run first live eval (after LLM key set):
  uv run inspect eval goldenmcp/lifi_quote --model anthropic/claude-3-5-haiku-20241022

Walrus eval storage (testnet, no Sui wallet):
  ./scripts/verify_walrus.sh

Chain defaults: Base (8453) quotes; Fraxtal (252) for odos_swap only.
EOF
}

main() {
  check_prerequisites
  if $CHECK_ONLY; then
    log "--check passed"
    exit 0
  fi

  ensure_env_file
  remove_stale_env_keys
  ensure_default_urls
  ensure_walrus_defaults
  generate_eval_wallet
  sync_python_deps

  if $VERIFY_WALRUS; then
    verify_walrus_reachable
    log "Running live Walrus upload/download tests"
    (cd "$ROOT" && ./scripts/verify_walrus.sh)
  fi

  print_next_steps
}

main "$@"
