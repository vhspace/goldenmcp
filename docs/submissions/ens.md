# ENS Bounty Submission

## Integration

- ENS v2 subnames per MCP: `{vendor}-{capability}.goldenmcp.eth`
- ENSIP-25 `agent-registration[...]` linking to ERC-8004 MCP registry on Arc
- ENSIP-26 `agent-endpoint[mcp]` and `agent-context` with scores + Walrus pointer
- `goldenmcp/eval-blob` text record → `walrus://<blobId>`

## Demo

1. Web demo `/ens` — live resolution, no hard-coded values
2. `skills/ens-mcp-identity/SKILL.md` — repeatable registration workflow

## Code

- `packages/identity/src/goldenmcp_identity/registry.py` — ENSClient
- `apps/web/src/app/ens/page.tsx` — resolver UI
