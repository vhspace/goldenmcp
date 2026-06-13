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
#   - Qwen3.5-9B, Mistral-Small -> Together (TOGETHER_API_KEY, native endpoint).
#     Qwen runs with thinking disabled via chat_template_kwargs in extra_body
#     (passed through GenerateConfig via --model-config, since extra_body is not a
#     -M provider arg).
# A leaked ANTHROPIC_BASE_URL from a Claude Code shell is stripped so it can't
# hijack the Together runs.
#
# Usage:
#   ./scripts/run_eval.sh <task> [extra inspect args...]
#   ./scripts/run_eval.sh lifi_quote
#   MODELS="haiku" ./scripts/run_eval.sh lifi_quote      # subset (space/comma sep)
#   EVAL_TIME_LIMIT=90 ./scripts/run_eval.sh lifi_quote  # per-sample wall cap (s)
#
# Requires .env with ANTHROPIC_BASE_URL, DO_INFERENCE_KEY, TOGETHER_API_KEY.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PKG="${ROOT}/packages/inspect-web3"
ENV_FILE="${ROOT}/.env"
TASK="${1:?usage: run_eval.sh <task> [inspect args...]}"
shift || true

# Per-sample wall-clock cap (seconds). A slow/hung model (e.g. a reasoning model
# rambling, or Together queue latency) is bounded and scored on its partial
# transcript rather than stalling the whole K=3 run. Healthy runs are ~15-35s;
# 120s leaves headroom. Override with EVAL_TIME_LIMIT.
EVAL_TIME_LIMIT="${EVAL_TIME_LIMIT:-120}"

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
      --max-connections 1 --time-limit "$EVAL_TIME_LIMIT" "$@"
}

run_together() {  # $1 = together slug; remaining args -> inspect
  local slug="$1"; shift
  "${CLEAN_ENV[@]}" TOGETHER_API_KEY="$TOGETHER_API_KEY" uv run "${WITH[@]}" \
    inspect eval "src/goldenmcp_inspect/tasks.py@${TASK}" \
      --model "together/$slug" \
      --max-connections 1 --time-limit "$EVAL_TIME_LIMIT" "$@"
}

# Together model with thinking disabled via GenerateConfig.extra_body
# (chat_template_kwargs.enable_thinking=false). extra_body can't be set on Inspect's
# CLI and is rejected (HTTP 400) by the Anthropic endpoint, so the task applies it
# only when GOLDENMCP_DISABLE_THINKING=1. Used for Qwen3.5 and gemma-4 (both reason
# by default).
run_together_nothink() {  # $1 = slug; rest -> inspect
  local slug="$1"; shift
  GOLDENMCP_DISABLE_THINKING=1 run_together "$slug" "$@"
}

SELECTED="${MODELS:-haiku qwen gemma}"
SELECTED="${SELECTED//,/ }"

# Run each model as its own background `inspect eval` invocation and wait for all.
# The three calls hit different providers/connections (Haiku -> DO proxy, qwen+gemma
# -> Together) and Inspect writes a uniquely timestamped+hashed .eval per run, so
# concurrent invocations don't collide. Concurrent Together invocations were verified
# not to 401/429 on the free tier. Per-model stdout is captured to a temp file and
# replayed in order after the run so logs aren't interleaved. Any model failure makes
# the whole script exit non-zero.
TMPDIR_RUN="$(mktemp -d)"
trap 'rm -rf "$TMPDIR_RUN"' EXIT

declare -a PIDS=() NAMES=() LOGS=()

launch() {  # $1 = label; $2 = fn; rest -> inspect args
  local label="$1" fn="$2"; shift 2
  local out="${TMPDIR_RUN}/${label}.out"
  echo ">>> $TASK @ $label"
  { "$fn" "$@"; } >"$out" 2>&1 &
  PIDS+=("$!"); NAMES+=("$label"); LOGS+=("$out")
}

for m in $SELECTED; do
  case "$m" in
    haiku)  launch "haiku (DO proxy)" run_haiku "$@" ;;
    qwen)   launch "qwen3.5-9b (Together, no-think)" run_together_nothink "Qwen/Qwen3.5-9B" "$@" ;;
    gemma)  launch "gemma-4-31b-it (Together, no-think)" run_together_nothink "google/gemma-4-31B-it" "$@" ;;
    *) echo "unknown model: $m (use haiku|qwen|gemma)" >&2; exit 1 ;;
  esac
done

FAILED=0
for i in "${!PIDS[@]}"; do
  if wait "${PIDS[$i]}"; then rc=0; else rc=$?; fi
  echo "===== ${NAMES[$i]} (exit $rc) ====="
  cat "${LOGS[$i]}"
  [[ $rc -eq 0 ]] || FAILED=1
done

exit "$FAILED"
