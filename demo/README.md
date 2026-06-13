# GoldenMCP demo runbook

This directory contains the judge-facing local demo for GoldenMCP.

## What the demo proves

The demo is intended to prove that a judge can run the repository end-to-end far enough to validate the submitted bounty packet:

1. Python package tests for Inspect scoring and Walrus storage paths.
2. Solidity registry tests for the Arc MCP registry.
3. Web tests for the frontend data/scoring layer.
4. Service startup commands for the eval runner and x402 marketplace MCP.
5. The lookup-agent command that exercises the paid MCP discovery flow when Arc/x402 credentials are available.

## Prerequisites

- Python 3.12 and `uv`
- `bun`
- Foundry (`forge`)
- Optional for live external flows: `.env` with LLM, Walrus, Chainlink CAI, Arc registry/wallet, and x402 payment settings.

## Quick smoke run

From the repository root:

```bash
./demo/run_demo.sh
```

The script runs local tests first and then prints the service commands that require credentials or long-running processes.

## Manual run order

### 1. Install dependencies

```bash
uv sync --all-packages
cd apps/web && bun install && cd ../..
```

### 2. Run local verification

```bash
uv run pytest packages/inspect-web3/tests packages/walrus-client/tests -v
forge test -C contracts/mcp-registry
cd apps/web && bun test && cd ../..
```

### 3. Start backend services

Open two terminals:

```bash
uv run python -m goldenmcp_eval_runner
```

```bash
uv run python -m goldenmcp_marketplace
```

### 4. Start frontend

```bash
cd apps/web
bun run dev
```

Open the local web URL printed by Next.js and inspect the leaderboard/eval pages plus the ENS resolver page.

### 5. Run x402 lookup agent

When Arc/x402 credentials are configured:

```bash
uv run python demo/lookup_agent.py --capability quote --min-score 0.9
```

Expected flow:

1. the marketplace returns an HTTP 402 payment challenge;
2. the agent prepares or submits payment proof through the configured x402/Arc rail;
3. the agent retries the lookup; and
4. the marketplace returns ranked MCP endpoint(s) whose score evidence maps to registry and Walrus data.

## Notes for judges

- Local test steps do not require private keys or funded wallets.
- Live payment and onchain write steps require external credentials and should be run only in an appropriately funded test environment.
- The bounty submission packet lives in [`../docs/submissions/`](../docs/submissions/).
