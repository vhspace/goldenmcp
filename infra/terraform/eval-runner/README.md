# GoldenMCP eval-runner — DigitalOcean Terraform

Provisions an **8 GB RAM** droplet in `nyc3` for the Inspect eval-runner HTTP service ([GH #59](https://github.com/vhspace/goldenmcp/issues/59)).

## Prerequisites

- Terraform `>= 1.14.0` (latest recommended: 1.15.x)
- `DO_API_KEY` in repo-root `.env` (never commit)
- SSH key pair for operator access
- Your public IP for `allowed_ssh_cidrs`

## Quick start

From repo root:

```bash
# Plan + apply (exports DIGITALOCEAN_TOKEN from DO_API_KEY)
./scripts/terraform-apply-eval-runner.sh plan
./scripts/terraform-apply-eval-runner.sh apply

# Upload application secrets (LLM keys, MCP URLs, Walrus, wallet)
./scripts/sync-eval-runner-secrets.sh "$(terraform -chdir=infra/terraform/eval-runner output -raw droplet_ip)"

# Health check (self-signed TLS — use -k)
curl -k "https://$(terraform -chdir=infra/terraform/eval-runner output -raw droplet_ip)/health"
```

## Secrets

- **Terraform / DO API:** `DO_API_KEY` in local `.env` only
- **Application secrets:** copied post-apply via `sync-eval-runner-secrets.sh` to `/etc/goldenmcp/.env` (mode 600). Not stored in Terraform state or cloud-init.

DigitalOcean Droplets do not have a native secrets vault (unlike App Platform encrypted env vars). Do not put LLM or wallet keys in `terraform.tfvars` or cloud-init.

## Configuration

Copy `terraform.tfvars.example` to `terraform.tfvars` and set `allowed_ssh_cidrs`.

Alternatively pass variables:

```bash
export TF_VAR_ssh_public_key="$(cat ~/.ssh/id_ed25519.pub)"
export TF_VAR_allowed_ssh_cidrs='["203.0.113.10/32"]'
```

## Outputs

| Output | Description |
|--------|-------------|
| `droplet_ip` | Public IPv4 |
| `health_check_url` | `https://<ip>/health` |
| `ssh_command` | SSH as root |
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
