# ENS bounty submission

## Bounty fit

GoldenMCP uses ENS as the public identity and discovery layer for evaluated MCP servers. Each evaluated MCP/capability pair can publish text records that point agents to the MCP endpoint, Walrus evidence, and Arc registry state.

## Integration summary

- ENS v2 subnames per MCP: `{vendor}-{capability}.goldenmcp.eth`.
- ENSIP-25-style `agent-registration[...]` record links the name to the Arc MCP registry entry.
- ENSIP-26-style `agent-endpoint[mcp]` and `agent-context` records expose the MCP endpoint plus score context.
- `goldenmcp/eval-blob` text record points to the Walrus score/eval artifact (`walrus://<blobId>`).
- Resolution is live; the frontend and identity package do not rely on hard-coded demo names.

## Demo checklist

| Check | Evidence |
| --- | --- |
| Resolve ENS text records from code | `packages/identity/src/goldenmcp_identity/registry.py` (`resolve_text`, `resolve_agent_context`, `resolve_eval_blob`, `resolve_mcp_endpoint`) |
| Register/lookup SDK includes ENS name | `packages/identity/` registry SDK and tests |
| Web UI can resolve ENS records | `apps/web/src/app/ens/page.tsx`, `apps/web/src/app/api/ens/route.ts` |
| Eval artifacts are discoverable from ENS | `goldenmcp/eval-blob` convention points at Walrus artifacts |

## ENS booth prep checklist

Use this checklist for the ENS booth or judge walkthrough:

1. Open the GoldenMCP README and explain that ENS names are the user-facing identity for scored MCPs.
2. Show the resolver implementation in `packages/identity/src/goldenmcp_identity/registry.py`.
3. Open the `/ens` page and enter a configured MCP ENS name.
4. Confirm the UI displays endpoint, context, registry, and Walrus pointer fields.
5. Follow the Walrus pointer to the eval evidence, if live credentials/data are available.
6. Explain how another MCP can be added by registering a new ENS subname and updating its text records.

## Code references

- `packages/identity/src/goldenmcp_identity/registry.py` — ENS client and resolver helpers.
- `packages/identity/tests/test_registry.py` — registry/identity tests.
- `apps/web/src/app/ens/page.tsx` — resolver UI.
- `apps/web/src/app/api/ens/route.ts` — frontend API route.
- `skills/ens-mcp-identity/SKILL.md` — repeatable registration workflow.
