# Eval-runner host runbook (DigitalOcean)

Deploy the GoldenMCP **eval-runner** on a DigitalOcean droplet so Chainlink CRE can call `https://<host>/health`, `/benchmarks`, and (after [GH #23](https://github.com/vhspace/goldenmcp/issues/23)) `/eval/inspect` over HTTPS.

## Architecture

- **Droplet:** `s-4vcpu-8gb` in `nyc3` (4 vCPU, 8 GB RAM)
- **Stack:** Ubuntu 24.04, `uv`, Node.js, nginx TLS `:443` → eval-runner `:8090`
- **Secrets:** post-provision SSH sync to `/etc/goldenmcp/.env` (not in Terraform state)
- **Firewall:** SSH (22) from operator IP only; HTTPS (443) public; **8090 not exposed**

See [infra/terraform/eval-runner/README.md](../infra/terraform/eval-runner/README.md) for Terraform details.

## Prerequisites

1. [DigitalOcean](https://www.digitalocean.com/) account and API token
2. Local `.env` with `DO_API_KEY` (copy from `.env.example`)
3. Terraform `>= 1.14.0`
4. SSH key pair (`~/.ssh/id_ed25519.pub` or set `TF_VAR_ssh_public_key`)
5. Your public IP for firewall SSH allowlist

## One-time setup

```bash
cp .env.example .env
# Edit .env — set DO_API_KEY and eval/MCP secrets

export TF_VAR_allowed_ssh_cidrs='["YOUR_PUBLIC_IP/32"]'
# Optional if key is not ~/.ssh/id_ed25519.pub:
# export TF_VAR_ssh_public_key="$(cat ~/.ssh/id_ed25519.pub)"
```

Find your public IP: `curl -s https://ifconfig.me`

## Provision droplet

```bash
./scripts/terraform-apply-eval-runner.sh plan
./scripts/terraform-apply-eval-runner.sh apply
```

Outputs:

```bash
terraform -chdir=infra/terraform/eval-runner output droplet_ip
terraform -chdir=infra/terraform/eval-runner output health_check_url
```

## Sync application secrets

After apply, copy the filtered `.env` subset to the droplet:

```bash
./scripts/sync-eval-runner-secrets.sh "$(terraform -chdir=infra/terraform/eval-runner output -raw droplet_ip)"
```

This script:

- Uploads only allowlisted keys (LLM, MCP, Walrus, wallet, CAI, etc.)
- **Does not** upload `DO_API_KEY`
- Generates `EVAL_RUNNER_API_KEY` on first run if missing locally
- Sets `EVAL_RUNNER_PUBLIC_URL=https://<ip>` if unset
- Restarts `goldenmcp-eval-runner.service`

Add generated `EVAL_RUNNER_API_KEY` to local `.env` for CRE bearer auth (GH #23).

## Verify

```bash
IP="$(terraform -chdir=infra/terraform/eval-runner output -raw droplet_ip)"
curl -k "https://${IP}/health"
curl -k "https://${IP}/benchmarks"
```

Self-signed TLS on first boot — use `curl -k` or install Let's Encrypt (optional; see Terraform README).

## SSH operations

```bash
ssh root@"$(terraform -chdir=infra/terraform/eval-runner output -raw droplet_ip)"

# Service logs
journalctl -u goldenmcp-eval-runner -f

# Manual Inspect (until CRE HTTP trigger lands)
sudo -u goldenmcp bash -lc 'cd /opt/goldenmcp && uv run python -m goldenmcp_eval_runner'
```

## CRE integration

In `workflows/eval-pipeline/config.staging.json` (follow-up PR):

```json
{
  "evalRunnerUrl": "https://<droplet_ip>",
  "evalRunnerApiKey": "<EVAL_RUNNER_API_KEY>"
}
```

Until GH #23 adds bearer middleware, CRE can only use unauthenticated endpoints (`/health`, `/benchmarks`).

## Phase B pipeline (target)

```
CRE → POST /eval/inspect (score)
    → CAI attest
    → POST /eval/publish (Walrus)
    → Arc write
```

The droplet runs Inspect + npx stdio MCPs; CRE calls HTTP only.

## Destroy

```bash
./scripts/terraform-apply-eval-runner.sh destroy
```

## Troubleshooting

| Symptom | Check |
|---------|--------|
| `502` from nginx | `systemctl status goldenmcp-eval-runner`; secrets synced? |
| SSH refused | `allowed_ssh_cidrs` matches current IP |
| Terraform auth error | `DO_API_KEY` in `.env` |
| Eval fails on MCP | Re-run sync; verify LLM/MCP keys in `/etc/goldenmcp/.env` on droplet |
| TLS errors from CRE | Use real cert or configure CRE client to trust self-signed (dev only) |

## Related issues

- [GH #59](https://github.com/vhspace/goldenmcp/issues/59) — this deploy
- [GH #23](https://github.com/vhspace/goldenmcp/issues/23) — `/eval/inspect` + bearer auth
- [GH #49](https://github.com/vhspace/goldenmcp/issues/49) — CRE pipeline orchestration
