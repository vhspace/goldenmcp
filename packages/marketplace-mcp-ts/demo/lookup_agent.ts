/**
 * x402 nanopayments buyer demo — deposits USDC into Circle Gateway (once),
 * then makes a gasless payment to the marketplace /tools/lookup endpoint on Arc.
 *
 * Env:
 *   DEMO_PAYER_PRIVATE_KEY  EOA private key (0x...) funded with Arc testnet USDC + native gas
 *   MARKETPLACE_URL         seller base URL (default http://localhost:8091)
 */
import { GatewayClient } from "@circle-fin/x402-batching/client";

const ARCSCAN_TX = "https://testnet.arcscan.app/tx/";

function parseArgs() {
  const args = process.argv.slice(2);
  const out: Record<string, string> = {};
  for (let i = 0; i < args.length; i++) {
    const a = args[i]!;
    if (a.startsWith("--")) out[a.slice(2)] = args[++i] ?? "";
  }
  return out;
}

async function main() {
  const { capability, "min-score": minScoreStr } = parseArgs();
  if (!capability || minScoreStr === undefined) {
    console.error("usage: bun demo/lookup_agent.ts --capability quote --min-score 0.9");
    process.exit(1);
  }
  const minScore = Number(minScoreStr);
  const privateKey = process.env.DEMO_PAYER_PRIVATE_KEY as `0x${string}`;
  if (!privateKey) {
    console.error("DEMO_PAYER_PRIVATE_KEY is required (EOA with Arc testnet USDC + gas)");
    process.exit(1);
  }
  const marketplaceUrl = (process.env.MARKETPLACE_URL ?? "http://localhost:8091").replace(/\/$/, "");

  const client = new GatewayClient({ chain: "arcTestnet", privateKey });
  console.log(`payer=${client.address} chain=arcTestnet`);

  // Ensure a Gateway balance (one-time onchain deposit; payments after are gasless).
  const balances = await client.getBalances();
  console.log(`Gateway available: ${balances.gateway.formattedAvailable} USDC`);
  if (balances.gateway.available < 1_000_000n) {
    console.log("Depositing 1 USDC into Gateway...");
    const deposit = await client.deposit("1");
    console.log(`Deposit tx: ${deposit.depositTxHash}`);
  }

  // Gasless x402 payment — client handles 402 -> sign -> retry automatically.
  const url = `${marketplaceUrl}/tools/lookup`;
  const { data, amount, formattedAmount, transaction, status } = await client.pay<{
    results: Array<{ ens_name: string; mcp_endpoint: string; composite: number }>;
  }>(url, { method: "POST", body: { capability, min_score: minScore } });

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

main().catch((err) => {
  console.error("demo failed:", err);
  process.exit(1);
});
