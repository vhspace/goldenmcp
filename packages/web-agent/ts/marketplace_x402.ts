/**
 * Paid marketplace lookup — Circle GatewayClient x402 (no mock settlement).
 *
 * Usage:
 *   DEMO_PAYER_PRIVATE_KEY=0x... bun ts/marketplace_x402.ts --capability quote --min-score 0.9
 *
 * Env: MARKETPLACE_URL (default http://localhost:8091)
 */
import { GatewayClient } from "@circle-fin/x402-batching/client";

const ARCSCAN_TX = "https://testnet.arcscan.app/tx/";

function parseArgs(): Record<string, string> {
  const out: Record<string, string> = {};
  const args = process.argv.slice(2);
  for (let i = 0; i < args.length; i++) {
    const a = args[i]!;
    if (a.startsWith("--")) out[a.slice(2)] = args[++i] ?? "";
  }
  return out;
}

export async function paidLookup(
  capability: string,
  minScore: number,
  opts?: { marketplaceUrl?: string; privateKey?: `0x${string}` },
) {
  const privateKey = (opts?.privateKey ?? process.env.DEMO_PAYER_PRIVATE_KEY) as `0x${string}`;
  if (!privateKey) {
    throw new Error("DEMO_PAYER_PRIVATE_KEY is required (EOA with Arc testnet USDC + gas)");
  }
  const marketplaceUrl = (opts?.marketplaceUrl ?? process.env.MARKETPLACE_URL ?? "http://localhost:8091").replace(
    /\/$/,
    "",
  );

  const client = new GatewayClient({ chain: "arcTestnet", privateKey });
  const url = `${marketplaceUrl}/tools/lookup`;
  return client.pay<{
    results: Array<{
      ens_name: string;
      mcp_endpoint: string;
      composite: number;
      attestation_id?: string | null;
      transcript_hash?: string | null;
    }>;
    payment_settled?: boolean;
    price_paid?: string;
    transaction?: string | null;
  }>(url, { method: "POST", body: { capability, min_score: minScore } });
}

async function main() {
  const { capability, "min-score": minScoreStr } = parseArgs();
  if (!capability || minScoreStr === undefined) {
    console.error("usage: bun ts/marketplace_x402.ts --capability quote --min-score 0.9");
    process.exit(1);
  }
  const minScore = Number(minScoreStr);
  const { data, amount, formattedAmount, transaction, status } = await paidLookup(capability, minScore);

  console.log(`status=${status} paid=${formattedAmount} USDC (${amount} atomic)`);
  if (transaction) console.log(`settlement: ${ARCSCAN_TX}${transaction}`);
  const best = data.results?.[0];
  if (best) {
    console.log(
      `best MCP: ${best.ens_name} endpoint=${best.mcp_endpoint} composite=${best.composite.toFixed(3)}`,
    );
  } else {
    console.log("response:", JSON.stringify(data, null, 2));
  }
}

if (import.meta.main) {
  main().catch((err) => {
    console.error("paid lookup failed:", err);
    process.exit(1);
  });
}
