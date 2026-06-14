---
name: terraform-eval-runner-discover
description: >-
  Find the GoldenMCP eval-runner droplet IP and SSH key to use after Terraform
  deploy. Reads local Terraform state/outputs first (no DigitalOcean API). Falls
  back to staging-do config and DO API when state is missing. Use when SSHing to
  the eval-runner, syncing secrets, health checks, CRE staging-do, or asking
  what was deployed by infra/terraform/eval-runner.
---

# Discover eval-runner Terraform deploy

Find **droplet IP** and **which SSH key** to use without calling the DigitalOcean API when local Terraform state exists.

## Quick path (preferred)

From repo root:

```bash
./scripts/terraform-eval-runner-info.sh
./scripts/terraform-eval-runner-info.sh --text
```

JSON fields:

| Field | Meaning |
|-------|---------|
| `source` | `terraform_output`, `terraform_tfstate`, `staging_do_config`, or `digitalocean_api` |
| `droplet_ip` | Public IPv4 |
| `ssh_command` | e.g. `ssh root@<ip>` |
| `ssh_key_names` | DO account key names attached at apply time |
| `ssh_key_fingerprints` | Match against local `~/.ssh/*.pub` |
| `local_ssh_key_hint` | Local private key path when fingerprint matches |

Use the hint for SSH:

```bash
ssh -i "$(./scripts/terraform-eval-runner-info.sh | python3 -c 'import json,sys; print(json.load(sys.stdin).get("local_ssh_key_hint") or "")')" \
  root@"$(./scripts/terraform-eval-runner-info.sh | python3 -c 'import json,sys; print(json.load(sys.stdin)["droplet_ip"])')"
```

Or use `ssh_command` when your default key is already on the droplet.

## Resolution order

1. **`terraform output -json`** — `infra/terraform/eval-runner/terraform.tfstate` on the machine that ran `apply`
2. **Parse `terraform.tfstate`** — same file, no `terraform` CLI required
3. **`workflows/eval-pipeline/config.staging-do.json`** — `evalRunnerUrl` host (IP only; SSH keys unknown)
4. **DigitalOcean API** — last resort; needs `DO_API_KEY` in repo-root `.env`

State is **local and gitignored** (`infra/terraform/eval-runner/terraform.tfstate`). If missing in this checkout, check the operator machine that ran `./scripts/terraform-apply-eval-runner.sh apply`, or use DO API fallback.

## Manual Terraform commands

When the script is unavailable:

```bash
./scripts/terraform-apply-eval-runner.sh output
terraform -chdir=infra/terraform/eval-runner output -raw droplet_ip
terraform -chdir=infra/terraform/eval-runner output ssh_key_names
terraform -chdir=infra/terraform/eval-runner output ssh_command
```

Defined in `infra/terraform/eval-runner/outputs.tf`.

## Match local SSH key to deployed key

```bash
terraform -chdir=infra/terraform/eval-runner output -json ssh_key_fingerprints
ssh-keygen -E md5 -lf ~/.ssh/id_ed25519.pub   # DO uses MD5 fingerprints
```

Attach the matching private key: `ssh -i ~/.ssh/id_ed25519 root@<ip>`

## DigitalOcean API fallback

Use only when Terraform state is absent or stale.

**Requires:** repo-root `.env` with `DO_API_KEY` (same token as Terraform).

List droplets tagged `eval-runner` (default tag from `variables.tf`):

```bash
set -a && source .env && set +a
curl -sf -H "Authorization: Bearer ${DO_API_KEY}" \
  "https://api.digitalocean.com/v2/droplets?tag_name=eval-runner" \
  | python3 -m json.tool
```

Default droplet name: `goldenmcp-eval-runner`.

List account SSH keys (names + fingerprints):

```bash
curl -sf -H "Authorization: Bearer ${DO_API_KEY}" \
  "https://api.digitalocean.com/v2/account/keys" | python3 -m json.tool
```

Or with `doctl`:

```bash
doctl compute droplet list --tag-name eval-runner --format ID,Name,PublicIPv4
doctl compute ssh-key list --format Name,Fingerprint
```

Compare droplet `ssh_keys` IDs/fingerprints to account keys to pick the local key.

## Verify IP is live

```bash
IP="$(./scripts/terraform-eval-runner-info.sh | python3 -c 'import json,sys; print(json.load(sys.stdin)["droplet_ip"])')"
curl -sf "http://${IP}/health"
curl -sk "https://${IP}/health"
```

## Related docs

- `infra/terraform/eval-runner/README.md` — apply/destroy
- `docs/eval-runner-host.md` — sync secrets, CRE `staging-do`
- `./scripts/sync-eval-runner-secrets.sh "$(terraform -chdir=infra/terraform/eval-runner output -raw droplet_ip)"`

## Do not

- Commit `terraform.tfstate`, `terraform.tfvars`, or `.env`
- Assume `config.staging-do.json` IP is current without a health check (may lag reprovision)
- Put secrets in Terraform state; app secrets live in `/etc/goldenmcp/.env` on the droplet
