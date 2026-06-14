# Registering a new MCP

GoldenMCP evaluates each MCP server's capabilities, has two open-weight models
judge the results in a Chainlink Confidential AI (CAI) TEE, and records the
attested scores on the Arc `MCPRegistry`. To add a new MCP to the eval set you
do two things: add its **golden benchmarks** and **register it on-chain**. The
running pipeline picks it up automatically — no workflow code change.

## 1. Add golden benchmark(s)

Each `mcp/capability` pair is a YAML golden under:

```
benchmarks/golden/<mcp>/<capability>.yaml
```

e.g. `benchmarks/golden/lifi/quote.yaml`. The `<mcp>` directory name is the MCP's
canonical name — it must match the name you register on-chain (step 2) and the
connector key in `packages/inspect-web3/src/goldenmcp_inspect/mcp_connectors.py`.

A golden defines the task's expected data, allowed tools, and security policy
(see existing files for the schema, and `docs/scoring.md` for how they score).
The eval-runner discovers benchmarks by scanning this directory
(`list_benchmarks()` — sorted, so ordering is stable), so a new file is live as
soon as it's on the eval-runner host.

Wire the MCP's transport/endpoint in `mcp_connectors.py` (HTTP/SSE URL via an
env var, or an `npx`/stdio launch) so the eval can actually call it.

## 2. Register the MCP on Arc

The registry maps an MCP **name → agent id** (`nameToAgentId`). The eval pipeline
resolves a benchmark's MCP name to its agent id at run time, so registration is
all that's needed to route that MCP's scores to its own agent.

Use the idempotent helper (skips any name already registered):

```bash
./scripts/register-mcps.sh
```

It reads `MARKETPLACE_WALLET_PRIVATE_KEY`, `ARC_RPC_URL`, and
`ARC_REGISTRY_ADDRESS` from the repo-root `.env` and calls `register(name,
mcpEndpoint, agentUri, ensName)` for each MCP in its list. To add a brand-new
MCP, append a `name|endpoint|agentUri|ensName` row to the `MCPS=( … )` array and
re-run — existing entries are skipped. (`endpoint`/`agentUri`/`ensName` are
descriptive metadata; the eval uses the connector, not these strings.)

Or register one manually:

```bash
cast send "$ARC_REGISTRY_ADDRESS" \
  "register(string,string,string,string)" \
  "mymcp" "https://my.mcp/endpoint" "walrus://goldenmcp/mymcp" "mymcp.goldenmcp.eth" \
  --private-key "$MARKETPLACE_WALLET_PRIVATE_KEY" --rpc-url "$ARC_RPC_URL"
```

Verify the agent id:

```bash
cast call "$ARC_REGISTRY_ADDRESS" "nameToAgentId(string)(uint256)" "mymcp" --rpc-url "$ARC_RPC_URL"
```

Currently registered: `lifi`=1, `1inch`=2, `odos`=3, `jupiter`=4, `kyberswap`=5.

## 3. How it flows at run time

- The eval-runner's `GET /benchmarks/next` rotates over `(benchmark × model)`
  pairs and resolves each MCP's `agent_id` via `nameToAgentId` (best-effort; `0`
  falls back to the workflow's `defaultAgentId`).
- Each CRE cron fire scores one `(benchmark, model)`; the two open-weight models
  for a benchmark are paired (`/eval/pair`) and submitted to one CAI judge.
- Handler B resolves the agent id from the run's MCP (`GET /agent-id?mcp=…`) and
  writes the attestation + score to that agent on Arc, with the manifest on
  Walrus.

So after registering, the MCP's benchmarks simply join the rotation and start
producing attested on-chain scores under their own agent id.
