#!/usr/bin/env bash
# Verify Walrus testnet eval storage: load .env, ping aggregator, run live upload tests.
#
# Usage:
#   ./scripts/verify_walrus.sh

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ROOT}/.env"

log() { printf '[verify_walrus] %s\n' "$*"; }
err() { printf '[verify_walrus] ERROR: %s\n' "$*" >&2; }

if [[ ! -f "$ENV_FILE" ]]; then
  err "Missing ${ENV_FILE}. Run ./scripts/setup_eval_env.sh first."
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

for key in WALRUS_PUBLISHER_URL WALRUS_AGGREGATOR_URL WALRUS_EPOCHS; do
  if [[ -z "${!key:-}" ]]; then
    err "${key} is not set in ${ENV_FILE}"
    exit 1
  fi
done

log "Publisher:  ${WALRUS_PUBLISHER_URL}"
log "Aggregator: ${WALRUS_AGGREGATOR_URL}"
log "Epochs:     ${WALRUS_EPOCHS}"

log "Checking aggregator OpenAPI at ${WALRUS_AGGREGATOR_URL}/v1/api"
curl -fsS "${WALRUS_AGGREGATOR_URL}/v1/api" >/dev/null

log "Running Walrus client integration tests"
cd "$ROOT"
uv run pytest packages/walrus-client/tests/test_walrus_client.py -v

log "Running post-eval Walrus pipeline integration test"
uv run pytest packages/inspect-web3/tests/test_pipeline.py::test_post_eval_walrus_upload_integration -v

log "Walrus eval storage verified"
