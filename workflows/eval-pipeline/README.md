# GoldenMCP eval pipeline (CRE)

Orchestrates eval-runner scoring, Chainlink Confidential AI attestation, Walrus publish, and optional Arc registry writes.

## Pipeline order

```
eval-runner score/inspect → CAI attest → Walrus publish → Arc registry write
```

Shared entry point: `runPipeline(runtime, { mcp, capability, agentId? })` in `src/pipeline.ts`.

## Local tests

```bash
cd workflows/eval-pipeline
bun test
```

## Simulate

Start eval-runner (from repo root):

```bash
EVAL_RUNNER_API_KEY=dev-key uv run --package goldenmcp-eval-runner eval-runner
```

Use the **`staging-simulate`** target (CAI skipped by default, `useScoreOnly` + `lifi/quote` only):

```bash
cd workflows/eval-pipeline
export EVAL_RUNNER_API_KEY_VAR=dev-key
cre workflow simulate goldenmcp-eval-pipeline --target staging-simulate
```

For full pipeline including CAI, use **`staging-settings`** and set both:

- `chainlinkCaiUrl` (already set in yaml)
- `CHAINLINK_CAI_API_KEY_VAR` in environment / secrets

Remote DigitalOcean eval-runner (real Inspect on `lifi/quote`, CAI/Arc skipped):

```bash
./scripts/sync-eval-runner-secrets.sh <droplet_ip>
export EVAL_RUNNER_API_KEY_VAR="$EVAL_RUNNER_API_KEY"   # from sync output or .env
cre workflow simulate eval-pipeline --target staging-do --timeout 900s --limits none
```

Run `cre workflow simulate` from the repo root (directory containing `project.yaml`).

Secrets (see `secrets.yaml`):

- `EVAL_RUNNER_API_KEY_VAR` — bearer token for eval-runner
- `CHAINLINK_CAI_API_KEY_VAR` — required when `chainlinkCaiUrl` is non-empty

`useScoreOnly` uses a minimal transcript fixture that only scores **`lifi/quote`** meaningfully. Set `benchmarkAllowlist` when using score-only mode.

Arc writes require `arcRegistryAddress` and CRE `project.yaml` EVM RPC for `arc-testnet`.
