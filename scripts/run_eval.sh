#!/usr/bin/env bash
# Run a live MCP eval task across the K=3 model ensemble with correct provider
# routing. Each model runs as its own `inspect eval` invocation because provider
# config (base URL, api key) is global per invocation — you cannot point Haiku at
# the DO proxy while leaving the Together models on their own endpoint in a single
# multi-model run.
#
# Routing handled here so callers (and the CRE pipeline) don't repeat it:
#   - Haiku  -> DigitalOcean inference proxy (ANTHROPIC_BASE_URL + DO_INFERENCE_KEY),
#              passed explicitly via --model-base-url / -M api_key because Inspect's
#              env-var auth handling conflicts with the proxy.
#   - Llama, MiniMax -> Together (TOGETHER_API_KEY, native endpoint).
# A leaked ANTHROPIC_BASE_URL from a Claude Code shell is stripped so it can't
# hijack the Together runs.
#
# Usage:
#   ./scripts/run_eval.sh <task> [extra inspect args...]
#   ./scripts/run_eval.sh lifi_quote
#   MODELS="haiku" ./scripts/run_eval.sh lifi_quote      # subset (space/comma sep)
#
# Requires .env with ANTHROPIC_BASE_URL, DO_INFERENCE_KEY, TOGETHER_API_KEY.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PKG="${ROOT}/packages/inspect-web3"
ENV_FILE="${ROOT}/.env"
TASK="${1:?usage: run_eval.sh <task> [inspect args...]}"
shift || true

[[ -f "$ENV_FILE" ]] || { echo "missing $ENV_FILE (run setup_eval_env.sh)" >&2; exit 1; }
set -a; . "$ENV_FILE"; set +a

: "${DO_INFERENCE_KEY:?DO_INFERENCE_KEY required for Haiku via DO proxy}"
: "${ANTHROPIC_BASE_URL:?ANTHROPIC_BASE_URL required (DO proxy)}"
: "${TOGETHER_API_KEY:?TOGETHER_API_KEY required for Llama/MiniMax}"

cd "$PKG"

WITH=(--with anthropic --with together --with openai)
# Strip leaked Anthropic proxy vars so they can't hijack the Together runs.
CLEAN_ENV=(env -u ANTHROPIC_API_KEY -u ANTHROPIC_BASE_URL
           -u ANTHROPIC_MODEL -u ANTHROPIC_DEFAULT_OPUS_MODEL
           -u ANTHROPIC_DEFAULT_SONNET_MODEL -u ANTHROPIC_DEFAULT_HAIKU_MODEL)

run_haiku() {
  "${CLEAN_ENV[@]}" uv run "${WITH[@]}" \
    inspect eval "src/goldenmcp_inspect/tasks.py@${TASK}" \
      --model anthropic/anthropic-claude-haiku-4.5 \
      --model-base-url "$ANTHROPIC_BASE_URL" \
      -M "api_key=${DO_INFERENCE_KEY}" \
      --max-connections 1 "$@"
}

run_together() {  # $1 = together slug
  "${CLEAN_ENV[@]}" TOGETHER_API_KEY="$TOGETHER_API_KEY" uv run "${WITH[@]}" \
    inspect eval "src/goldenmcp_inspect/tasks.py@${TASK}" \
      --model "together/$1" \
      --max-connections 1 "$@"
}

SELECTED="${MODELS:-haiku llama minimax}"
SELECTED="${SELECTED//,/ }"
for m in $SELECTED; do
  case "$m" in
    haiku)   echo ">>> $TASK @ haiku (DO proxy)";  run_haiku "$@" ;;
    llama)   echo ">>> $TASK @ llama (Together)";  run_together "meta-llama/Llama-3.3-70B-Instruct-Turbo" "$@" ;;
    minimax) echo ">>> $TASK @ minimax (Together)"; run_together "MiniMaxAI/MiniMax-M2.7" "$@" ;;
    *) echo "unknown model: $m (use haiku|llama|minimax)" >&2; exit 1 ;;
  esac
done
