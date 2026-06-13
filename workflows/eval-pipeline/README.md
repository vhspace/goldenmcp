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
uv run --package goldenmcp-eval-runner eval-runner
```

For faster simulate without Inspect subprocess, set `useScoreOnly: true` in `workflow.yaml` staging-settings (uses `/eval/score` with a minimal transcript fixture).

```bash
cd workflows/eval-pipeline
cre workflow simulate goldenmcp-eval-pipeline --target staging-settings
```

Secrets (via `.env` or environment, see `secrets.yaml`):

- `EVAL_RUNNER_API_KEY_VAR` — bearer token for eval-runner (`EVAL_RUNNER_API_KEY` in eval-runner env)
- `CHAINLINK_CAI_API_KEY_VAR` — optional; omit both CAI URL and key to skip attestation in simulate

Arc writes require `arcRegistryAddress` and CRE `project.yaml` EVM RPC for `arc-testnet`.
