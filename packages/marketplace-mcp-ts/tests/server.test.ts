import { test, expect, beforeAll, afterAll } from "bun:test";
import type { Server } from "http";
import { createApp, type ServerDeps } from "../src/server.ts";
import type { IndexEntry } from "../src/registry.ts";

const SAMPLE: IndexEntry = {
  agent_id: 1,
  mcp: "lifi",
  capability: "quote",
  ens_name: "lifi.eth",
  mcp_endpoint: "https://mcp.lifi",
  data_score: 0.8,
  path_score: 0.9,
  token_efficiency: 0.7,
  composite: 0.95,
  failed: false,
  walrus_blob_id: "blob-1",
  attestation_id: "att-1",
  transcript_hash: null,
  manifest: { x: 1 },
};

/** Fake gateway: returns 402 unless the request carries a PAYMENT-SIGNATURE header. */
function fakeGateway(opts: { settleSucceeds: boolean }): ServerDeps["gateway"] {
  return {
    require: (_price: string) => {
      return (req: any, res: any, next: (err?: unknown) => void) => {
        const sig = req.headers?.["payment-signature"];
        if (!sig) {
          res
            .status(402)
            .json({
              x402Version: 2,
              accepts: [{ scheme: "exact", network: "eip155:5042002", payTo: "0xseller" }],
            });
          return;
        }
        if (!opts.settleSucceeds) {
          res.status(402).json({ error: "Settlement failed" });
          return;
        }
        req.payment = {
          verified: true,
          payer: "0xpayer",
          amount: "50000",
          network: "eip155:5042002",
          transaction: "0xabc",
        };
        next();
      };
    },
    verify: async () => ({ valid: true }),
    settle: async () => ({ success: true }),
  } as unknown as ServerDeps["gateway"];
}

function startApp(deps: ServerDeps): Promise<{ server: Server; url: string }> {
  const app = createApp(deps);
  return new Promise((resolve) => {
    const server = app.listen(0, () => {
      const addr = server.address();
      const port = typeof addr === "object" && addr ? addr.port : 0;
      resolve({ server, url: `http://127.0.0.1:${port}` });
    });
  });
}

let ctx: { server: Server; url: string };
const registry = { listIndex: async () => [SAMPLE] };

beforeAll(async () => {
  ctx = await startApp({ registry, gateway: fakeGateway({ settleSucceeds: true }) });
});
afterAll(() => ctx.server.close());

test("health is unprotected", async () => {
  const res = await fetch(`${ctx.url}/health`);
  expect(res.status).toBe(200);
  expect((await res.json()).network).toBe("eip155:5042002");
});

test("lookup without payment returns 402 with Arc accepts", async () => {
  const res = await fetch(`${ctx.url}/tools/lookup`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ capability: "quote", min_score: 0.9 }),
  });
  expect(res.status).toBe(402);
  const body = await res.json();
  expect(body.accepts[0].network).toBe("eip155:5042002");
});

test("lookup with payment settles and returns result", async () => {
  const res = await fetch(`${ctx.url}/tools/lookup`, {
    method: "POST",
    headers: { "content-type": "application/json", "payment-signature": "sig" },
    body: JSON.stringify({ capability: "quote", min_score: 0.9 }),
  });
  expect(res.status).toBe(200);
  const body = await res.json();
  expect(body.payment_settled).toBe(true);
  expect(body.transaction).toBe("0xabc");
  expect(body.results[0].ens_name).toBe("lifi.eth");
  expect(body.results[0].manifest).toBeUndefined();
});

test("lookup below threshold returns 404 (after payment)", async () => {
  const res = await fetch(`${ctx.url}/tools/lookup`, {
    method: "POST",
    headers: { "content-type": "application/json", "payment-signature": "sig" },
    body: JSON.stringify({ capability: "route", min_score: 0.99 }),
  });
  expect(res.status).toBe(404);
});

test("settlement failure surfaces 402", async () => {
  const failCtx = await startApp({ registry, gateway: fakeGateway({ settleSucceeds: false }) });
  const res = await fetch(`${failCtx.url}/tools/lookup`, {
    method: "POST",
    headers: { "content-type": "application/json", "payment-signature": "sig" },
    body: JSON.stringify({ capability: "quote", min_score: 0.9 }),
  });
  expect(res.status).toBe(402);
  failCtx.server.close();
});
