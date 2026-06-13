#!/usr/bin/env bash
# Upsert Cloudflare A record for the eval-runner droplet (GH #73).
# Requires CF_API_KEY, CF_ZONE_ID, and EVAL_RUNNER_DNS_NAME in repo-root .env.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ROOT}/.env"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "ERROR: missing ${ENV_FILE}" >&2
  exit 1
fi

# shellcheck disable=SC1090
set -a
source "${ENV_FILE}"
set +a

for var in CF_API_KEY CF_ZONE_ID EVAL_RUNNER_DNS_NAME; do
  if [[ -z "${!var:-}" ]]; then
    echo "ERROR: set ${var} in ${ENV_FILE}" >&2
    exit 1
  fi
done

DROPLET_IP="${1:-}"
if [[ -z "${DROPLET_IP}" ]]; then
  if [[ -d "${ROOT}/infra/terraform/eval-runner" ]] && command -v terraform >/dev/null; then
    DROPLET_IP="$(terraform -chdir="${ROOT}/infra/terraform/eval-runner" output -raw droplet_ip 2>/dev/null || true)"
  fi
fi
if [[ -z "${DROPLET_IP}" ]]; then
  echo "Usage: $0 <droplet_ip>" >&2
  echo "  or set terraform output droplet_ip" >&2
  exit 1
fi

DNS_NAME="${EVAL_RUNNER_DNS_NAME}"
API="https://api.cloudflare.com/client/v4"

echo "Looking up existing A record for ${DNS_NAME} ..."
EXISTING="$(curl -sf -G "${API}/zones/${CF_ZONE_ID}/dns_records" \
  -H "Authorization: Bearer ${CF_API_KEY}" \
  --data-urlencode "type=A" \
  --data-urlencode "name=${DNS_NAME}")"

RECORD_ID="$(python3 -c "import json,sys; d=json.load(sys.stdin); recs=d.get('result',[]); print(recs[0]['id'] if recs else '')" <<<"${EXISTING}")"

PAYLOAD="$(python3 -c "import json; print(json.dumps({'type':'A','name':'${DNS_NAME}','content':'${DROPLET_IP}','ttl':300,'proxied':False}))")"

if [[ -n "${RECORD_ID}" ]]; then
  echo "Updating record ${RECORD_ID} -> ${DROPLET_IP}"
  curl -sf -X PUT "${API}/zones/${CF_ZONE_ID}/dns_records/${RECORD_ID}" \
    -H "Authorization: Bearer ${CF_API_KEY}" \
    -H "Content-Type: application/json" \
    -d "${PAYLOAD}" | python3 -c "import json,sys; r=json.load(sys.stdin); print('updated', r['result']['name'], r['result']['content'])"
else
  echo "Creating A record ${DNS_NAME} -> ${DROPLET_IP}"
  curl -sf -X POST "${API}/zones/${CF_ZONE_ID}/dns_records" \
    -H "Authorization: Bearer ${CF_API_KEY}" \
    -H "Content-Type: application/json" \
    -d "${PAYLOAD}" | python3 -c "import json,sys; r=json.load(sys.stdin); print('created', r['result']['name'], r['result']['content'])"
fi

echo "Verify: dig +short ${DNS_NAME}"
echo "Set EVAL_RUNNER_PUBLIC_URL=https://${DNS_NAME} and re-run sync-eval-runner-secrets.sh"
