# GoldenMCP eval-runner — DigitalOcean Terraform

Provisions an **8 GB RAM** droplet in `nyc3` for the Inspect eval-runner HTTP service ([GH #59](https://github.com/vhspace/goldenmcp/issues/59)).

## Prerequisites

- Terraform `>= 1.14.0` (latest recommended: 1.15.x)
- `DO_API_KEY` in repo-root `.env` (never commit)
- At least one SSH key already registered on your DigitalOcean account

## Quick start

From repo root:

```bash
# Plan + apply (exports DIGITALOCEAN_TOKEN from DO_API_KEY;
# auto-attaches all account SSH keys if TF_VAR_ssh_key_names is unset)
./scripts/terraform-apply-eval-runner.sh plan
./scripts/terraform-apply-eval-runner.sh apply

# Upload application secrets (LLM keys, MCP URLs, Walrus, wallet)
./scripts/sync-eval-runner-secrets.sh "$(terraform -chdir=infra/terraform/eval-runner output -raw droplet_ip)"

# Health check (self-signed TLS — use -k)
curl -k "https://$(terraform -chdir=infra/terraform/eval-runner output -raw droplet_ip)/health"

# Discover IP + SSH key without DO API (agents: see .cursor/skills/terraform-eval-runner-discover/)
./scripts/terraform-eval-runner-info.sh
```

## Secrets

- **Terraform / DO API:** `DO_API_KEY` in local `.env` only
- **Application secrets:** copied post-apply via `sync-eval-runner-secrets.sh` to `/etc/goldenmcp/.env` (mode 600). Not stored in Terraform state or cloud-init.

DigitalOcean Droplets do not have a native secrets vault (unlike App Platform encrypted env vars). Do not put LLM or wallet keys in `terraform.tfvars` or cloud-init.

## Configuration

The apply script discovers SSH keys from your DO account automatically. To attach a subset, set names explicitly:

```bash
export TF_VAR_ssh_key_names='["TAI"]'
```

List registered keys:

```bash
doctl compute ssh-key list --format Name,Fingerprint
# or: curl -H "Authorization: Bearer $DO_API_KEY" https://api.digitalocean.com/v2/account/keys
```

Copy `terraform.tfvars.example` to `terraform.tfvars` for non-secret overrides (region, droplet size, etc.).

SSH (port 22) is open to the world by default via the droplet firewall — no operator CIDR configuration required.

## Outputs

| Output | Description |
|--------|-------------|
| `droplet_ip` | Public IPv4 |
| `health_check_url` | `https://<ip>/health` |
| `ssh_command` | SSH as root |
| `ssh_key_names` | Attached DO SSH key names |
| `ssh_key_fingerprints` | Attached key fingerprints |
| `sync_secrets_command` | Hint for secrets sync |

## CRE integration

Point CRE workflow config at the droplet:

```json
{ "evalRunnerUrl": "https://<droplet_ip>" }
```

Use `-k` or install a real cert (Certbot) for production demos.

## Destroy

```bash
./scripts/terraform-apply-eval-runner.sh destroy
```
