#!/usr/bin/env bash
# Create GoldenMCP GitHub labels and issues #1-#64
set -euo pipefail
cd "$(dirname "$0")/.."
REPO="vhspace/goldenmcp"

create_label() {
  gh label create "$1" --color "$2" --description "$3" -R "$REPO" 2>/dev/null || true
}

echo "Creating labels..."
for epic in infra eval walrus web identity chainlink marketplace; do
  create_label "epic/$epic" "0E8A16" "Epic: $epic"
done
create_label "P0" "B60205" "Priority 0"
create_label "estimate:1h" "FEF2C0" "Estimate 1 hour"
create_label "estimate:2h" "FEF2C0" "Estimate 2 hours"
create_label "estimate:3h" "FEF2C0" "Estimate 3 hours"
create_label "estimate:4h" "FEF2C0" "Estimate 4 hours"

create_issue() {
  local num="$1" title="$2" epic="$3" estimate="$4" skill="$5" acceptance="$6"
  gh issue create -R "$REPO" \
    --title "[#$num] $title" \
    --label "P0,epic/$epic,$estimate" \
    --body "$(cat <<EOF
## Epic
\`epic/$epic\`

## Estimate
\`$estimate\`

## Assignee skill
$skill

## Acceptance tests
$acceptance

## Plan reference
GoldenMCP eval marketplace — issue #$num
EOF
)"
}

echo "Creating issues..."

create_issue 1 "Monorepo + CI skeleton" infra estimate:2h DevOps \
  "\`uv run pytest\` + \`bun test\` in CI; Python 3.12 pinned"

create_issue 2 "Cursor rules (plans, real-code, TDD)" infra estimate:1h Lead \
  "Three \`.mdc\` files committed in \`.cursor/rules/\`"

create_issue 3 "GitHub issue templates + labels" infra estimate:1h Lead \
  "Epics creatable from template; labels epic/* and estimate:* exist"

create_issue 4 "Dev env doc + .env.example" infra estimate:2h Any \
  "README documents \`uv sync\`, Arc/ENS/CRE/Walrus setup (no pip)"

create_issue 10 "Security scorer + composite tests (TDD)" eval estimate:2h Python \
  "Injection/path-violation cases binary-fail; \`uv run pytest packages/inspect-web3/tests/test_scorers.py\`"

create_issue 10b "DataScore + PathScore + TokenEfficiency scorers (TDD)" eval estimate:3h Python \
  "All dimension scorers pass; composite weights 0.45/0.35/0.20"

create_issue 11 "LI.FI MCP connector + quote task" eval estimate:4h Python \
  "Live LI.FI quote eval passes with LIFI_MCP_URL set"

create_issue 12 "0x MCP quote + trade tasks" eval estimate:4h Python \
  "Live 0x evals pass with ZEROX_MCP_URL set"

create_issue 13 "Uniswap MCP quote + swap tasks" eval estimate:4h Python \
  "Live Uniswap evals pass with UNISWAP_MCP_URL set"

create_issue 14 "Golden datasets with expected_path + security allowlists" eval estimate:3h Python \
  "All 9 task runs produce manifests with 3 dimension scores"

create_issue 20 "Walrus client upload test (TDD)" walrus estimate:2h Python \
  "Real blob on Walrus testnet; \`uv run pytest packages/walrus-client/tests/\`"

create_issue 21 "walrus:// fsspec adapter" walrus estimate:4h Python \
  "Inspect writes .eval to Walrus via walrus:// paths"

create_issue 22 "Score manifest schema + upload" walrus estimate:2h Python \
  "Manifest retrievable via Walrus aggregator HTTP API"

create_issue 23 "Post-eval hook → Walrus pipeline" walrus estimate:2h Python \
  "Full eval run end-to-end on Walrus testnet"

create_issue 30 "Leaderboard page (live Arc + Walrus)" web estimate:4h Frontend \
  "Deployed URL shows real scores from Arc registry"

create_issue 31 "Eval report viewer (Walrus blob)" web estimate:3h Frontend \
  "Click MCP → transcript + Data/Path/Token scores; show fail_reason if binary-failed"

create_issue 32 "ENS resolver page" web estimate:3h Frontend \
  "Live ENS lookup at /ens, no hard-coded names"

create_issue 33 "Deploy apps/web to public URL" web estimate:2h DevOps \
  "Public URL documented in README"

create_issue 40 "MCP registry contract + tests (TDD)" identity estimate:4h Solidity \
  "\`forge test -C contracts/mcp-registry\` passes; deployed Arc testnet"

create_issue 41 "Register 3 MCPs with Walrus pointers" identity estimate:2h "Full-stack" \
  "Onchain entries verified for lifi, 0x, uniswap"

create_issue 42 "ENS subnames + ENSIP-25/26 records" identity estimate:3h ENS \
  "Live resolution in web demo"

create_issue 43 "ENS CLI skill for repeatable registration" identity estimate:2h Lead \
  "\`skills/ens-mcp-identity/SKILL.md\` + registration script"

create_issue 50 "Eval-runner HTTP service" chainlink estimate:3h Python \
  "CRE can trigger real Inspect run via POST /eval"

create_issue 51 "CRE workflow: trigger → Walrus read" chainlink estimate:4h TypeScript \
  "\`cre workflow simulate\` passes"

create_issue 52 "CAI attestation integration" chainlink estimate:4h TypeScript \
  "Real Confidential AI sandbox inference recorded"

create_issue 53 "CRE → Arc onchain score write" chainlink estimate:3h TypeScript \
  "Registry updated after workflow run"

create_issue 54 "Attestation badge in web demo" chainlink estimate:2h Frontend \
  "Web demo shows real attestation tx hash"

create_issue 60 "Marketplace MCP server skeleton" marketplace estimate:3h Python \
  "HTTP MCP transport via \`uv run python -m goldenmcp_marketplace\`"

create_issue 61 "lookup tool + tiered pricing" marketplace estimate:3h Python \
  "Real HTTP 402 response with Arc USDC price"

create_issue 62 "x402 payment + settlement on Arc" marketplace estimate:4h "Full-stack" \
  "Real micropayment completes on Arc testnet"

create_issue 63 "Agent demo script (demo/lookup_agent.py)" marketplace estimate:3h Any \
  "Script pays and receives MCP config"

create_issue 64 "Submission docs + demo video" marketplace estimate:4h Lead \
  "ENS/Chainlink/Arc docs in docs/submissions/ + demo script"

echo "Done. Issue list:"
gh issue list -R "$REPO" --limit 50
