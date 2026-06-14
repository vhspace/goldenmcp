import express, { type Request, type Response, type NextFunction } from "express";
import { createGatewayMiddleware } from "@circle-fin/x402-batching/server";
import { RegistryClient, type IndexEntry } from "./registry.ts";
import { priceString, BASE_USDC } from "./pricing.ts";

const ARC_NETWORK = "eip155:5042002";
const FACILITATOR_URL =
  process.env.X402_FACILITATOR_URL ?? "https://gateway-api-testnet.circle.com";

type PaidRequest = Request & {
  payment?: {
    verified: boolean;
    payer: string;
    amount: string;
    network: string;
    transaction?: string;
  };
};

export interface ServerDeps {
  registry: Pick<RegistryClient, "listIndex">;
  gateway: ReturnType<typeof createGatewayMiddleware>;
}

function matchLookup(index: IndexEntry[], capability: string, minScore: number): IndexEntry[] {
  return index
    .filter((r) => r.capability === capability && !r.failed && r.composite >= minScore)
    .sort((a, b) => b.composite - a.composite);
}

function paymentInfo(req: PaidRequest, price: string) {
  const p = req.payment;
  return {
    payment_settled: true,
    price_paid: price,
    payer: p?.payer ?? null,
    network: p?.network ?? ARC_NETWORK,
    transaction: p?.transaction ?? null,
  };
}

export function createApp(deps: ServerDeps): express.Express {
  const app = express();
  app.use(express.json());

  app.get("/health", (_req, res) => {
    res.json({ status: "ok", service: "goldenmcp-marketplace-ts", network: ARC_NETWORK });
  });

  // Run the dynamic-priced Gateway middleware, then the handler.
  const paidPost = (
    priceFor: (req: Request) => string,
    handler: (req: PaidRequest, res: Response, price: string) => Promise<void> | void,
  ) => {
    return async (req: Request, res: Response, next: NextFunction) => {
      const price = priceFor(req);
      const middleware = deps.gateway.require(price);
      middleware(req as never, res as never, ((err?: unknown) => {
        if (err) return next(err as Error);
        Promise.resolve(handler(req as PaidRequest, res, price)).catch(next);
      }) as never);
    };
  };

  app.post(
    "/tools/lookup",
    paidPost(
      (req) => priceString(Number(req.body?.min_score ?? 0)),
      async (req, res, price) => {
        const capability = String(req.body?.capability ?? "");
        const minScore = Number(req.body?.min_score ?? 0);
        if (!capability || Number.isNaN(minScore) || minScore < 0 || minScore > 1) {
          res.status(400).json({ error: "capability and min_score (0..1) are required" });
          return;
        }
        const index = await deps.registry.listIndex();
        const matches = matchLookup(index, capability, minScore);
        if (matches.length === 0) {
          res
            .status(404)
            .json({ error: `No MCPs found for capability=${capability} min_score=${minScore}` });
          return;
        }
        const top = matches[0]!;
        const { manifest: _manifest, agent_id: _agentId, ...result } = top;
        res.json({ results: [result], ...paymentInfo(req, price) });
      },
    ),
  );

  app.post(
    "/tools/get_scores",
    paidPost(
      () => `$${BASE_USDC.toFixed(4)}`,
      async (req, res, price) => {
        const mcp = String(req.body?.mcp ?? "");
        const capability = String(req.body?.capability ?? "");
        if (!mcp || !capability) {
          res.status(400).json({ error: "mcp and capability are required" });
          return;
        }
        const index = await deps.registry.listIndex();
        const match = index.find((r) => r.mcp === mcp && r.capability === capability);
        if (!match) {
          res.status(404).json({ error: `No scores for ${mcp}/${capability}` });
          return;
        }
        res.json({ ...match, ...paymentInfo(req, price) });
      },
    ),
  );

  return app;
}

export function main() {
  const sellerAddress = process.env.X402_PAYEE_ADDRESS;
  if (!sellerAddress) throw new Error("X402_PAYEE_ADDRESS is required");

  const gateway = createGatewayMiddleware({
    sellerAddress,
    facilitatorUrl: FACILITATOR_URL,
    networks: [ARC_NETWORK],
  });
  const registry = new RegistryClient();
  const app = createApp({ registry, gateway });

  const port = Number(process.env.MARKETPLACE_PORT ?? "8091");
  app.listen(port, () => {
    console.log(`GoldenMCP marketplace (TS) listening on :${port} network=${ARC_NETWORK}`);
  });
}

if (import.meta.main) {
  main();
}
