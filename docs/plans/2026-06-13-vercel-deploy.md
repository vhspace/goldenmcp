# Deploy GoldenMCP demo web to Vercel (GH #106)

## Scope

Host **`apps/web`** (Next.js 15) on Vercel. Eval-runner and marketplace MCP remain on DigitalOcean / separate hosts; the web app proxies to them via environment variables.

## Vercel project setup

1. Import `vhspace/goldenmcp` in [Vercel](https://vercel.com/new).
2. **Root Directory:** `apps/web`
3. **Framework Preset:** Next.js (auto-detected)
4. **Install Command:** `bun install` (from `vercel.json`)
5. **Build Command:** `bun run build`
6. Deploy.

`vercel.json` in `apps/web` pins Bun install/build. `next.config.js` skips `output: standalone` when `VERCEL=1`.

## Required environment variables

Set in **Project → Settings → Environment Variables** (Production + Preview):

| Variable | Example | Purpose |
|----------|---------|---------|
| `NEXT_PUBLIC_ARC_RPC_URL` | `https://rpc.testnet.arc.network` | Arc registry reads |
| `NEXT_PUBLIC_REGISTRY_ADDRESS` | `0xae264f…` | MCPRegistry contract |
| `NEXT_PUBLIC_ENS_RPC_URL` | Sepolia public RPC | ENS resolver UI |
| `NEXT_PUBLIC_WALRUS_AGGREGATOR_URL` | Walrus testnet aggregator | Manifest fetch |
| `EVAL_RUNNER_PUBLIC_URL` | `https://eval.example.com` | Flight tracker health + pipeline |
| `MARKETPLACE_URL` | `https://marketplace.example.com` | x402 lookup proxy |

Optional aliases (same values): `ARC_RPC_URL`, `ARC_REGISTRY_ADDRESS`, `EVAL_RUNNER_URL`.

**Do not** use `localhost` for `MARKETPLACE_URL` on Vercel — `web-env.ts` fails loudly if `VERCEL=1` and URL is local.

Secrets (`EVAL_RUNNER_API_KEY`, wallet keys) are **not** needed in the web app unless future routes require them.

## Architecture on Vercel

```
Browser → Vercel (apps/web)
            ├─ SSR /demo, /leaderboard (Arc + Walrus + ENS reads)
            └─ API routes
                 ├─ /api/demo/pipeline/* → eval-runner + marketplace
                 └─ /api/marketplace/lookup → marketplace + eval-runner health

eval-runner (DO)          marketplace MCP (DO or Railway)
```

## Local vs Vercel env

- **Local:** repo-root `.env` parsed by `load-web-env.cjs` when `process.env` keys are unset.
- **Vercel:** only dashboard env vars; no repo `.env` file at build time.
- **Priority:** `process.env` (Vercel) → repo `.env` → documented defaults for public RPCs.

## Acceptance checklist

- [ ] Vercel build succeeds with Root Directory `apps/web`
- [ ] `/demo` loads vendor cards (Arc + registry env set)
- [ ] Start Workflow reaches marketplace step (eval-runner + marketplace URLs public)
- [ ] x402 402 response shows at price gate (expected without payment)

## Follow-ups

- Custom domain + Cloudflare DNS
- Deploy marketplace-mcp-ts to a public HTTPS host if not already
- Vercel preview deployments per PR
