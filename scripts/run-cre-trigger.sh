#!/usr/bin/env bash
# Run the CRE eval-pipeline workflow long-lived, serving its HTTP trigger on
# port 2000 (path /trigger) so the Confidential AI Attester's cre_callback can
# reach handler B directly (GH #54). Requires cre CLI >= 1.19.0.
#
# On the demo droplet (159.203.78.85) run this under tmux/systemd so the trigger
# stays up; CAI posts the completed inference to http://<ip>:2000/trigger. The
# droplet firewall must allow inbound :2000.
#
# Usage: ./scripts/run-cre-trigger.sh [target]   (default target: staging-do)
set -euo pipefail

TARGET="${1:-staging-do}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "${ROOT}"

ver="$(cre version 2>/dev/null | grep -oE 'v?[0-9]+\.[0-9]+\.[0-9]+' | head -1 || true)"
echo "cre version: ${ver:-unknown} (need >= 1.19.0 to serve the local HTTP trigger)"

# --broadcast performs the real on-chain Arc write via the MockKeystoneForwarder.
# No --http-payload: with cre >= 1.19 this serves the trigger and waits for CAI.
exec cre workflow simulate eval-pipeline --target "${TARGET}" --broadcast
