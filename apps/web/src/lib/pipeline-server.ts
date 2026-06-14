/** Server-side use-case workflow steps — Arc registry, marketplace x402 (GH #82). */

import { fetchLeaderboard, resolveENS } from "@/lib/data";
import type {
  ExecutionResult,
  MarketplaceMcpResult,
  X402PriceResult,
  X402SettlementResult,
} from "@/lib/pipeline";

export async function runMarketplaceMcpStep(
  capability: string,
  minScore: number,
): Promise<MarketplaceMcpResult> {
  const entries = await fetchLeaderboard();
  const matches = entries.filter(
    (e) =>
      e.capability === capability &&
      !e.failed &&
      e.composite >= minScore &&
      Boolean(e.ensName?.trim()),
  );
  matches.sort((a, b) => b.composite - a.composite);

  if (matches.length === 0) {
    throw new Error(
      `No marketplace MCPs for capability=${capability} with composite ≥ ${minScore} — register lifi/1inch on Arc and run evals`,
    );
  }

  const candidates = matches.map((e) => ({
    mcp: e.mcp,
    ensName: e.ensName,
    capability: e.capability,
    composite: e.composite,
    attestationRef: e.attestationRef,
    walrusBlobId: e.walrusBlobId,
  }));

  const best = matches[0];
  const ensRecords = await resolveENS(best.ensName);
  const endpoint = ensRecords["agent-endpoint[mcp]"] ?? "";

  const vendorNames = [...new Set(candidates.map((c) => c.mcp))].join(", ");
  const pct = Math.round(best.composite * 100);

  return {
    ensName: best.ensName,
    mcp: best.mcp,
    capability: best.capability,
    composite: best.composite,
    mcpEndpoint: endpoint,
    ensRecords,
    candidates,
    summary: `Marketplace goldenmcp — ${vendorNames} · selected ${best.mcp} @ ${pct}%`,
  };
}

/** @deprecated alias */
export const runEnsDiscoveryStep = runMarketplaceMcpStep;

export interface X402PriceStepResult {
  price: X402PriceResult;
  execution: ExecutionResult;
}

export async function runX402PriceStep(
  capability: string,
  minScore: number,
): Promise<X402PriceStepResult> {
  const execution = await runMarketplaceLookup(capability, minScore);
  const priceUsdc = execution.priceUsdc;
  const minPct = Math.round(minScore * 100);

  return {
    price: {
      minScore,
      priceUsdc,
      priceLabel:
        priceUsdc !== null
          ? `≥ ${minPct}% score · $${priceUsdc.toFixed(4)} USDC`
          : `≥ ${minPct}% score`,
      capability,
      payee: execution.payee ?? null,
      network: execution.network ?? "arc-testnet",
      paymentRequired: execution.paymentRequired,
    },
    execution,
  };
}

export async function runX402SettlementStep(
  execution: ExecutionResult,
  vendor: MarketplaceMcpResult,
): Promise<X402SettlementResult> {
  const registryAddress = process.env.NEXT_PUBLIC_REGISTRY_ADDRESS ?? null;

  if (execution.paymentRequired) {
    return {
      status: "payment_required",
      payee: execution.payee ?? null,
      network: execution.network ?? "arc-testnet",
      priceUsdc: execution.priceUsdc,
      registryAddress,
      demoRoute: vendor.mcp,
      mcpEndpoint: vendor.mcpEndpoint || null,
      summary: `x402 loop — settle $${execution.priceUsdc ?? "?"} USDC on Arc to unlock demo ${vendor.mcp}`,
    };
  }

  const top = execution.results?.[0];
  const endpoint = (top?.mcp_endpoint as string | undefined) ?? vendor.mcpEndpoint;

  return {
    status: "settled",
    payee: null,
    network: "arc-testnet",
    priceUsdc: execution.priceUsdc,
    registryAddress,
    demoRoute: vendor.mcp,
    mcpEndpoint: endpoint || null,
    summary: `Payment settled — route to demo ${vendor.mcp}${endpoint ? ` @ ${endpoint}` : ""}`,
  };
}

async function runMarketplaceLookup(
  capability: string,
  minScore: number,
): Promise<ExecutionResult> {
  const marketplaceUrl =
    process.env.MARKETPLACE_URL ??
    process.env.NEXT_PUBLIC_MARKETPLACE_URL ??
    "http://localhost:8091";

  const evalRunnerUrl =
    process.env.EVAL_RUNNER_URL ??
    `http://${process.env.EVAL_RUNNER_HOST ?? "127.0.0.1"}:${process.env.EVAL_RUNNER_PORT ?? "8090"}`;

  const healthRes = await fetch(`${evalRunnerUrl.replace(/\/$/, "")}/health`, {
    signal: AbortSignal.timeout(5000),
  });
  if (!healthRes.ok) {
    throw new Error(
      `eval-runner health check failed: HTTP ${healthRes.status} ${await healthRes.text()}`,
    );
  }

  const lookupUrl = `${marketplaceUrl.replace(/\/$/, "")}/tools/lookup`;
  const lookupRes = await fetch(lookupUrl, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ capability, min_score: minScore }),
    signal: AbortSignal.timeout(30000),
  });

  const body = (await lookupRes.json().catch(() => ({}))) as Record<string, unknown>;

  if (lookupRes.status === 402) {
    return {
      httpStatus: 402,
      paymentRequired: true,
      priceUsdc: typeof body.price_usdc === "number" ? body.price_usdc : null,
      capability,
      minScore,
      results: null,
      payee: typeof body.payee === "string" ? body.payee : undefined,
      network: typeof body.network === "string" ? body.network : undefined,
    };
  }

  if (!lookupRes.ok) {
    const msg =
      (typeof body.error === "string" && body.error) ||
      (typeof body.detail === "string" && body.detail) ||
      `HTTP ${lookupRes.status}`;
    throw new Error(`Marketplace lookup failed: ${msg}`);
  }

  const results = Array.isArray(body.results)
    ? (body.results as Record<string, unknown>[])
    : null;

  return {
    httpStatus: lookupRes.status,
    paymentRequired: false,
    priceUsdc: typeof body.price_paid_usdc === "number" ? body.price_paid_usdc : null,
    capability,
    minScore,
    results,
  };
}

/** @deprecated alias */
export const runExecutionStep = runMarketplaceLookup;
