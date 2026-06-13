# GoldenMCP

Web3 MCP evaluation marketplace: standardized Inspect evals, Walrus-backed results, ENS identity, Chainlink attestation, and x402 discovery on Arc.

## Bounties

- **ENS** — MCP discovery via ENSIP-25/26
- **Chainlink** — CRE eval orchestration + Confidential AI attestation
- **Arc** — x402 USDC nanopayments for MCP lookup

## Quick start

```bash
# Python 3.12 + uv (no pip)
uv python install 3.12
uv sync --all-packages

# Run unit tests
uv run pytest packages/ -v

# Run eval (requires OPENAI_API_KEY + MCP endpoints in .env)
uv run inspect eval goldenmcp/lifi_quote --model openai/gpt-4o-mini

# Eval runner HTTP service (for CRE)
uv run python -m goldenmcp_eval_runner

# Web demo
cd apps/web && bun install && bun run dev

# Marketplace MCP
uv run python -m goldenmcp_marketplace

# Lookup agent demo (requires Arc wallet + x402)
uv run python demo/lookup_agent.py --capability quote --min-score 0.9
```

Copy `.env.example` to `.env` and fill in credentials.

## Scoring

| Dimension | Weight |
|-----------|--------|
| DataScore | 0.45 |
| PathScore | 0.35 |
| TokenEfficiency | 0.20 |

Binary fail (composite 0.0) on prompt injection, disallowed tools, or policy violations.

See [docs/scoring.md](docs/scoring.md).

## Plans for judges

All implementation plans: [docs/plans/](docs/plans/)

## Agent skills (Chainlink)

Project-local [Chainlink Developer Agent Skills](https://docs.chain.link/resources/chainlink-developer-agent-skills) from `smartcontractkit/chainlink-agent-skills`:

| Path | Agent |
|------|-------|
| `.agents/skills/` | Cursor |
| `.claude/skills/` | Claude Code (this repo) |

Installed skills: CRE, Confidential AI Attester, CCIP, Data Feeds, Data Streams, ACE, VRF. Pin file: `skills-lock.json`.

Invoke explicitly in chat, e.g. `Using /chainlink-cre-skill, …` or `/chainlink-confidential-ai-attester-skill` for CAI attestation work.

Refresh from upstream:

```bash
npx skills add smartcontractkit/chainlink-agent-skills --skill '*' --agent cursor --agent claude-code -y --copy
```

## Structure

```
packages/inspect-web3   Inspect tasks + scorers
packages/walrus-client  walrus:// fsspec + HTTP client
packages/marketplace-mcp  x402 MCP server
packages/identity       ENS + registry SDK
packages/eval-runner    HTTP service for CRE
apps/web                Leaderboard, eval viewer, ENS resolver
workflows/eval-pipeline Chainlink CRE workflow
contracts/mcp-registry  ERC-8004 MCP registry (Arc)
```

## License

MIT
