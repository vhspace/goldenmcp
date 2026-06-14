#!/usr/bin/env bash
# Discover eval-runner droplet IP and SSH keys from Terraform state (preferred) or DO API.
# Does not require DO_API_KEY when local terraform.tfstate exists.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TF_DIR="${ROOT}/infra/terraform/eval-runner"
TFSTATE="${TF_DIR}/terraform.tfstate"
ENV_FILE="${ROOT}/.env"
STAGING_DO_CONFIG="${ROOT}/workflows/eval-pipeline/config.staging-do.json"
DROPLET_NAME="${TF_VAR_droplet_name:-goldenmcp-eval-runner}"
DROPLET_TAG="${TF_VAR_droplet_tag:-eval-runner}"

usage() {
  cat <<EOF
Usage: $(basename "$0") [--json|--text]

Print eval-runner deploy info: droplet IP, SSH key names/fingerprints, ssh command.

Resolution order:
  1. terraform output (local state in infra/terraform/eval-runner/)
  2. Parse terraform.tfstate directly (no terraform CLI)
  3. workflows/eval-pipeline/config.staging-do.json evalRunnerUrl (IP only)
  4. DigitalOcean API (needs DO_API_KEY in repo-root .env)

EOF
}

format="${1:---json}"
case "${format}" in
  --json|--text|-h|--help)
    ;;
  *)
    echo "ERROR: unknown argument ${format}" >&2
    usage >&2
    exit 1
    ;;
esac

if [[ "${format}" == "-h" || "${format}" == "--help" ]]; then
  usage
  exit 0
fi

SOURCE=""
DROPLET_IP=""
DROPLET_ID=""
SSH_KEY_NAMES_JSON="[]"
SSH_FPS_JSON="[]"
SSH_COMMAND=""
HEALTH_URL=""

emit_json() {
  python3 -c '
import json, sys
print(json.dumps({
    "source": sys.argv[1],
    "droplet_ip": sys.argv[2] or None,
    "droplet_id": sys.argv[3] or None,
    "health_check_url": sys.argv[4] or None,
    "ssh_command": sys.argv[5] or None,
    "ssh_key_names": json.loads(sys.argv[6]),
    "ssh_key_fingerprints": json.loads(sys.argv[7]),
    "local_ssh_key_hint": sys.argv[8] or None,
    "notes": json.loads(sys.argv[9]),
}, indent=2))
' "${SOURCE}" "${DROPLET_IP}" "${DROPLET_ID}" "${HEALTH_URL}" "${SSH_COMMAND}" \
    "${SSH_KEY_NAMES_JSON}" "${SSH_FPS_JSON}" "${LOCAL_SSH_HINT:-}" "${NOTES_JSON:-[]}"
}

emit_text() {
  echo "source: ${SOURCE}"
  echo "droplet_ip: ${DROPLET_IP:-<unknown>}"
  [[ -n "${DROPLET_ID}" ]] && echo "droplet_id: ${DROPLET_ID}"
  [[ -n "${HEALTH_URL}" ]] && echo "health_check_url: ${HEALTH_URL}"
  [[ -n "${SSH_COMMAND}" ]] && echo "ssh_command: ${SSH_COMMAND}"
  echo "ssh_key_names: ${SSH_KEY_NAMES_JSON}"
  echo "ssh_key_fingerprints: ${SSH_FPS_JSON}"
  [[ -n "${LOCAL_SSH_HINT:-}" ]] && echo "local_ssh_key_hint: ${LOCAL_SSH_HINT}"
}

finish() {
  if [[ "${format}" == "--json" ]]; then
    emit_json
  else
    emit_text
  fi
}

guess_local_ssh_key() {
  local fp name pub
  while IFS= read -r fp; do
    [[ -z "${fp}" ]] && continue
    for pub in "${HOME}/.ssh/"*.pub; do
      [[ -f "${pub}" ]] || continue
      local pub_fp
      pub_fp="$(ssh-keygen -E md5 -lf "${pub}" 2>/dev/null | awk '{print $2}' | sed 's/^MD5://')"
      if [[ "${pub_fp}" == "${fp}" ]]; then
        LOCAL_SSH_HINT="${pub%.pub}"
        return 0
      fi
    done
  done < <(python3 -c 'import json,sys; [print(x) for x in json.loads(sys.argv[1])]' "${SSH_FPS_JSON}")
  return 1
}

load_from_terraform_output() {
  if [[ ! -d "${TF_DIR}" ]]; then
    return 1
  fi
  if ! command -v terraform >/dev/null 2>&1; then
    return 1
  fi
  if [[ ! -f "${TFSTATE}" ]]; then
    return 1
  fi
  local out
  if ! out="$(terraform -chdir="${TF_DIR}" output -json 2>/dev/null)"; then
    return 1
  fi
  SOURCE="terraform_output"
  read -r DROPLET_IP DROPLET_ID HEALTH_URL SSH_COMMAND SSH_KEY_NAMES_JSON SSH_FPS_JSON <<<"$(
    python3 -c '
import json, sys
data = json.load(sys.stdin)
def val(key):
    o = data.get(key, {})
    return o.get("value")
ip = val("droplet_ip") or ""
did = str(val("droplet_id") or "")
health = val("health_check_url") or ""
ssh = val("ssh_command") or ""
names = json.dumps(val("ssh_key_names") or [])
fps = json.dumps(val("ssh_key_fingerprints") or [])
print(ip, did, health, ssh, names, fps)
' <<<"${out}"
  )"
  [[ -n "${DROPLET_IP}" ]] || return 1
  NOTES_JSON='["Read from terraform output -json"]'
  guess_local_ssh_key || true
  finish
  exit 0
}

load_from_tfstate() {
  if [[ ! -f "${TFSTATE}" ]]; then
    return 1
  fi
  SOURCE="terraform_tfstate"
  read -r DROPLET_IP DROPLET_ID SSH_KEY_NAMES_JSON SSH_FPS_JSON <<<"$(
    python3 -c '
import json, sys
with open(sys.argv[1]) as f:
    state = json.load(f)
resources = state.get("resources") or []
ip = ""
did = ""
names = []
fps = []
for r in resources:
    if r.get("type") != "digitalocean_droplet":
        continue
    for inst in r.get("instances") or []:
        attrs = inst.get("attributes") or {}
        ip = attrs.get("ipv4_address") or ip
        did = str(attrs.get("id") or did)
for r in resources:
    if r.get("type") != "digitalocean_ssh_key":
        continue
    for inst in r.get("instances") or []:
        attrs = inst.get("attributes") or {}
        if attrs.get("name"):
            names.append(attrs["name"])
        if attrs.get("fingerprint"):
            fps.append(attrs["fingerprint"])
# outputs block (terraform 1.x)
for key, out in (state.get("outputs") or {}).items():
    val = out.get("value")
    if key == "droplet_ip" and val:
        ip = val
    if key == "droplet_id" and val:
        did = str(val)
    if key == "ssh_key_names" and val:
        names = val
    if key == "ssh_key_fingerprints" and val:
        fps = val
print(ip, did, json.dumps(names), json.dumps(fps))
' "${TFSTATE}"
  )"
  [[ -n "${DROPLET_IP}" ]] || return 1
  HEALTH_URL="https://${DROPLET_IP}/health"
  SSH_COMMAND="ssh root@${DROPLET_IP}"
  NOTES_JSON='["Parsed infra/terraform/eval-runner/terraform.tfstate directly"]'
  guess_local_ssh_key || true
  finish
  exit 0
}

load_from_staging_config() {
  if [[ ! -f "${STAGING_DO_CONFIG}" ]]; then
    return 1
  fi
  DROPLET_IP="$(python3 -c '
import json, re, sys
from urllib.parse import urlparse
with open(sys.argv[1]) as f:
    url = json.load(f).get("evalRunnerUrl", "")
if not url:
    raise SystemExit(1)
host = urlparse(url).hostname or ""
if not re.match(r"^\d+\.\d+\.\d+\.\d+$", host):
    raise SystemExit(1)
print(host)
' "${STAGING_DO_CONFIG}" 2>/dev/null)" || return 1
  SOURCE="staging_do_config"
  HEALTH_URL="http://${DROPLET_IP}/health"
  SSH_COMMAND="ssh root@${DROPLET_IP}"
  NOTES_JSON='["IP only from config.staging-do.json — SSH key names unknown; use DO API fallback or terraform state"]'
  finish
  exit 0
}

load_from_do_api() {
  if [[ ! -f "${ENV_FILE}" ]]; then
    echo "ERROR: no terraform state and missing ${ENV_FILE} for DO API fallback" >&2
    exit 1
  fi
  # shellcheck disable=SC1090
  set -a
  source "${ENV_FILE}"
  set +a
  if [[ -z "${DO_API_KEY:-}" ]]; then
    echo "ERROR: DO_API_KEY unset in ${ENV_FILE}" >&2
    exit 1
  fi
  local response
  response="$(curl -sf \
    -H "Authorization: Bearer ${DO_API_KEY}" \
    -H "Content-Type: application/json" \
    "https://api.digitalocean.com/v2/droplets?tag_name=${DROPLET_TAG}")" || {
    echo "ERROR: DO API droplet list failed (tag=${DROPLET_TAG})" >&2
    exit 1
  }
  read -r DROPLET_IP DROPLET_ID SSH_KEY_NAMES_JSON SSH_FPS_JSON <<<"$(
    python3 -c '
import json, sys
data = json.load(sys.stdin)
name = sys.argv[1]
droplets = data.get("droplets") or []
match = None
for d in droplets:
    if d.get("name") == name:
        match = d
        break
if match is None and droplets:
    match = droplets[0]
if match is None:
    raise SystemExit(1)
networks = match.get("networks", {}).get("v4") or []
ip = next((n["ip_address"] for n in networks if n.get("type") == "public"), "")
did = str(match.get("id") or "")
names = []
fps = []
for kid in match.get("ssh_keys") or []:
    fps.append(str(kid))
print(ip, did, json.dumps(names), json.dumps(fps))
' "${DROPLET_NAME}" <<<"${response}"
  )" || {
    echo "ERROR: no droplet found with tag ${DROPLET_TAG} or name ${DROPLET_NAME}" >&2
    exit 1
  }
  # Enrich SSH key names from account keys when we only have IDs/fingerprints
  local keys_response
  keys_response="$(curl -sf \
    -H "Authorization: Bearer ${DO_API_KEY}" \
    "https://api.digitalocean.com/v2/account/keys")" || true
  if [[ -n "${keys_response}" ]]; then
    read -r SSH_KEY_NAMES_JSON SSH_FPS_JSON <<<"$(
      python3 -c '
import json, sys
droplet_fps = set(json.loads(sys.argv[1]))
keys = json.load(sys.stdin).get("ssh_keys") or []
names = []
fps = []
for k in keys:
    fp = k.get("fingerprint")
    if fp and (not droplet_fps or fp in droplet_fps or str(k.get("id")) in droplet_fps):
        names.append(k["name"])
        fps.append(fp)
if not names:
    for k in keys:
        names.append(k["name"])
        fps.append(k.get("fingerprint", ""))
print(json.dumps(names), json.dumps(fps))
' "${SSH_FPS_JSON}" <<<"${keys_response}"
    )"
  fi
  SOURCE="digitalocean_api"
  HEALTH_URL="https://${DROPLET_IP}/health"
  SSH_COMMAND="ssh root@${DROPLET_IP}"
  NOTES_JSON='["Resolved via DigitalOcean API — verify IP against terraform state if available elsewhere"]'
  guess_local_ssh_key || true
  finish
  exit 0
}

load_from_terraform_output || true
load_from_tfstate || true
load_from_staging_config || true
load_from_do_api
