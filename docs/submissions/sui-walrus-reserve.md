# Sui Walrus Reserve Submission

Use this submission if swapping a primary bounty slot to Sui.

## Integration

- Walrus testnet as primary eval blob store
- `walrus://` fsspec adapter for Inspect
- Score manifests and eval logs stored as Walrus blobs
- ENS and ERC-8004 records point to `walrus://<blobId>`
- Web demo fetches manifests via Walrus aggregator HTTP API

## Code

- `packages/walrus-client/`
- `apps/web/src/lib/data.ts` — Walrus manifest fetch
