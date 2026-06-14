#!/usr/bin/env bash
# Provision a DigitalOcean droplet to run the async CAI attestation flow (GH #54):
# the eval-runner HTTP service + a long-lived CRE HTTP-trigger server on :2000 that
# the Confidential AI Attester's cre_callback posts to.
#
# Idempotent-ish: safe to re-run; it re-syncs code, (re)installs cre, reopens :2000,
# and restarts the services. Run from the repo root on your laptop.
#
# Prereqs in repo-root .env: DO_API_KEY (DigitalOcean), and the eval-runner/CAI/Walrus
# secrets the droplet needs (synced via scripts/sync-eval-runner-secrets.sh).
#
# Usage:
#   ./scripts/provision-cre-trigger-droplet.sh <droplet_ip> [git_branch]
#
# What it does:
#   1. rsync the eval-runner + inspect-web3 packages to /opt/goldenmcp
#   2. uv sync + restart the goldenmcp-eval-runner systemd service
#   3. install the Linux cre CLI (>= 1.19) to /usr/local/bin/cre
#   4. open tcp/2000 on the DO cloud firewall (and ufw if active)
#   5. start the CRE trigger under tmux (session: cre-trigger) serving :2000/trigger
#
# NOTE: this assumes the droplet already exists (created by
# scripts/terraform-apply-eval-runner.sh) with /opt/goldenmcp checked out and the
# goldenmcp-eval-runner.service unit installed by cloud-init. For a brand-new box,
# run terraform first, then this.
set -euo pipefail

IP="${1:?usage: provision-cre-trigger-droplet.sh <droplet_ip> [git_branch]}"
BRANCH="${2:-main}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ROOT}/.env"
SSH="ssh -o ConnectTimeout=15 -o StrictHostKeyChecking=accept-new root@${IP}"
CRE_VERSION="v1.20.0"
INSTALL_DIR="/opt/goldenmcp"

[[ -f "${ENV_FILE}" ]] || { echo "ERROR: missing ${ENV_FILE}" >&2; exit 1; }
# shellcheck disable=SC1090
set -a; source "${ENV_FILE}"; set +a
: "${DO_API_KEY:?DO_API_KEY required in .env}"

echo "==> 1/5 rsync code to ${IP}:${INSTALL_DIR}"
for pkg in eval-runner/src/goldenmcp_eval_runner inspect-web3/src/goldenmcp_inspect; do
  rsync -az --delete \
    --exclude='__pycache__' --exclude='*.pyc' --exclude='.venv' --exclude='node_modules' \
    "${ROOT}/packages/${pkg}/" \
    "root@${IP}:${INSTALL_DIR}/packages/${pkg}/"
done
# Workflow code (so the droplet can serve the trigger from the same tree).
rsync -az --delete --exclude='node_modules' --exclude='.cre_build_tmp.*' \
  "${ROOT}/workflows/eval-pipeline/" "root@${IP}:${INSTALL_DIR}/workflows/eval-pipeline/"
${SSH} "chown -R goldenmcp:goldenmcp ${INSTALL_DIR}/packages ${INSTALL_DIR}/workflows"

echo "==> 2/5 uv sync + restart eval-runner"
${SSH} "cd ${INSTALL_DIR} && sudo -u goldenmcp /home/goldenmcp/.local/bin/uv sync --all-packages >/dev/null 2>&1 || true; systemctl restart goldenmcp-eval-runner; sleep 5; systemctl is-active goldenmcp-eval-runner"

echo "==> 3/7 install cre ${CRE_VERSION} (linux amd64)"
# 'cre update' is unreliable (slow CDN -> timeout); install the release tarball directly.
${SSH} bash -s <<EOF
set -e
if cre version 2>/dev/null | grep -q "${CRE_VERSION#v}"; then
  echo "cre ${CRE_VERSION} already installed"
else
  cd /tmp
  curl -sSL -m 180 "https://github.com/smartcontractkit/cre-cli/releases/download/${CRE_VERSION}/cre_linux_amd64.tar.gz" -o cre.tar.gz
  tar xzf cre.tar.gz
  install -m 0755 cre_*_linux_amd64 /usr/local/bin/cre
  cre version | head -1
fi
EOF

echo "==> 4/7 authenticate cre (copy local ~/.cre creds, or set CRE_API_KEY)"
# The trigger needs an authenticated cre. Non-interactive options:
#   (a) copy your local browser-login creds (~/.cre/context.yaml + cre.yaml), or
#   (b) set CRE_API_KEY in the droplet env (create at app.chain.link).
if [[ -f "${HOME}/.cre/context.yaml" && -f "${HOME}/.cre/cre.yaml" ]]; then
  ${SSH} "mkdir -p /home/goldenmcp/.cre && chown goldenmcp:goldenmcp /home/goldenmcp/.cre"
  scp -q "${HOME}/.cre/context.yaml" "${HOME}/.cre/cre.yaml" "root@${IP}:/tmp/"
  ${SSH} "mv /tmp/context.yaml /tmp/cre.yaml /home/goldenmcp/.cre/ && chown goldenmcp:goldenmcp /home/goldenmcp/.cre/*.yaml && chmod 600 /home/goldenmcp/.cre/*.yaml && sudo -u goldenmcp env HOME=/home/goldenmcp cre whoami 2>&1 | tail -2"
else
  echo "  WARN: no local ~/.cre creds; ensure CRE_API_KEY is set on the droplet"
fi

echo "==> 5/7 install bun + workflow deps (CRE TS workflow needs bun + cre-setup)"
${SSH} bash -s <<EOF
set -e
command -v unzip >/dev/null || apt-get install -y unzip >/dev/null 2>&1
if ! sudo -u goldenmcp bash -lc '~/.bun/bin/bun --version' >/dev/null 2>&1; then
  sudo -u goldenmcp bash -lc 'curl -fsSL https://bun.sh/install | bash' >/dev/null 2>&1
fi
sudo -u goldenmcp bash -lc 'cd ${INSTALL_DIR}/workflows/eval-pipeline && ~/.bun/bin/bun install' 2>&1 | tail -2
EOF

echo "==> 6/7 open tcp/2000 (DO firewall + ufw if active)"
FWID=$(curl -s -m 15 -H "Authorization: Bearer ${DO_API_KEY}" \
  "https://api.digitalocean.com/v2/firewalls" \
  | python3 -c "import sys,json;fs=[f['id'] for f in json.load(sys.stdin)['firewalls'] if 'eval-runner' in f['name']];print(fs[0] if fs else '')")
if [[ -n "${FWID}" ]]; then
  curl -s -m 15 -X POST -H "Authorization: Bearer ${DO_API_KEY}" -H "Content-Type: application/json" \
    "https://api.digitalocean.com/v2/firewalls/${FWID}/rules" \
    -d '{"inbound_rules":[{"protocol":"tcp","ports":"2000","sources":{"addresses":["0.0.0.0/0","::/0"]}}]}' \
    -w "  DO firewall rule add: http=%{http_code}\n" -o /dev/null
else
  echo "  WARN: no eval-runner firewall found; skipping DO firewall"
fi
${SSH} "ufw status 2>/dev/null | grep -q '^Status: active' && ufw allow 2000/tcp || echo '  ufw inactive — no host rule needed'"

echo "==> 7/7 start CRE trigger under tmux (session cre-trigger)"
# Write a launcher on the droplet that sources the env + sets bun/cre on PATH, then
# run it under tmux as goldenmcp. secrets.yaml maps the *_VAR names; /etc/goldenmcp/.env
# provides the values. CRE_ETH_PRIVATE_KEY enables the --broadcast Arc write.
${SSH} bash -s <<EOF
set -e
cat > ${INSTALL_DIR}/run-trigger.sh <<'LAUNCH'
#!/usr/bin/env bash
set -a; source /etc/goldenmcp/.env 2>/dev/null; set +a
export PATH=/home/goldenmcp/.bun/bin:/usr/local/bin:/usr/bin:/bin
export EVAL_RUNNER_API_KEY_VAR="\${EVAL_RUNNER_API_KEY:-dev-key}"
export CHAINLINK_CAI_API_KEY_VAR="\${CHAINLINK_CAI_API_KEY}"
export CRE_ETH_PRIVATE_KEY="\${MARKETPLACE_WALLET_PRIVATE_KEY}"
cd ${INSTALL_DIR}
exec cre workflow simulate workflows/eval-pipeline --target staging-do --listen --trigger-index 1 --broadcast --skip-type-checks
LAUNCH
chmod +x ${INSTALL_DIR}/run-trigger.sh
chown goldenmcp:goldenmcp ${INSTALL_DIR}/run-trigger.sh
sudo -u goldenmcp tmux kill-session -t cre-trigger 2>/dev/null || true
sudo -u goldenmcp tmux new-session -d -s cre-trigger "bash ${INSTALL_DIR}/run-trigger.sh 2>&1 | tee /tmp/cre-trigger.log"
sleep 20
grep -iE "listening|Waiting|compiled|error|login" /tmp/cre-trigger.log | tail -4 || true
ss -ltn | grep ':2000' && echo "trigger listening on :2000" || echo "WARN: not listening yet"
EOF

echo
echo "Done. Trigger should be at http://${IP}:2000/trigger"
echo "  - eval-runner:  curl http://${IP}/health"
echo "  - trigger log:  ssh root@${IP} 'tail -f /var/log/cre-trigger.log'"
echo "  - reattach:     ssh root@${IP} 'tmux attach -t cre-trigger'"
echo "  - set creCallbackUrl=http://${IP}:2000/trigger in config.staging-do.json"
