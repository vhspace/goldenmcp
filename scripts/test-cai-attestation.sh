#!/usr/bin/env bash
#
# test-cai-attestation.sh — end-to-end test/demo of the GoldenMCP async CAI
# attestation flow (GH #54).
#
# Drives ONE full attestation run and prints every link/value a human needs to
# verify the result on-chain (Arc testnet) and on Walrus.
#
# The flow mirrors the proven-live manual runs:
#   1. (Re)start the long-lived CRE HTTP-trigger (handler B) on the droplet.
#      The trigger serves exactly ONE execution then exits, so it must be
#      restarted before every run.
#   2. Ensure agent 1 (lifi) exists in the MCPRegistry.
#   3. POST /eval/score on the droplet  -> run_id
#   4. Submit a REAL CAI inference (/v1/inference) with cre_callback pointing
#      at the droplet trigger -> inference_id
#   5. POST /eval/cai-submitted to register inference_id -> run_id.
#   6. Poll GET /v1/inference/{id} until completed (CAI fires the callback;
#      handler B then runs: writes the attestation to Arc + publishes Walrus).
#   7. Poll GET /eval/runs/{run_id} until published -> walrus_manifest_blob_id.
#   8. cast call getRecord(1) -> lastAttestationId + lastTranscriptHash.
#
# The eval-runner HTTP calls and the CAI submit are executed ON THE DROPLET via
# ssh (sourcing the droplet's /etc/goldenmcp/.env), exactly like the manual
# runs — this keeps the eval-runner Authorization header and the CAI callback
# host all on the droplet, and sidesteps nested-quote issues by pushing each
# step as a heredoc script.
#
# WARNING: this consumes a REAL CAI inference (costs a real TEE run).
#
# Usage: ./scripts/test-cai-attestation.sh
# Requires (local): cast (foundry), curl, python3, ssh. No secrets are printed.

set -euo pipefail

# --- Static infra constants (per GH #54 deployment) --------------------------
DROPLET_IP="165.227.74.149"
DROPLET_SSH="root@${DROPLET_IP}"
TRIGGER_URL="http://${DROPLET_IP}:2000/trigger"
EVAL_RUNNER_BASE="http://${DROPLET_IP}"          # nginx :80 -> uvicorn :8090
FORWARDER_ADDRESS="0x6E9EE680ef59ef64Aa8C7371279c27E496b5eDc1"
ARCSCAN_BASE="https://testnet.arcscan.app"
DROPLET_ENV="/etc/goldenmcp/.env"
TRIGGER_LOG="/tmp/cre-trigger.log"

# CAI dev-preview endpoint (CHAINLINK_CAI_URL in .env is intentionally blank).
CAI_URL_DEFAULT="https://confidential-ai-dev-preview.cldev.cloud"

# --- Resolve repo root + load secrets ---------------------------------------
# scripts/ lives under the repo root and .env sits at that root. Prefer the
# directory above this script; if .env is absent (e.g. running from a git
# worktree whose .env lives in the main checkout), fall back to the main
# worktree resolved via the shared git common dir.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${REPO_ROOT}/.env"

if [[ ! -f "${ENV_FILE}" ]]; then
  if common_dir="$(git -C "${SCRIPT_DIR}" rev-parse --git-common-dir 2>/dev/null)"; then
    # git-common-dir is <main-worktree>/.git; its parent is the main checkout.
    main_root="$(cd "$(dirname "${common_dir}")" && pwd)"
    if [[ -f "${main_root}/.env" ]]; then
      REPO_ROOT="${main_root}"
      ENV_FILE="${main_root}/.env"
    fi
  fi
fi

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "FATAL: repo-root .env not found (looked in ${SCRIPT_DIR}/.. and the git main worktree)" >&2
  exit 1
fi

# Export everything in .env; never echo any of these values.
set -a
# shellcheck disable=SC1090
source "${ENV_FILE}"
set +a

ARC_RPC_URL="${ARC_RPC_URL:?ARC_RPC_URL missing from .env}"
ARC_REGISTRY_ADDRESS="${ARC_REGISTRY_ADDRESS:?ARC_REGISTRY_ADDRESS missing from .env}"
: "${MARKETPLACE_WALLET_PRIVATE_KEY:?MARKETPLACE_WALLET_PRIVATE_KEY missing from .env}"
: "${CHAINLINK_CAI_API_KEY:?CHAINLINK_CAI_API_KEY missing from .env}"
WALRUS_AGGREGATOR_URL="${WALRUS_AGGREGATOR_URL:-https://aggregator.walrus-testnet.walrus.space}"
CAI_URL="${CHAINLINK_CAI_URL:-${CAI_URL_DEFAULT}}"
CAI_URL="${CAI_URL%/}"  # strip any trailing slash

AGENT_ID=1
CAPABILITY="quote"
MCP_NAME="lifi"

# Derive the deployer/payee address (no key material printed).
PAYEE_ADDRESS="$(cast wallet address --private-key "${MARKETPLACE_WALLET_PRIVATE_KEY}")"

log()  { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
note() { printf '    %s\n' "$*"; }

# Robustly decode the MCPRegistry.getRecord(uint256) tuple. cast 0.3.0 mangles
# the nested dynamic tuple when given the typed signature, so we fetch the raw
# ABI return data and decode it in python. Echoes three lines:
#   <lastAttestationId>\n<lastTranscriptHash 0x...>\n<exists true|false>
decode_get_record() {
  local agent_id="$1"
  local raw
  raw="$(cast call "${ARC_REGISTRY_ADDRESS}" 'getRecord(uint256)' "${agent_id}" \
    --rpc-url "${ARC_RPC_URL}")"
  RAW="${raw}" python3 - <<'PY'
import os
h = os.environ["RAW"]
h = h[2:] if h[:2] == "0x" else h
b = bytes.fromhex(h)
def word(i): return b[i*32:(i+1)*32]
def u(i): return int.from_bytes(word(i), "big")
base = u(0) // 32  # outer tuple offset
def readstr(slot):
    off = u(base + slot) // 32
    a = base + off
    n = u(a)
    return b[(a + 1) * 32:(a + 1) * 32 + n].decode("utf-8", "replace")
# tuple: name, mcpEndpoint, agentUri, ensName, lastAttestationId,
#        lastTranscriptHash, exists
last_attestation_id = readstr(4)
last_transcript_hash = "0x" + word(base + 5).hex()
exists = "true" if u(base + 6) else "false"
print(last_attestation_id)
print(last_transcript_hash)
print(exists)
PY
}

# Run a heredoc script on the droplet with /etc/goldenmcp/.env sourced. The
# script body is piped over stdin so we never wrestle with nested ssh quoting.
# Usage: droplet_run <<'EOSH' ... EOSH
droplet_run() {
  # Forward caller vars across ssh as `NAME=value` args (env prefixes do NOT
  # cross ssh). The remote shell sources the droplet env (secrets), pins
  # EVAL_RUNNER_BASE to localhost (the eval-runner is local to the droplet),
  # exports the forwarded vars, then runs the heredoc piped on stdin.
  local assigns="EVAL_RUNNER_BASE=http://localhost"
  local kv
  for kv in "$@"; do assigns+=" $(printf '%q' "${kv}")"; done
  ssh -o BatchMode=yes -o ConnectTimeout=15 "${DROPLET_SSH}" \
    "set -euo pipefail; set -a; source ${DROPLET_ENV}; export ${assigns}; set +a; bash -s"
}

# ============================================================================
# Step 1 — ensure the CRE HTTP-trigger is listening on :2000 (handler B).
# ============================================================================
log "Step 1/8 — ensure CRE HTTP-trigger is up on ${DROPLET_IP}:2000"

trigger_listening() {
  ssh -o BatchMode=yes -o ConnectTimeout=15 "${DROPLET_SSH}" \
    "ss -ltn 2>/dev/null | grep -q ':2000'" 2>/dev/null
}

if trigger_listening; then
  note "trigger already listening — restarting it (serves only ONE run)."
else
  note "trigger not listening — starting it."
fi

# Always (re)start: the trigger exits after serving a single execution.
ssh -o BatchMode=yes -o ConnectTimeout=20 "${DROPLET_SSH}" \
  "sudo -u goldenmcp tmux kill-session -t cre-trigger 2>/dev/null || true; \
   sudo -u goldenmcp tmux new-session -d -s cre-trigger \
     'bash /opt/goldenmcp/run-trigger.sh 2>&1 | tee ${TRIGGER_LOG}'"

note "waiting up to 60s for :2000 to come up..."
trigger_up=0
for _ in $(seq 1 12); do
  sleep 5
  if trigger_listening; then trigger_up=1; break; fi
done
if [[ "${trigger_up}" -ne 1 ]]; then
  echo "FATAL: CRE trigger did not start listening on :2000 within 60s" >&2
  echo "       check: ssh ${DROPLET_SSH} 'cat ${TRIGGER_LOG}'" >&2
  exit 1
fi
note "trigger is listening on ${DROPLET_IP}:2000"

# ============================================================================
# Step 2 — ensure agent 1 (lifi) is registered.
# ============================================================================
log "Step 2/8 — ensure agent ${AGENT_ID} (${MCP_NAME}) exists in the registry"

agent_exists=0
if record_raw="$(decode_get_record "${AGENT_ID}" 2>/dev/null)"; then
  # Line 3 of the decoder output is the exists bool.
  if [[ "$(printf '%s\n' "${record_raw}" | sed -n '3p')" == "true" ]]; then
    agent_exists=1
  fi
fi

if [[ "${agent_exists}" -eq 1 ]]; then
  note "agent ${AGENT_ID} already registered."
else
  note "agent ${AGENT_ID} missing — registering ${MCP_NAME}..."
  cast send "${ARC_REGISTRY_ADDRESS}" \
    'register(string,string,string,string)' \
    "${MCP_NAME}" "https://mcp.li.fi/mcp" "walrus://manifest-proof" "lifi-quote.goldenmcp.eth" \
    --private-key "${MARKETPLACE_WALLET_PRIVATE_KEY}" \
    --rpc-url "${ARC_RPC_URL}" >/dev/null
  note "registered agent ${AGENT_ID} (${MCP_NAME})."
fi

# ============================================================================
# Step 3 — POST /eval/score on the droplet -> run_id.
# ============================================================================
log "Step 3/8 — POST /eval/score (${MCP_NAME}/${CAPABILITY}) on the droplet"

RUN_ID="$(droplet_run "MCP_NAME=${MCP_NAME}" "CAPABILITY=${CAPABILITY}" <<'EOSH'
score_resp="$(curl -fsS -X POST "${EVAL_RUNNER_BASE}/eval/score" \
  -H "Authorization: Bearer ${EVAL_RUNNER_API_KEY}" \
  -H "Content-Type: application/json" \
  -d "{\"mcp\":\"${MCP_NAME}\",\"capability\":\"${CAPABILITY}\",\"transcript\":{\"events\":[{\"kind\":\"tool\",\"tool_name\":\"get-quote\",\"content\":\"{\\\"amount\\\":1}\"}],\"final_output\":{\"amount\":1,\"token\":\"USDC\"},\"total_tokens\":2000}}")"
python3 -c "import sys,json; print(json.load(sys.stdin)['run_id'])" <<<"${score_resp}"
EOSH
)"
RUN_ID="$(printf '%s' "${RUN_ID}" | tr -d '[:space:]')"
[[ -n "${RUN_ID}" ]] || { echo "FATAL: /eval/score returned no run_id" >&2; exit 1; }
note "run_id=${RUN_ID}"

# ============================================================================
# Step 4 — submit a REAL CAI inference with the droplet callback -> inference_id.
# The manifest.json resource is fetched from the freshly-scored run so CAI
# reviews the actual score we just produced.
# ============================================================================
log "Step 4/8 — submit CAI inference (callback -> ${TRIGGER_URL})"

INFERENCE_ID="$(droplet_run "TRIGGER_URL=${TRIGGER_URL}" "RUN_ID=${RUN_ID}" <<'EOSH'
CAI_URL="${CHAINLINK_CAI_URL:-https://confidential-ai-dev-preview.cldev.cloud}"
CAI_API_KEY="${CHAINLINK_CAI_API_KEY}"
# Pull the scored manifest for this run from the eval-runner.
run_json="$(curl -fsS "${EVAL_RUNNER_BASE}/eval/runs/${RUN_ID}" \
  -H "Authorization: Bearer ${EVAL_RUNNER_API_KEY}")"

# Build the CAI submit body in python: a short PASS/FAIL review prompt, the
# manifest as a base64 manifest.json resource, and the cre_callback URL.
submit_body="$(RUN_JSON="${run_json}" TRIGGER_URL="${TRIGGER_URL}" python3 - <<'PY'
import base64, json, os
run = json.loads(os.environ["RUN_JSON"])
manifest = run.get("manifest") or {}
b64 = base64.b64encode(json.dumps(manifest).encode()).decode()
prompt = (
    "You are reviewing a GoldenMCP eval score manifest produced for an MCP server.\n"
    "Assess whether the scores in manifest.json are internally consistent and the "
    "composite is plausible.\n"
    "Reply with a short verdict: state PASS or FAIL and one sentence of reasoning."
)
body = {
    "model": "gemma4",
    "prompt": prompt,
    "resources": [
        {"filename": "manifest.json", "content_type": "application/json", "content_base64": b64}
    ],
    "cre_callback": {"url": os.environ["TRIGGER_URL"]},
}
print(json.dumps(body))
PY
)"

submit_resp="$(curl -fsS -X POST "${CAI_URL}/v1/inference" \
  -H "Authorization: Bearer ${CAI_API_KEY}" \
  -H "Content-Type: application/json" \
  -d "${submit_body}")"
python3 -c "import sys,json; print(json.load(sys.stdin)['id'])" <<<"${submit_resp}"
EOSH
)"
INFERENCE_ID="$(printf '%s' "${INFERENCE_ID}" | tr -d '[:space:]')"
[[ -n "${INFERENCE_ID}" ]] || { echo "FATAL: CAI submit returned no inference id" >&2; exit 1; }
note "inference_id=${INFERENCE_ID}"

# ============================================================================
# Step 5 — register the inference_id -> run_id mapping (handler A).
# ============================================================================
log "Step 5/8 — POST /eval/cai-submitted (map inference_id -> run_id)"

droplet_run "INFERENCE_ID=${INFERENCE_ID}" "RUN_ID=${RUN_ID}" <<'EOSH'
curl -fsS -X POST "${EVAL_RUNNER_BASE}/eval/cai-submitted" \
  -H "Authorization: Bearer ${EVAL_RUNNER_API_KEY}" \
  -H "Content-Type: application/json" \
  -d "{\"inference_id\":\"${INFERENCE_ID}\",\"run_id\":\"${RUN_ID}\"}" >/dev/null
echo "mapped"
EOSH
note "mapping registered."

# ============================================================================
# Step 6 — poll CAI until completed (the callback fires handler B).
# ============================================================================
log "Step 6/8 — poll GET /v1/inference/${INFERENCE_ID} until completed"

cai_status=""
for attempt in $(seq 1 60); do
  cai_status="$(droplet_run "INFERENCE_ID=${INFERENCE_ID}" <<'EOSH'
CAI_URL="${CHAINLINK_CAI_URL:-https://confidential-ai-dev-preview.cldev.cloud}"
resp="$(curl -fsS "${CAI_URL}/v1/inference/${INFERENCE_ID}" \
  -H "Authorization: Bearer ${CHAINLINK_CAI_API_KEY}")"
python3 -c "import sys,json; print(json.load(sys.stdin).get('status','unknown'))" <<<"${resp}"
EOSH
)"
  cai_status="$(printf '%s' "${cai_status}" | tr -d '[:space:]')"
  note "attempt ${attempt}/60 — CAI status=${cai_status}"
  case "${cai_status}" in
    completed) break ;;
    failed)    echo "FATAL: CAI inference failed" >&2; exit 1 ;;
  esac
  sleep 10
done
[[ "${cai_status}" == "completed" ]] || { echo "FATAL: CAI did not complete in time" >&2; exit 1; }
note "CAI inference completed — callback delivered to handler B."

# ============================================================================
# Step 7 — poll the eval run until published -> walrus_manifest_blob_id.
# Handler B publishes to Walrus and writes the attestation to Arc.
# ============================================================================
log "Step 7/8 — poll GET /eval/runs/${RUN_ID} until status=published"

WALRUS_BLOB_ID=""
run_status=""
for attempt in $(seq 1 60); do
  run_out="$(droplet_run "RUN_ID=${RUN_ID}" <<'EOSH'
resp="$(curl -fsS "${EVAL_RUNNER_BASE}/eval/runs/${RUN_ID}" \
  -H "Authorization: Bearer ${EVAL_RUNNER_API_KEY}")"
python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('status','unknown')); print(d.get('walrus_manifest_blob_id') or '')" <<<"${resp}"
EOSH
)"
  run_status="$(printf '%s\n' "${run_out}" | sed -n '1p' | tr -d '[:space:]')"
  WALRUS_BLOB_ID="$(printf '%s\n' "${run_out}" | sed -n '2p' | tr -d '[:space:]')"
  note "attempt ${attempt}/60 — run status=${run_status}"
  case "${run_status}" in
    published) break ;;
    failed)    echo "FATAL: eval run failed during publish" >&2; exit 1 ;;
  esac
  sleep 10
done
[[ "${run_status}" == "published" ]] || { echo "FATAL: eval run did not reach published in time" >&2; exit 1; }
note "published — walrus_manifest_blob_id=${WALRUS_BLOB_ID:-<none>}"

# ============================================================================
# Step 8 — read on-chain getRecord(1) + harvest the trigger log.
# ============================================================================
log "Step 8/8 — read on-chain getRecord(${AGENT_ID}) + harvest trigger log"

# decode_get_record emits: lastAttestationId / lastTranscriptHash / exists.
record_out="$(decode_get_record "${AGENT_ID}")"
ON_CHAIN_ATTESTATION_ID="$(printf '%s\n' "${record_out}" | sed -n '1p')"
ON_CHAIN_TRANSCRIPT_HASH="$(printf '%s\n' "${record_out}" | sed -n '2p' | tr -d '[:space:]')"

# The deployer/payee Arc balance (Arc's native gas token is USDC).
PAYEE_BALANCE_WEI="$(cast balance "${PAYEE_ADDRESS}" --rpc-url "${ARC_RPC_URL}" 2>/dev/null || echo 0)"
PAYEE_BALANCE_USDC="$(cast from-wei "${PAYEE_BALANCE_WEI}" 2>/dev/null || echo "?")"

# Discover the recordAttestation tx hash + transcript hash from the trigger log.
RECORD_TX_HASH="$(ssh -o BatchMode=yes -o ConnectTimeout=15 "${DROPLET_SSH}" \
  "grep -oE 'recordAttestation tx hash=(0x)?[0-9a-fA-F]+' ${TRIGGER_LOG} 2>/dev/null | tail -1 | sed 's/.*hash=//'" \
  2>/dev/null || true)"
RECORD_TX_HASH="$(printf '%s' "${RECORD_TX_HASH}" | tr -d '[:space:]')"
if [[ -n "${RECORD_TX_HASH}" && "${RECORD_TX_HASH}" != 0x* ]]; then
  RECORD_TX_HASH="0x${RECORD_TX_HASH}"
fi

# The transcript hash the trigger logged (for the PASS/FAIL cross-check).
LOG_TRANSCRIPT_HASH="$(ssh -o BatchMode=yes -o ConnectTimeout=15 "${DROPLET_SSH}" \
  "grep -oE 'transcript_hash=(0x)?[0-9a-fA-F]{64}' ${TRIGGER_LOG} 2>/dev/null | tail -1 | sed 's/.*transcript_hash=//'" \
  2>/dev/null || true)"
LOG_TRANSCRIPT_HASH="$(printf '%s' "${LOG_TRANSCRIPT_HASH}" | tr -d '[:space:]')"
if [[ -n "${LOG_TRANSCRIPT_HASH}" && "${LOG_TRANSCRIPT_HASH}" != 0x* ]]; then
  LOG_TRANSCRIPT_HASH="0x${LOG_TRANSCRIPT_HASH}"
fi

# ============================================================================
# PASS/FAIL determination.
# PASS iff on-chain lastTranscriptHash is non-zero AND (when the log hash is
# discoverable) matches the hash the trigger logged.
# ============================================================================
ZERO_BYTES32="0x0000000000000000000000000000000000000000000000000000000000000000"
RESULT="FAIL"
RESULT_REASON=""
oc_lower="$(printf '%s' "${ON_CHAIN_TRANSCRIPT_HASH}" | tr 'A-F' 'a-f')"
log_lower="$(printf '%s' "${LOG_TRANSCRIPT_HASH}" | tr 'A-F' 'a-f')"
if [[ -z "${ON_CHAIN_TRANSCRIPT_HASH}" || "${oc_lower}" == "${ZERO_BYTES32}" ]]; then
  RESULT_REASON="on-chain lastTranscriptHash is zero/empty"
elif [[ -n "${log_lower}" && "${oc_lower}" != "${log_lower}" ]]; then
  RESULT_REASON="on-chain hash != trigger-log hash"
elif [[ -z "${log_lower}" ]]; then
  RESULT="PASS"
  RESULT_REASON="on-chain hash non-zero (trigger-log hash not found for cross-check)"
else
  RESULT="PASS"
  RESULT_REASON="on-chain hash non-zero AND matches trigger-log hash"
fi

# ============================================================================
# FINAL SUMMARY
# ============================================================================
cat <<SUMMARY

============================================================================
  GoldenMCP async CAI attestation — RUN SUMMARY (GH #54)
============================================================================

Run / inference
  run_id .................. ${RUN_ID}
  CAI inference id ........ ${INFERENCE_ID}
    (== on-chain lastAttestationId; inspect in the CAI console/playground at
     ${CAI_URL})

Arc testnet (chain 5042002 — native gas token is USDC)
  MCPRegistry contract .... ${ARC_REGISTRY_ADDRESS}
    ${ARCSCAN_BASE}/address/${ARC_REGISTRY_ADDRESS}
  KeystoneForwarder ....... ${FORWARDER_ADDRESS}
    ${ARCSCAN_BASE}/address/${FORWARDER_ADDRESS}
  Deployer / payee wallet . ${PAYEE_ADDRESS}
    balance: ${PAYEE_BALANCE_USDC} USDC (Arc gas token)
    ${ARCSCAN_BASE}/address/${PAYEE_ADDRESS}
  recordAttestation tx .... ${RECORD_TX_HASH:-<not found in trigger log>}
    ${RECORD_TX_HASH:+${ARCSCAN_BASE}/tx/${RECORD_TX_HASH}}

On-chain getRecord(${AGENT_ID})
  lastAttestationId ....... ${ON_CHAIN_ATTESTATION_ID:-<empty>}
  lastTranscriptHash ...... ${ON_CHAIN_TRANSCRIPT_HASH:-<empty>}
  trigger-log txhash ...... ${LOG_TRANSCRIPT_HASH:-<not found>}

Walrus manifest
  blob id ................. ${WALRUS_BLOB_ID:-<none>}
    ${WALRUS_BLOB_ID:+${WALRUS_AGGREGATOR_URL%/}/v1/blobs/${WALRUS_BLOB_ID}}

----------------------------------------------------------------------------
  RESULT: ${RESULT}  (${RESULT_REASON})
----------------------------------------------------------------------------
SUMMARY

[[ "${RESULT}" == "PASS" ]] || exit 1
