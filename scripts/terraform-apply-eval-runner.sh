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

if [[ -z "${TF_VAR_ssh_public_key:-}" ]]; then
  for key in "${HOME}/.ssh/id_ed25519.pub" "${HOME}/.ssh/id_rsa.pub"; do
    if [[ -f "${key}" ]]; then
      export TF_VAR_ssh_public_key
      TF_VAR_ssh_public_key="$(cat "${key}")"
      echo "Using SSH public key: ${key}"
      break
    fi
  done
fi

if [[ -z "${TF_VAR_ssh_public_key:-}" ]]; then
  echo "ERROR: set TF_VAR_ssh_public_key or install ~/.ssh/id_ed25519.pub" >&2
  exit 1
fi

if [[ -z "${TF_VAR_allowed_ssh_cidrs:-}" ]]; then
  echo "ERROR: set TF_VAR_allowed_ssh_cidrs, e.g. export TF_VAR_allowed_ssh_cidrs='[\"203.0.113.10/32\"]'" >&2
  exit 1
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

terraform "${ACTION}" -input=false
