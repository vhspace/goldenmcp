# ENS MCP Identity Skill

Use the ENS CLI to register MCP subnames and set text records after eval runs.

## Prerequisites

- `ens-cli` installed
- Parent name controlled (e.g. `goldenmcp.eth`)
- `ENS_RPC_URL` in `.env`

## Register MCP after eval

```bash
# 1. Create subname
ens-cli create lifi-quote.goldenmcp.eth

# 2. Set ENSIP-26 records
ens-cli set-text lifi-quote.goldenmcp.eth agent-endpoint[mcp] https://mcp.lifi.io
ens-cli set-text lifi-quote.goldenmcp.eth agent-context '{"mcp":"lifi","capability":"quote"}'
ens-cli set-text lifi-quote.goldenmcp.eth goldenmcp/eval-blob walrus://<blobId>

# 3. Set ENSIP-25 agent-registration (ERC-8004 link)
ens-cli set-text lifi-quote.goldenmcp.eth \
  'agent-registration[<registry-erc7930>][<agentId>]' 1
```

## Verify

```bash
ens-cli get-text lifi-quote.goldenmcp.eth agent-endpoint[mcp]
```

Or use the web demo ENS resolver at `/ens`.
