# Chainlink Bounty Submission

## Integration

- CRE workflow in `workflows/eval-pipeline/` orchestrates eval → Walrus read → CAI attestation → Arc write
- Triggers: Cron + HTTP (via eval-runner)
- Integrates blockchain (Arc), external API (eval-runner, Walrus), LLM (Confidential AI Attester)

## Demo

```bash
cd workflows/eval-pipeline
cre workflow simulate goldenmcp-eval-pipeline --target staging-settings
```

Requires `CHAINLINK_CAI_API_KEY` for full CAI attestation path.

## Code

- `workflows/eval-pipeline/src/workflow.ts`
- `packages/eval-runner/` — HTTP service CRE calls
