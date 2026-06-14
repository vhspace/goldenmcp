#!/usr/bin/env bash
# Run specific benchmark pairs through the CRE workflow, one fully-aligned pair at
# a time. For each target we set the eval-runner cursor to the benchmark's model-0
# index and restart the eval-runner, guaranteeing leg1=model0 / leg2=model1 with
# no cursor desync even if a previous benchmark failed.
#
# Handler A is fired via the HTTP-run trigger (index 2); handler B (the CAI
# callback) listens on :2000 (index 1) and is re-armed per pair (one-shot).
#
# Usage (run as root so it can edit /etc/goldenmcp/.env + restart the service):
#   run-pairs.sh "12:lifi/quote 8:kyberswap/quote 16:odos/quote ..."
set -u
ENVF=/etc/goldenmcp/.env
WF=workflows/eval-pipeline
PAYLOAD=/tmp/p.json
LOG=/tmp/runpairs
mkdir -p "$LOG"
cd /opt/goldenmcp || exit 1

# Run cre as the goldenmcp user (it has the ~/.cre creds + bun on PATH).
run_cre () { # $@ = simulate args ; writes to $OUT (env); runs in background
  su - goldenmcp -c "set -a; source $ENVF 2>/dev/null; set +a; \
    export PATH=/home/goldenmcp/.bun/bin:/usr/local/bin:/usr/bin:/bin; \
    export EVAL_RUNNER_API_KEY_VAR=\${EVAL_RUNNER_API_KEY:-dev-key}; \
    export CHAINLINK_CAI_API_KEY_VAR=\${CHAINLINK_CAI_API_KEY}; \
    export CRE_ETH_PRIVATE_KEY=\${MARKETPLACE_WALLET_PRIVATE_KEY}; \
    cd /opt/goldenmcp; nohup timeout $1 cre workflow simulate $WF --target staging-do $2 --broadcast --skip-type-checks > $3 2>&1 &"
}

set_cursor () { # $1 = index
  if grep -q '^GOLDENMCP_CURSOR_START=' "$ENVF"; then
    sed -i "s/^GOLDENMCP_CURSOR_START=.*/GOLDENMCP_CURSOR_START=$1/" "$ENVF"
  else
    echo "GOLDENMCP_CURSOR_START=$1" >> "$ENVF"
  fi
  systemctl restart goldenmcp-eval-runner
  local i=0
  while [ $i -lt 30 ]; do
    curl -s -m4 http://127.0.0.1/health 2>/dev/null | grep -q '"status":"ok"' && return 0
    sleep 1; i=$((i+1))
  done
  return 1
}

arm_B () { # $1 = logfile
  pkill -9 -f "trigger-index 1" 2>/dev/null
  sleep 1
  run_cre 320 "--listen --trigger-index 1" "$1"
  local i=0
  while [ $i -lt 45 ]; do
    ss -ltn 2>/dev/null | grep -q :2000 && return 0
    sleep 1; i=$((i+1))
  done
  return 1
}

fire_A () { # $1 = logfile
  run_cre 200 "--trigger-index 2 --http-payload $PAYLOAD" "$1"
}

wait_for () { # $1=file $2=pattern $3=timeout_s ; rc0=match rc1=timeout rc2=workflow-failed
  local f=$1 pat=$2 to=$3 i=0
  while [ $i -lt "$to" ]; do
    grep -qE "$pat" "$f" 2>/dev/null && return 0
    grep -qE "Workflow execution failed" "$f" 2>/dev/null && return 2
    sleep 3; i=$((i+3))
  done
  return 1
}

for spec in $1; do
  idx=${spec%%:*}
  name=${spec#*:}
  echo "===== $name (cursor=$idx) ====="
  set_cursor "$idx" || { echo "[$name] eval-runner restart failed"; continue; }
  arm_B "$LOG/B_${idx}.log" || { echo "[$name] handler B failed to listen"; continue; }

  echo "[$name] firing leg 1..."
  fire_A "$LOG/${idx}_l1.log"
  if wait_for "$LOG/${idx}_l1.log" ":waiting|waiting for the other model" 150; then
    echo "[$name] leg1 parked"
  else
    echo "[$name] leg1 FAILED:"; grep -E "failed|429|McpError|Connection" "$LOG/${idx}_l1.log" | tail -1
    pkill -9 -f "trigger-index 2" 2>/dev/null; pkill -9 -f "trigger-index 1" 2>/dev/null
    continue
  fi
  pkill -9 -f "trigger-index 2" 2>/dev/null; sleep 1

  echo "[$name] firing leg 2..."
  fire_A "$LOG/${idx}_l2.log"
  if wait_for "$LOG/${idx}_l2.log" ":attested:|pair complete" 150; then
    echo "[$name] pair complete -> CAI submitted"
  else
    echo "[$name] leg2 FAILED:"; grep -E "failed|429|McpError|Connection" "$LOG/${idx}_l2.log" | tail -1
    pkill -9 -f "trigger-index 2" 2>/dev/null; pkill -9 -f "trigger-index 1" 2>/dev/null
    continue
  fi
  pkill -9 -f "trigger-index 2" 2>/dev/null

  echo "[$name] waiting for CAI callback -> Arc..."
  if wait_for "$LOG/B_${idx}.log" "updateCapabilityScore tx hash" 260; then
    echo "[$name] ON-CHAIN:"; grep -E "recordAttestation tx hash|updateCapabilityScore tx hash" "$LOG/B_${idx}.log" | tail -2
  else
    echo "[$name] no Arc write within budget:"; grep -E "Attestation callback|publish|failed" "$LOG/B_${idx}.log" | tail -2
  fi
  pkill -9 -f "trigger-index 1" 2>/dev/null
done
echo "===== ALL DONE ====="
