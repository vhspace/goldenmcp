# GoldenMCP bounty submission packet

This directory is the judge-facing submission packet for the GoldenMCP eval marketplace.

## Bounty we are submitting for

GoldenMCP is submitted as a Web3 MCP evaluation marketplace that combines:

- standardized Inspect evaluations for live Web3 MCP servers;
- Walrus-backed storage for score manifests and raw eval logs;
- ENS identity and discovery records for evaluated MCPs;
- Chainlink CRE orchestration plus Confidential AI attestation; and
- an Arc-hosted MCP registry with x402 USDC-gated lookup.

## Submission artifacts

| Track | Artifact | What judges should check |
| --- | --- | --- |
| ENS | [`ens.md`](ens.md) | ENS text-record model, resolver flow, code references, booth/demo checklist |
| Chainlink | [`chainlink.md`](chainlink.md) | CRE workflow, CAI attestation path, simulation commands, evidence checklist |
| Arc Agentic Economy | [`arc.md`](arc.md) | frontend/backend checklist, x402 flow, Circle tooling statement, architecture diagram, video plan |
| Sui/Walrus reserve | [`sui-walrus-reserve.md`](sui-walrus-reserve.md) | Walrus storage model, adapter, manifest/log evidence, reserve-bounty positioning |
| End-to-end demo | [`../../demo/README.md`](../../demo/README.md) | local demo runbook for tests, services, lookup flow, and expected outputs |

## Judge run order

1. Read this packet and the project [`README.md`](../../README.md).
2. Run the local smoke demo in [`demo/README.md`](../../demo/README.md).
3. For each bounty track, verify the linked code paths and checklist evidence.
4. If live credentials are available, run the optional live Chainlink/Walrus/Arc commands from each track file.

## Media checklist

The Arc Agentic Economy track requires a 3-minute demo video. The recording plan and narration outline are in [`arc.md`](arc.md#3-minute-demo-video-outline). A completed final submission should attach or link the rendered video next to this packet.
