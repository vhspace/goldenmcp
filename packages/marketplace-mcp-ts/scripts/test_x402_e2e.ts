/**
 * End-to-end x402 nanopayments test on Arc testnet.
 *
 * 1. Prints buyer balances (wallet + Gateway).
 * 2. Starts the marketplace seller in-process.
 * 3. Confirms an unpaid request returns 402.
 * 4. Makes a real gasless payment via GatewayClient (deposits into Gateway if needed).
 * 5. Prints buyer balances again so you can see the delta.
 *
 * Requires .env: ARC_RPC_URL, ARC_REGISTRY_ADDRESS, WALRUS_AGGREGATOR_URL,
 * X402_PAYEE_ADDRESS, X402_FACILITATOR_URL, DEMO_PAYER_PRIVATE_KEY.
 *
 * Usage:
 *   set -a && source ../../.env && set +a
 *   bun scripts/test_x402_e2e.ts [--capability quote] [--min-score 0.8] [--deposit 1] [--verify-settlement]
 *
 * --verify-settlement polls the Gateway transfer record + seller credit until the
 * batch settles on-chain (can take several minutes on testnet). Off by default.
 */
import type { Server } from "http";
import { GatewayClient } from "@circle-fin/x402-batching/client";
import { createGatewayMiddleware } from "@circle-fin/x402-batching/server";
import { createApp } from "../src/server.ts";
import { RegistryClient } from "../src/registry.ts";
import { priceForThreshold } from "../src/pricing.ts";

const ARC_NETWORK = "eip155:5042002";
const ARCSCAN_TX = "https://testnet.arcscan.app/tx/";

function arg(name: string, fallback: string): string {
  const i = process.argv.indexOf(`--${name}`);
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1]! : fallback;
}

function flag(name: string): boolean {
  return process.argv.includes(`--${name}`);
}

function requireEnv(...keys: string[]) {
  const missing = keys.filter((k) => !process.env[k]);
  if (missing.length) {
    console.error(`Missing env: ${missing.join(", ")}. Did you source ../../.env?`);
    process.exit(1);
  }
}

async function printBalances(client: GatewayClient, label: string) {
  const b = await client.getBalances();
  console.log(`\n[balances ${label}] payer=${client.address}`);
  console.log(`  wallet USDC      : ${b.wallet.formatted}`);
  console.log(`  gateway available: ${b.gateway.formattedAvailable}`);
  console.log(`  gateway total    : ${b.gateway.formattedTotal}`);
  return b;
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

const TERMINAL_STATUSES = new Set(["confirmed", "completed", "failed"]);

/** Poll the Gateway transfer record until it reaches a terminal status. */
async function verifyTransfer(client: GatewayClient, transferId: string) {
  console.log(`\n[verify] polling Gateway transfer ${transferId} ...`);
  const maxAttempts = 30; // ~2.5 min at 5s
  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    let t;
    try {
      t = await client.getTransferById(transferId);
    } catch (err) {
      console.log(`  attempt ${attempt}: lookup error (${(err as Error).message}); retrying`);
      await sleep(5000);
      continue;
    }
    console.log(
      `  attempt ${attempt}: status=${t.status} amount=${t.amount} ` +
        `from=${t.fromAddress} to=${t.toAddress} net=${t.recipientNetwork}`,
    );
    if (TERMINAL_STATUSES.has(t.status)) {
      if (t.status === "failed") {
        console.error(`  ✗ transfer FAILED: ${JSON.stringify(t)}`);
        process.exitCode = 1;
      } else {
        const seller = (process.env.X402_PAYEE_ADDRESS ?? "").toLowerCase();
        const toOk = t.toAddress.toLowerCase() === seller;
        console.log(`  ✓ settled (${t.status}); recipient matches payee: ${toOk}`);
        if (!toOk) process.exitCode = 1;
      }
      return t;
    }
    await sleep(5000);
  }
  console.warn("  ⚠ transfer did not reach a terminal status within the poll window");
  return null;
}

/** Poll the seller's Gateway balance until it reflects the expected credit. */
async function verifySellerCredit(
  client: GatewayClient,
  before: bigint,
  expectedDelta: bigint,
) {
  const seller = process.env.X402_PAYEE_ADDRESS as `0x${string}`;
  console.log(`\n[verify] seller credit on Arc (payee=${seller})`);
  console.log(`  seller gateway available before: ${formatUsdc(before)} USDC`);
  const maxAttempts = 24; // ~2 min at 5s
  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    const b = await client.getBalances(seller);
    const after = b.gateway.available;
    const delta = after - before;
    if (delta >= expectedDelta) {
      console.log(
        `  ✓ seller credited: +${formatUsdc(delta)} USDC ` +
          `(available now ${b.gateway.formattedAvailable})`,
      );
      return;
    }
    console.log(
      `  attempt ${attempt}: available=${b.gateway.formattedAvailable} ` +
        `(delta ${formatUsdc(delta)}, need ${formatUsdc(expectedDelta)}); batch may be pending`,
    );
    await sleep(5000);
  }
  console.warn(
    "  ⚠ seller credit not yet visible — Gateway batches can take longer; re-run later to confirm",
  );
}

function formatUsdc(atomic: bigint): string {
  const neg = atomic < 0n;
  const v = neg ? -atomic : atomic;
  const whole = v / 1_000_000n;
  const frac = (v % 1_000_000n).toString().padStart(6, "0").replace(/0+$/, "") || "0";
  return `${neg ? "-" : ""}${whole}.${frac}`;
}

function startSeller(): Promise<{ server: Server; url: string }> {
  const gateway = createGatewayMiddleware({
    sellerAddress: process.env.X402_PAYEE_ADDRESS!,
    facilitatorUrl: process.env.X402_FACILITATOR_URL ?? "https://gateway-api-testnet.circle.com",
    networks: [ARC_NETWORK],
  });
  const app = createApp({ registry: new RegistryClient(), gateway });
  return new Promise((resolve) => {
    const server = app.listen(0, () => {
      const addr = server.address();
      const port = typeof addr === "object" && addr ? addr.port : 0;
      resolve({ server, url: `http://127.0.0.1:${port}` });
    });
  });
}

async function main() {
  requireEnv(
    "ARC_RPC_URL",
    "ARC_REGISTRY_ADDRESS",
    "WALRUS_AGGREGATOR_URL",
    "X402_PAYEE_ADDRESS",
    "DEMO_PAYER_PRIVATE_KEY",
  );
  const capability = arg("capability", "quote");
  const minScore = Number(arg("min-score", "0.8"));
  const depositAmount = arg("deposit", "1");
  // Settlement on testnet is batched and can take a while; opt in to poll for it.
  const verifySettlement = flag("verify-settlement");

  const client = new GatewayClient({
    chain: "arcTestnet",
    privateKey: process.env.DEMO_PAYER_PRIVATE_KEY as `0x${string}`,
  });
  console.log(`payee (seller): ${process.env.X402_PAYEE_ADDRESS}`);
  await printBalances(client, "before");

  // Snapshot seller Gateway balance so we can confirm the credit delta later (opt-in).
  let sellerBalanceBefore = 0n;
  if (verifySettlement) {
    const sellerBefore = await client.getBalances(process.env.X402_PAYEE_ADDRESS as `0x${string}`);
    sellerBalanceBefore = sellerBefore.gateway.available;
  }

  const { server, url } = await startSeller();
  console.log(`\nseller listening at ${url}`);

  let transferId: string | null = null;
  let paidAtomic = 0n;

  try {
    // 1. Unpaid request -> expect 402.
    const unpaid = await fetch(`${url}/tools/lookup`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ capability, min_score: minScore }),
    });
    console.log(`\n[unpaid] status=${unpaid.status} (expected 402)`);
    if (unpaid.status !== 402) {
      console.error("Expected 402 for unpaid request:", await unpaid.text());
      process.exit(1);
    }

    // 2. Ensure Gateway balance covers this payment; deposit only if it can't.
    const priceAtomic = BigInt(Math.round(priceForThreshold(minScore) * 1_000_000));
    const bal = await client.getBalances();
    if (bal.gateway.available < priceAtomic) {
      console.log(
        `\nGateway available ${bal.gateway.formattedAvailable} < price ${formatUsdc(priceAtomic)} — ` +
          `depositing ${depositAmount} USDC (one-time onchain tx)...`,
      );
      const dep = await client.deposit(depositAmount);
      console.log(`  deposit tx: ${ARCSCAN_TX}${dep.depositTxHash}`);
    }

    // 3. Gasless payment.
    console.log(`\n[pay] capability=${capability} min_score=${minScore}`);
    const res = await client.pay<{
      results?: Array<{ ens_name: string; mcp_endpoint: string; composite: number }>;
      transaction?: string;
    }>(`${url}/tools/lookup`, {
      method: "POST",
      body: { capability, min_score: minScore },
    });
    console.log(`  status=${res.status} paid=${res.formattedAmount} USDC (${res.amount} atomic)`);
    if (res.transaction) console.log(`  settlement transfer id: ${res.transaction}`);
    const best = res.data.results?.[0];
    if (best) {
      console.log(
        `  best MCP: ${best.ens_name} endpoint=${best.mcp_endpoint} composite=${best.composite.toFixed(3)}`,
      );
    } else {
      console.log("  response:", JSON.stringify(res.data));
    }
    transferId = res.transaction ?? null;
    paidAtomic = res.amount;
  } finally {
    server.close();
  }

  // 4 & 5. Settlement verification (opt-in: --verify-settlement).
  // Gateway batches payments, so on-chain settlement can lag minutes on testnet.
  if (verifySettlement) {
    if (transferId) {
      await verifyTransfer(client, transferId);
    } else {
      console.warn("\n[verify] no transfer id returned — cannot confirm settlement");
    }
    await verifySellerCredit(client, sellerBalanceBefore, paidAtomic);
  } else if (transferId) {
    console.log(
      `\n[settlement] transfer id ${transferId} queued (batched). ` +
        `Re-run with --verify-settlement to poll for on-chain confirmation.`,
    );
  }

  // 6. Final buyer balances.
  await printBalances(client, "after");
}

main().catch((err) => {
  console.error("\nE2E test failed:", err);
  process.exit(1);
});
