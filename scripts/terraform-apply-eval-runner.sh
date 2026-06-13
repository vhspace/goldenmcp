#!/usr/bin/env bash
# Apply or plan the DigitalOcean eval-runner Terraform module.
# Requires DO_API_KEY in repo-root .env (never commit .env).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TF_DIR="${ROOT}/infra/terraform/eval-runner"
ENV_FILE="${ROOT}/.env"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "ERROR: missing ${ENV_FILE} — copy .env.example and set DO_API_KEY" >&2
  exit 1
fi

# shellcheck disable=SC1090
set -a
source "${ENV_FILE}"
set +a

if [[ -z "${DO_API_KEY:-}" ]]; then
  echo "ERROR: DO_API_KEY is unset in ${ENV_FILE}" >&2
  exit 1
fi

export DIGITALOCEAN_TOKEN="${DO_API_KEY}"

ACTION="${1:-plan}"
case "${ACTION}" in
  plan|apply|destroy|output|init|validate)
    ;;
  *)
    echo "Usage: $0 [plan|apply|destroy|output|init|validate]" >&2
    exit 1
    ;;
esac

ensure_operator_ssh_key() {
  local pubkey_path="${HOME}/.ssh/id_ed25519.pub"
  local key_name="ballew-ed25519"
  if [[ ! -f "${pubkey_path}" ]]; then
    echo "ERROR: missing ${pubkey_path}" >&2
    exit 1
  fi
  local pubkey
  pubkey="$(cat "${pubkey_path}")"
  local response
  response="$(curl -sf \
    -H "Authorization: Bearer ${DO_API_KEY}" \
    -H "Content-Type: application/json" \
    "https://api.digitalocean.com/v2/account/keys")" || {
    echo "ERROR: failed to list DigitalOcean SSH keys via API" >&2
    exit 1
  }
  local existing_name
  existing_name="$(python3 -c '
import json, sys
data = json.load(sys.stdin)
pubkey = sys.argv[1]
for k in data.get("ssh_keys", []):
    if k.get("public_key", "").strip() == pubkey.strip():
        print(k["name"])
        break
' "${pubkey}" <<<"${response}")"
  if [[ -n "${existing_name}" ]]; then
    echo "DigitalOcean SSH key already registered: ${existing_name}" >&2
    echo "${existing_name}"
    return 0
  fi
  echo "Uploading ${pubkey_path} to DigitalOcean as ${key_name}..." >&2
  curl -sf -X POST \
    -H "Authorization: Bearer ${DO_API_KEY}" \
    -H "Content-Type: application/json" \
    -d "$(python3 -c 'import json,sys; print(json.dumps({"name":sys.argv[1],"public_key":sys.argv[2]}))' "${key_name}" "${pubkey}")" \
    "https://api.digitalocean.com/v2/account/keys" >/dev/null
  echo "${key_name}"
}

if [[ -z "${TF_VAR_ssh_key_names:-}" ]]; then
  KEY_NAME="$(ensure_operator_ssh_key)"
  export TF_VAR_ssh_key_names
  TF_VAR_ssh_key_names="$(python3 -c 'import json,sys; print(json.dumps([sys.argv[1]]))' "${KEY_NAME}")"
  echo "Using DigitalOcean SSH key: ${TF_VAR_ssh_key_names}"
fi

cd "${TF_DIR}"

if [[ "${ACTION}" == "init" ]]; then
  terraform init
  exit 0
fi

terraform init -input=false

if [[ "${ACTION}" == "validate" ]]; then
  terraform validate
  exit 0
fi

if [[ "${ACTION}" == "output" ]]; then
  shift || true
  terraform output "$@"
  exit 0
fi

if [[ "${ACTION}" == "apply" ]]; then
  terraform apply -input=false -auto-approve
else
  terraform "${ACTION}" -input=false
fi
