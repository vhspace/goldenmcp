# DO staging-do CRE handoff — blockers and state

**Date:** 2026-06-13  
**Branch:** `feat/do-staging-http` (1 commit ahead of `origin/main`)  
**Commit:** `be92d8e` — *Expose eval-runner over HTTP on DO for staging-do CRE runs.*  
**Droplet IP:** `165.227.74.149` (reprovisioned after destroy of `159.203.78.85`)  
**Worktree:** `.worktrees/feat/do-staging-http`

---

## Goal

1. Commit Terraform/nginx/staging-do config fixes to a branch.
2. Rebase from `main`.
3. Run full CRE workflow simulate: **inspect → Walrus publish** via `staging-do` target (CAI/Arc skipped).

---

## Completed successfully

| Item | Status |
|------|--------|
| Branch `feat/do-staging-http` created/reused | Done |
| Rebase onto latest `origin/main` (includes PR #77 in-process Inspect, PR #78 CAI wiring) | Done |
| Commit with 3 files (see below) | Done |
| DO droplet health after secrets sync | `GET /health` → 200 |
| **First** live `POST /eval/inspect` on droplet | Scored in ~31s, composite **0.2** |
| Mac-local in-process Inspect + unit tests | Passed in prior session |

### Committed changes (`be92d8e`)

1. **`infra/terraform/eval-runner/main.tf`** — firewall inbound TCP **80** (same CIDRs as 443).
2. **`infra/terraform/eval-runner/cloud-init.yaml.tftpl`** — nginx **:80** server block (plain HTTP proxy to 8090), in addition to existing :443 self-signed block.
3. **`workflows/eval-pipeline/config.staging-do.json`** — `evalRunnerUrl` → `http://165.227.74.149`.

**Not committed:** `infra/terraform/eval-runner/terraform.tfstate` (local state from apply; gitignored).  
**Not pushed:** branch is local only unless pushed since this doc was written.

---

## Blockers (need advanced model / follow-up)

### 1. CRE `staging-do` simulate failed — 5-minute simulator timeout

**Command used (from worktree root):**

```bash
set -a && source /path/to/repo/.env && set +a
export EVAL_RUNNER_API_KEY_VAR="$EVAL_RUNNER_API_KEY"
export CHAINLINK_CAI_API_KEY_VAR="$CHAINLINK_CAI_API_KEY"   # required even when CAI URL empty
cd .worktrees/feat/do-staging-http/workflows/eval-pipeline && bun install
cd .worktrees/feat/do-staging-http
cre workflow simulate ./workflows/eval-pipeline -T staging-do --limits none --skip-type-checks -R .
```

**Observed behavior:**

- Workflow compiles and runs cron trigger.
- `POST /eval/inspect` accepted (`run_id=4d7a125f-eba5-497d-9610-a74303d4d230`).
- CRE polls `GET /eval/runs/{id}` every ~2s; status stays **`running`** for 142+ attempts (~5 min).
- Simulator exits: **`Timeout waiting for execution to finish`** (~5 min wall clock from trigger start).
- Final error: `Error converting from 'Error' into js 'now() returned non-zero status'`.

**Notes:**

- README documents `--timeout 900s` but **installed CRE CLI does not accept `--timeout`** on `cre workflow simulate` (unknown flag).
- No documented env var found to extend simulation timeout.
- `pollBusyWait: true` in `config.staging-do.json` — busy-wait used because `runtime.sleep` traps in simulate (by design).
- `inspectPollMaxAttempts: 300` × 2s ≈ 10 min poll budget in workflow, but CRE simulator killed the run at ~5 min.

**Hypothesis:** CRE engine hard-caps simulate duration; either increase that cap (CLI/config TBD) or ensure inspect completes well under 5 min.

---

### 2. Eval-runner on DO: inspect hangs after the first successful run

**Symptoms:**

| Run | run_id | Started (UTC) | Result |
|-----|--------|---------------|--------|
| 1 | `617d896a-c149-4f7a-a12a-e3110a78a0c5` | 21:16:57 | **scored** ~31s, composite 0.2 |
| 2 | `4d7a125f-eba5-497d-9610-a74303d4d230` | 21:29:23 | **running** indefinitely (CRE timed out) |
| 3 | `54adbece-f70d-4cd7-b92e-13f402a39fc6` | 21:35:17 | **running** after 60×2s polls (~120s+) post-restart |

**Log evidence (droplet `/var/log/syslog`):**

- Run 1: full log trail — `background in-process inspect` → `in-process inspect eval task=lifi_quote` → completed.
- Run 2: only `POST /eval/inspect 202` and poll lines — **no** `eval/inspect queued` / `background in-process inspect` lines (possible logging race or code path anomaly).
- Run 3 (after `systemctl restart goldenmcp-eval-runner`): normal `background in-process inspect` + `in-process inspect eval` lines, then **no completion** for 2+ minutes.

**Partial Inspect log files on droplet:**

```
/opt/goldenmcp/logs/
  2026-06-13T21-17-00-00-00_lifi-quote_....eval   21161 bytes  ← success
  2026-06-13T21-29-23-00-00_lifi-quote_....eval    1262 bytes  ← stuck (journal only)
  2026-06-13T21-35-19-00-00_lifi-quote_....eval    1269 bytes  ← stuck (journal only)
```

Small `.eval` zip files contain only `_journal/start.json` — eval never progressed past startup.

**Manual repro on droplet (also failed quickly / hung):**

```bash
# /tmp/test_inspect.py calls run_inspect_eval() in-process
sudo -u goldenmcp bash -lc 'cd /opt/goldenmcp && uv run python /tmp/test_inspect.py'
# Prints start log line only; exits ~6s with code 1, no "OK" print, no traceback
```

**Service / env on droplet:**

- `systemctl status goldenmcp-eval-runner` — active, single uvicorn process.
- Secrets at `/etc/goldenmcp/.env` (synced via `scripts/sync-eval-runner-secrets.sh`) — includes `TOGETHER_API_KEY`, `LIFI_MCP_URL`, `EVAL_RUNNER_API_KEY`, etc.
- Droplet code: cloned at cloud-init from **`main`** at provision time — **does not include** `feat/do-staging-http` nginx/firewall commit unless reprovisioned or `git pull` on box.
- `cloud-init status` was **error** on fresh provision (service failed until secrets sync) — expected.

**Leading hypotheses (unverified):**

1. **LiFi MCP or Together API** — second concurrent or back-to-back call hangs (rate limit, connection pool, DNS). First call succeeds.
2. **inspect-ai in-process inside uvicorn worker thread** — GIL / event-loop / MCP client lifecycle: first eval completes but leaves state that blocks subsequent `inspect_ai.eval()` calls in the same process.
3. **Resource leak** — MCP subprocess or HTTP client not torn down after run 1.
4. **Silent failure** — exception swallowed or process killed without updating job status to `failed` (job stays `running` until 600s `eval_inspect_timeout`).

**Relevant code paths:**

- `packages/eval-runner/src/goldenmcp_eval_runner/app.py` — `_run_inspect_job()` spawns `threading.Thread` per request; uses `ThreadPoolExecutor(max_workers=1)` + `future.result(timeout=600)`.
- `packages/eval-runner/src/goldenmcp_eval_runner/inspect_runner.py` — `inspect_ai.eval(tasks="lifi_quote", ...)`.
- Model on droplet: `together/google/gemma-4-31B-it` (from settings default).

---

### 3. CRE secrets.yaml requires CAI key even when staging-do skips CAI

After PR #78, `workflows/eval-pipeline/secrets.yaml` maps:

```yaml
secretsNames:
  EVAL_RUNNER_API_KEY:
    - EVAL_RUNNER_API_KEY_VAR
  CHAINLINK_CAI_API_KEY:
    - CHAINLINK_CAI_API_KEY_VAR
```

`config.staging-do.json` has `"chainlinkCaiUrl": ""` — pipeline skips CAI at runtime, but **CRE simulate still fails** unless `CHAINLINK_CAI_API_KEY_VAR` is exported:

```
failed to replace secret names with environment variables: environment variable CHAINLINK_CAI_API_KEY_VAR for secret value not found
```

**Workaround:** export dummy or real key from `.env` before simulate.  
**Possible fix:** separate `secrets.yaml` for staging-do, or make CAI secret optional in CRE config when URL empty.

---

### 4. Terraform / cloud-init drift on live droplet

| Issue | Repo state | Live droplet |
|-------|------------|--------------|
| nginx :80 | Fixed in `feat/do-staging-http` cloud-init | Manually patched via SSH during prior session; HTTP works |
| Firewall :80 | Fixed in branch `main.tf` (applied from main checkout) | Applied |
| cloud-init error on boot | Service starts before secrets | Expected until `sync-eval-runner-secrets.sh` |
| Droplet app code | `/opt/goldenmcp` at provision-time `main` | No auto-deploy on merge; needs `git pull` + `uv sync` + restart |

---

### 5. Minor / tooling

- **`cre workflow simulate --timeout 900s`** — documented in README but **not supported** by current CRE CLI.
- **`bun install`** required in `workflows/eval-pipeline/` before first simulate (`cre-compile` not found otherwise).
- Main checkout had stash `stash@{0}: do-staging-http` (duplicate of committed work); can drop after verifying branch.
- Stuck runs remain **`running`** in eval-runner in-memory job store until service restart or 600s timeout — no persistence across restart (jobs lost on restart).

---

## CRE staging-do intended path

```
cron → GET /benchmarks → filter lifi/quote
     → POST /eval/inspect (async)
     → poll GET /eval/runs/{id} until scored
     → skip CAI (empty chainlinkCaiUrl)
     → POST /eval/publish → Walrus
     → skip Arc (empty arcRegistryAddress)
```

Config: `workflows/eval-pipeline/config.staging-do.json`  
Secrets: `workflows/eval-pipeline/secrets.yaml` + repo root `.env`

---

## Reproduction checklist

```bash
# 1. Branch / worktree
cd .worktrees/feat/do-staging-http
git log -1 --oneline   # be92d8e

# 2. Droplet health
source .env  # from repo root
curl -sf http://165.227.74.149/health
curl -sf -H "Authorization: Bearer $EVAL_RUNNER_API_KEY" \
  -X POST -H "Content-Type: application/json" \
  -d '{"mcp":"lifi","capability":"quote"}' \
  http://165.227.74.149/eval/inspect

# 3. Poll until scored (watch for hang on 2nd consecutive call)
curl -sf -H "Authorization: Bearer $EVAL_RUNNER_API_KEY" \
  http://165.227.74.149/eval/runs/<run_id>

# 4. CRE full workflow
cd workflows/eval-pipeline && bun install && cd ../..
export EVAL_RUNNER_API_KEY_VAR="$EVAL_RUNNER_API_KEY"
export CHAINLINK_CAI_API_KEY_VAR="$CHAINLINK_CAI_API_KEY"
cre workflow simulate ./workflows/eval-pipeline -T staging-do --limits none --skip-type-checks -R .

# 5. Droplet logs
ssh root@165.227.74.149 'grep -E "background in-process|inspect eval|timed out|failed" /var/log/syslog | tail -30'
ssh root@165.227.74.149 'ls -la /opt/goldenmcp/logs/'
```

---

## Suggested next steps for advanced model

1. **Root-cause the inspect hang** — run `inspect_ai.eval()` twice in same Python process on DO (and locally) with verbose logging; inspect LiFi MCP connectivity between runs; check for zombie MCP child processes (`ps auxf`).
2. **Fail loudly** — if inspect stalls, ensure job transitions to `failed` with error text (and consider process-level isolation: subprocess or worker restart per eval).
3. **CRE simulate timeout** — find CRE 1.x knob for simulation wall clock (CLI flag, env, or limits JSON); align with `inspectPollMaxAttempts` budget.
4. **Optional secrets** — staging-do should not require CAI key when URL empty.
5. **Deploy pipeline** — after merge, reprovision or add `git pull && uv sync && systemctl restart` to droplet update script so code matches `main`.
6. **Push branch + open PR** — `feat/do-staging-http` ready for review once E2E passes.
7. **GH #73** — stable DNS + trusted TLS for production CRE HTTPS (out of scope for this handoff).

---

## Related PRs / context

- **#76** — DO eval-runner deploy, cloud-init, SSH workflow (merged).
- **#77** — In-process `inspect_ai.eval()`, log slug fixes, CRE staging-do, pollBusyWait (merged).
- **#78** — CAI attestation wiring + `CHAINLINK_CAI_API_KEY` in secrets.yaml (merged).

Prior Mac verification: direct `run_inspect_eval` ~25s; `POST /eval/inspect` → scored ~31–52s; 33 unit tests passed.
