# ENS MCP Identity Skill

Register an ENSv2 subname per evaluated MCP on **Sepolia** and set its
ENSIP-25/26 records, so `{vendor}-{capability}.goldenmcp.eth` resolves to the
MCP endpoint, eval scores, Walrus pointer, and a link to the Arc ERC-8004
registry. Verify in the web demo at `/ens`.

## Tooling

Use **[gskril/ens-cli](https://github.com/gskril/ens-cli)** (`@ensdomains/cli`),
an agent-native CLI built on viem. It targets **ENSv2 on Sepolia** and is an
experimental preview — pin a commit hash once a flow works.

```sh
alias ens='npx -y "https://pkg.pr.new/gskril/ens-cli/@ensdomains/cli@main"'
export ETH_RPC_URL="$ENS_RPC_URL"   # Sepolia RPC from .env
```

**Read** commands (`get`, `whois`, `available`, `price`) execute directly.
**Write** commands (`register`, `resolver deploy`, `subname create`, `set …`)
DO NOT broadcast — they print unsigned calldata JSON `{to, data, value}`. You
sign + send it yourself with the signer wallet (`MARKETPLACE_WALLET_PRIVATE_KEY`)
via the registration script (`packages/identity/scripts/`), which is the
canonical ENSv2 write pattern (viem `walletClient.writeContract`).

## Costs (Sepolia ENSv2)

`.eth` registration is paid in a **dummy ERC-20 USDC**
(`0x3DfC8b53dAFa5eBbb071a8B97678Ab534Ed838D9`, 6 decimals), NOT ETH. Run
`ens price <name>.eth --chain sepolia` for the exact amount and the registrar
address to approve. The token has open minting — mint to the signer wallet,
`approve` the registrar for `total`, then register. Gas is still paid in
Sepolia ETH, so the signer wallet must hold some.

## Register a parent name (one-time)

```sh
# 1. Deploy the per-account permissioned resolver (idempotent).
ens resolver deploy <wallet> --chain sepolia --json     # → { resolver, alreadyDeployed }

# 2. Check availability + price; mint+approve the test-USDC fee.
ens available goldenmcp.eth --chain sepolia
ens price     goldenmcp.eth --chain sepolia             # → total, registrar, paymentToken

# 3. Commit, wait >=60s, reveal — pass the deployed resolver from step 1.
ens register commit goldenmcp.eth --owner <wallet> --resolver <resolver> --chain sepolia --json
#   ... sign+send commit, save the secret, wait >=60s ...
ens register reveal goldenmcp.eth --owner <wallet> --resolver <resolver> --secret <secret> --chain sepolia --json

# 4. Deploy + wire a UserRegistry subregistry so the parent can own subnames.
ens subregistry deploy goldenmcp.eth --deployer <wallet> --chain sepolia --json   # → alreadySet, factory
#   ... sign+send; read the proxy address from the ProxyDeployed event in the receipt ...
ens subregistry set goldenmcp.eth --registry <proxy> --chain sepolia --json
```

> **Subregistry (ENSv2):** subnames live in a parent `UserRegistry`. The deploy
> calldata does NOT return the proxy address — read it from the `ProxyDeployed`
> event in the deploy receipt (the registration script does this and then calls
> `subregistry set`). A subname's parent must report a non-zero subregistry
> before `subname create` works.

## Register an MCP subname + records (loop per MCP)

```sh
# 4. Create the subname under the parent (owner = signer wallet).
ens subname create lifi-quote.goldenmcp.eth --owner <wallet> --chain sepolia --json

# 5. Set all records in one multicall. agent-context is free-form (JSON here).
ens set batch lifi-quote.goldenmcp.eth --chain sepolia --json --data '[
  {"type":"text","key":"agent-endpoint[mcp]","value":"https://mcp.lifi.io"},
  {"type":"text","key":"agent-context","value":"{\"mcp\":\"lifi\",\"capability\":\"quote\",\"scores\":{...},\"walrusBlobId\":\"...\"}"},
  {"type":"text","key":"goldenmcp/eval-blob","value":"walrus://<blobId>"},
  {"type":"text","key":"agent-registration[<erc7930>][<agentId>]","value":"1"}
]'
```

**ENSIP-25 `agent-registration` key:** `<erc7930>` is the ERC-7930 interoperable
encoding of the Arc registry (chain ID + address), NOT the raw address. For Arc
testnet (chain `5042002`, registry from `.env` `ARC_REGISTRY_ADDRESS`) the
encoding is computed by the registration script and re-derived whenever the
registry address changes. Layout: `0001`(version) `0000`(eip155)
`<chainRefLen><chainRef>` `14`(addrLen) `<20-byte addr>`. `<agentId>` is the
MCP's id in the Arc registry. Value `"1"` per ENSIP-25 (any non-empty string).

## Verify

```sh
ens get text lifi-quote.goldenmcp.eth --key "agent-endpoint[mcp]" --chain sepolia
ens whois    lifi-quote.goldenmcp.eth --chain sepolia    # owner + resolver
```

Or open the web demo at `/ens` and resolve the name — it reads the same records
over Sepolia via the Universal Resolver. The Python `ENSClient`
(`packages/identity`) resolves them the same way.
