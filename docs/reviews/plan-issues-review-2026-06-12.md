All the material needed is in the bundle, so here is the review directly.

## Executive summary

Plan and issue tracker are structurally healthy: all 32 planned work items exist as open GitHub issues with correct epic labels, estimates, and plan back-references, and every epic has full nominal coverage. The two systemic weaknesses are (1) a pervasive plan-ID ↔ GitHub-number mismatch (e.g. plan #14 is GH #10 while GH #14 is plan #23) that will cause cross-referencing errors under hackathon pressure, and (2) no `blocked-by` relationships populated anywhere despite the plan's own issue template mandating them — so the critical path, the CAI-key blocker, and the ENS booth deadline exist only in the plan prose, not in the tracker.

## Plan ↔ issues alignment

Mapping (plan ID → GH issue):

| Epic | Plan IDs | GH issues |
|------|----------|-----------|
| infra | #1–#4 | GH #1–#4 (aligned 1:1) |
| eval | #10, #10b, #11, #12, #13, #14 | GH #5, #6, #7, #8, #9, #10 |
| walrus | #20–#23 | GH #11–#14 |
| web | #30–#33 | GH #15–#18 |
| identity | #40–#43 | GH #19–#22 |
| chainlink | #50–#54 | GH #23–#27 |
| marketplace | #60–#64 | GH #28–#32 |

- **No orphan GitHub issues** — all 32 trace to a plan ID via title prefix and "Plan reference" field. **No missing plan items** at the issue level — all 32 plan rows exist.
- **Numbering mismatch is total beyond #4.** Worst collisions: GH #10 = plan #14 but plan #10 = GH #5; GH #14 (Walrus hook) = plan #23 but plan #14 (golden datasets) = GH #10; GH #30 (x402 settlement) = plan #62 but plan #30 (leaderboard) = GH #15; GH #20–#22 are identity issues while plan #20–#22 are Walrus issues. The plan's "Create all issues #1–#64" and parallelism notes ("#11–#13, #30–#32 parallelizable") are now ambiguous — those numbers mean different issues in the two systems.
- **Plan items with no issue coverage:** submission doc *templates* at Phase 0 (`docs/submissions/{ens,chainlink,arc,sui-walrus-reserve}.md` — Friday PM per plan, but only GH #32 at Phase 6 touches submissions, and its acceptance omits the Sui reserve doc); `docs/architecture.md` + `docs/scoring.md`; architecture diagram (listed in the demo-submit todo, absent from GH #32 acceptance); ENS booth prep (hard Sunday AM deadline, tracked nowhere); marketplace tools `list_capabilities`, `get_scores`, `register_mcp` (only `lookup` has an issue); cron + HTTP trigger wiring for CRE (GH #24 covers trigger→Walrus read generically); golden dataset snapshots stored on Walrus (plan's "what gets stored" list).

## Epic coverage

| Epic | Status | Notes |
|------|--------|-------|
| infra | **Complete** (GH #1–#4) | Gap: no issue for Phase-0 submission templates / docs scaffold |
| eval | **Complete** (GH #5–#10) | Ordering wrinkle: GH #10's acceptance ("manifests with 3 dimension scores") depends on the manifest schema defined in walrus epic GH #13 |
| walrus | **Complete** (GH #11–#14) | Strongest epic; clean TDD ladder. Golden-snapshot storage uncovered |
| web | **Complete** (GH #15–#18) | Plan's "MCP detail" page is not clearly owned — implicitly split across GH #15/#16 |
| identity | **Complete** (GH #19–#22) | ERC-8004 Validation Registry (plan mentions it for attestation verification) not explicit in GH #19 scope |
| chainlink | **Complete** (GH #23–#27) | CAI key risk (plan's top risk) not encoded as a blocker on GH #25 |
| marketplace | **Partial** | GH #28–#32 cover skeleton/lookup/payment/demo/docs, but 3 of 4 planned MCP tools have no issue; tiered-pricing *demo* (0.5 vs 0.9 price difference) untested |

## Bounty traceability

- **ENS ($2.5k, P0):** GH #21 (subnames + ENSIP-25/26), GH #20 (registry entries the records point at), GH #17 (live resolver page), GH #22 (registration skill), GH #32 (submission doc). **Gaps:** the bounty's "functional demo, no hard-coded values" criterion lives only in GH #17; ENSIP-25 `agent-registration` correctness is not independently testable in any acceptance; the Sunday-AM booth deadline has no issue or milestone.
- **Chainlink CRE + CAI ($2k+$2k):** GH #23 (eval-runner the workflow calls), GH #24 (`cre workflow simulate` with real capabilities), GH #25 (real CAI sandbox inference), GH #26 (EVM write on Arc), GH #27 (attestation surfaced). This is the best-traced bounty. **Gaps:** GH #24's acceptance doesn't forbid CRE capability mocks (plan explicitly requires real HTTP/EVM in simulate); the "blocked until key" status for GH #25 isn't recorded on the issue.
- **Arc x402 ($2.25k):** GH #19 (ERC-8004 registry *deployed on Arc* — explicit bounty requirement), GH #28–#31 (marketplace, 402 pricing, USDC settlement, autonomous agent), GH #26 (onchain score writes). **Gaps:** bounty criterion "gas-free micro-settlement, not a single large transfer" — GH #30's acceptance says "real micropayment completes" (singular); "agents autonomously pay tiered fees" — no acceptance verifies the 0.9-costs-more-than-0.5 behavior.
- **Main track:** working end-to-end is covered by the union of epics; web demo by GH #15–#18; video/docs by GH #32. **Gaps:** architecture diagram and the full 7-step judge demo script (including step 7, agent connects to returned MCP and executes a quote) are not in any acceptance test.
- **Walrus/Sui reserve:** GH #11–#14 fully satisfy the integration ("real blob on testnet" through "full eval run end-to-end"). **Gap:** the pre-written `sui-walrus-reserve.md` submission doc — the entire point of the reserve strategy — is absent from GH #32's acceptance, which lists only ENS/Chainlink/Arc.

## Sequencing and dependencies

- **Critical path:** GH #1 → GH #5/#6 (scorers) → GH #7 (first live eval) → GH #11–#14 (Walrus) → GH #15/#16 (web) → GH #19/#20/#21 (identity) → GH #23–#26 (CRE) → GH #28–#31 (marketplace) → GH #32. Walrus is the spine: web, identity pointers, CRE reads, and the marketplace index all consume Walrus manifests, so GH #13/#14 slipping slips four epics.
- **No `blocked-by` fields are populated on any issue**, despite the plan's issue template requiring them and the plan's phase-gate rule ("do not start Phase N+1 until Phase N acceptance tests pass"). The tracker currently shows 32 equally-pickable P0 issues.
- **Env prerequisites:** GH #4 (`.env.example`) gates everything downstream — eval acceptance tests reference `LIFI_MCP_URL`/`ZEROX_MCP_URL`/`UNISWAP_MCP_URL`, and Arc/ENS/CRE/Walrus keys are needed by phases 2–6. It should be done Friday PM alongside GH #1.
- **External blockers** (per plan risk table, none reflected on issues): CAI sandbox key (GH #25), live MCP availability (GH #7–#9), Walrus testnet stability (GH #11–#14), Circle Gateway setup friction (GH #30 — plan says "escalate early").
- **Deadlines:** ENS booth Sunday AM means GH #21 and GH #17 must land Saturday PM, yet they sit in Phases 4 and 3 with no milestone. GH #27 (badge) needs GH #25+#26 first, compressing Sunday AM further.

## Acceptance test quality

The weakest criteria, with suggested fixes:

- **GH #32:** "ENS/Chainlink/Arc docs + demo script" — omits the 3-min video (in the plan's table), the Sui reserve doc, the architecture diagram, and booth prep. Fix: enumerate all five artifacts plus "judge can run `demo/` end-to-end from README."
- **GH #20:** "Onchain entries verified" — verified how? Fix: "each of lifi/0x/uniswap readable via `cast call` on Arc testnet with a `walrusBlobId` that resolves via the aggregator."
- **GH #21:** "Live resolution in web demo" — couples identity to web epic and doesn't name the records. Fix: "ENSIP-25 `agent-registration`, ENSIP-26 `agent-endpoint[mcp]`/`agent-context`, and `goldenmcp/eval-blob` resolvable via ens-cli/viem for all 3 names" — web rendering stays in GH #17.
- **GH #27:** "shows real attestation tx hash" — fix: "hash links to Arc explorer and matches the registry's stored attestation for that MCP."
- **GH #24:** "`cre workflow simulate` passes" — passes how? Fix: "simulate runs against the live eval-runner (GH #23) and a real Walrus aggregator read; no CRE capability mocks in the workflow path" (this is the plan's own rule).
- **GH #23:** should require the response to return the Walrus blob ID, since CRE step 3 depends on it.
- **GH #29:** "Real 402 with Arc USDC price" — fix: assert the price formula, e.g. "price for `min_score=0.9` > price for `0.5`, matching `base * (1 + 4 * min_score)`."
- **GH #30:** "Real micropayment completes" — doesn't demonstrate the bounty's *nano*payment claim. Fix: "≥2 distinct sub-cent USDC settlements on Arc testnet with tx hashes, not one aggregated transfer."
- **GH #31:** stops at "receives MCP config" — the plan's demo step 7 has the agent connect and execute a quote. Fix: add that final step.
- **GH #15:** "shows real scores from Arc registry" — plan says leaderboard merges Arc registry *and* Walrus manifests. Fix: name both sources and require binary-failed MCPs to render `composite: 0.0` with `fail_reason`.
- **GH #10:** "9 task runs produce manifests" presumes a manifest schema defined later in GH #13. Fix: scope GH #10 to "9 runs produce `.eval` logs + local score JSON with 3 dimension scores," leaving Walrus manifest format to GH #13.

## Recommendations

- [META] Add a plan-ID ↔ GH-number mapping table to the meta review issue (or each epic label description) — every cross-reference in the plan ("issues #11–#13 parallelizable", "issue #42 P0") points at the wrong GH number today.
- [META] Populate `blocked-by` on all issues per the plan's own template: GH #5/#6 → GH #1; GH #7–#9 → GH #6; GH #12–#14 → GH #11; GH #15–#17 → GH #13; GH #20/#21 → GH #19+#14; GH #24 → GH #23; GH #26/#27 → GH #25; GH #29–#31 → GH #28.
- [META] Create a "Sunday AM — ENS booth" milestone and put GH #17, #20, #21, #22 on it with a Saturday-PM internal cutoff; this is the only hard external deadline and it is currently invisible in the tracker.
- [GH-25] Mark blocked-on-CAI-key in the issue body per the plan's risk table, and state the unblock condition ("real sandbox inference recorded; do not stub").
- [GH-32] Expand acceptance to enumerate: ENS + Chainlink + Arc + **sui-walrus-reserve** submission docs, 3-min video, architecture diagram, and ENS booth prep checklist.
- [GH-30] Tighten acceptance to require multiple distinct sub-cent USDC settlements on Arc testnet (gas-free micro-settlement, not one transfer) — this is the Arc bounty's literal criterion.
- [GH-29] Add price-formula assertion: 402 price for `min_score=0.9` strictly greater than for `0.5`, per `base * (1 + 4 * min_score)`.
- [GH-31] Extend the agent demo to connect to the returned MCP and execute one quote (plan demo step 7).
- [GH-21] Decouple from the web epic: acceptance = all ENSIP-25/26 + `goldenmcp/eval-blob` records resolvable via CLI for all 3 subnames.
- [GH-24] Specify "no CRE capability mocks; simulate hits live eval-runner + real Walrus aggregator."
- [GH-23] Require the eval-runner response to include the Walrus blob ID consumed by GH #24.
- [GH-20] Specify verification method (`cast call` + blob resolution) for the 3 onchain entries.
- [GH-15] Require both data sources (Arc registry + Walrus manifests) and explicit rendering of binary-failed MCPs.
- [GH-10] Rescope manifest output to local score JSON; Walrus manifest schema stays in GH #13.
- [NEW epic/infra] Phase-0 docs scaffold issue: `docs/submissions/` templates (all four bounties), `docs/architecture.md`, `docs/scoring.md` — the plan schedules this Friday PM but nothing tracks it.
- [NEW epic/marketplace] Issue for the remaining marketplace tools (`list_capabilities` free tier, `get_scores`, `register_mcp`) or explicitly descope them from MVP in GH #28.
- [NEW epic/chainlink] Issue for CRE cron + HTTP trigger wiring (nightly re-eval and on-demand registration), currently implied but unowned between GH #23 and GH #24.
- [NEW epic/walrus] Issue for versioned golden-dataset snapshots on Walrus — listed in the plan's "what gets stored" but covered by no acceptance test.
