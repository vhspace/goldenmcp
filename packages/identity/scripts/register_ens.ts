/**
 * Register ENSv2 subnames + ENSIP-25/26 records on Sepolia for every MCP in the
 * Arc registry. Reads MCP data (ensName, endpoint, agentId, scores, Walrus blob)
 * from the Arc registry, then for each MCP creates `<vendor>-<capability>.<parent>`
 * and sets its agent records.
 *
 * gskril/ens-cli emits unsigned calldata; this script signs + broadcasts each tx
 * with MARKETPLACE_WALLET_PRIVATE_KEY (the canonical ENSv2 write pattern).
 *
 * Usage (from repo root, where viem resolves):
 *   node packages/identity/scripts/register_ens.ts            # full run
 *   node packages/identity/scripts/register_ens.ts --dry-run  # print calldata only
 *
 * Idempotent: resolver/subregistry/registration steps short-circuit when already done.
 */
import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import {
  createPublicClient,
  createWalletClient,
  decodeEventLog,
  encodeFunctionData,
  http,
  parseAbi,
  parseAbiItem,
  getAddress,
} from "viem";
import { sepolia } from "viem/chains";
import { privateKeyToAccount } from "viem/accounts";

const DRY_RUN = process.argv.includes("--dry-run");
const ENS_CLI = ["-y", "https://pkg.pr.new/gskril/ens-cli/@ensdomains/cli@main"];
const PARENT = process.env.ENS_PARENT_NAME || "goldenmcp.eth";
const USDC = "0x3DfC8b53dAFa5eBbb071a8B97678Ab534Ed838D9"; // Sepolia ENSv2 dummy USDC
const ARC_CHAIN_ID = 5042002;
const CAPABILITIES = ["quote", "route", "trade", "swap"];
// Capability TTL: a subname expires this many days after its last eval, so a
// lapsed agent identity auto-decays (re-eval renews it). Configurable via
// ENS_SUBNAME_TTL_DAYS; aligns with the nightly re-eval cadence.
const TTL_DAYS = Number(process.env.ENS_SUBNAME_TTL_DAYS || "30");
const TTL_SECONDS = Math.round(TTL_DAYS * 86400);

function env(key: string): string {
  const m = readFileSync(process.cwd() + "/.env", "utf8").match(
    new RegExp("^" + key + "=(.*)$", "m"),
  );
  return (m?.[1] ?? "").trim();
}

/** Run the ens-cli and parse its JSON calldata output. */
function ens(args: string[]): any {
  const out = execFileSync("npx", [...ENS_CLI, ...args, "--json"], {
    encoding: "utf8",
    env: { ...process.env, ETH_RPC_URL: env("ENS_RPC_URL") },
    maxBuffer: 1 << 24,
  });
  // Strip node experimental-warning noise, then parse the JSON object.
  const start = out.indexOf("{");
  return JSON.parse(out.slice(start));
}

/** ERC-7930 interoperable encoding of an EVM (chainId, address). */
function erc7930(chainId: number, addr: string): `0x${string}` {
  const a = addr.toLowerCase().replace(/^0x/, "");
  let h = BigInt(chainId).toString(16);
  if (h.length % 2) h = "0" + h;
  const chainRefLen = (h.length / 2).toString(16).padStart(2, "0");
  return `0x0001${"0000"}${chainRefLen}${h}14${a}`;
}

const REGISTRY_ABI = parseAbi([
  "function nextAgentId() view returns (uint256)",
  "function getRecord(uint256 agentId) view returns ((string name,string mcpEndpoint,string agentUri,string ensName,string lastAttestationId,bytes32 lastTranscriptHash,bool exists))",
  "function getCapabilityScore(uint256 agentId,string capability) view returns ((uint16 dataScoreBps,uint16 pathScoreBps,uint16 tokenEfficiencyBps,uint16 compositeBps,bool failed,string walrusBlobId))",
]);
const ERC20_ABI = parseAbi([
  "function balanceOf(address) view returns (uint256)",
  "function allowance(address owner,address spender) view returns (uint256)",
  "function mint(address,uint256)",
  "function approve(address spender,uint256 amount) returns (bool)",
]);

async function main() {
  let pk = env("MARKETPLACE_WALLET_PRIVATE_KEY");
  if (!pk) throw new Error("MARKETPLACE_WALLET_PRIVATE_KEY missing from .env");
  if (!pk.startsWith("0x")) pk = "0x" + pk;
  const account = privateKeyToAccount(pk as `0x${string}`);
  const wallet = account.address;

  const sepoliaRpc = env("ENS_RPC_URL");
  const pub = createPublicClient({ chain: sepolia, transport: http(sepoliaRpc) });
  const signer = createWalletClient({ account, chain: sepolia, transport: http(sepoliaRpc) });

  const arcRpc = env("ARC_RPC_URL");
  const arcRegistry = getAddress(env("ARC_REGISTRY_ADDRESS"));
  const arc = createPublicClient({
    chain: { ...sepolia, id: ARC_CHAIN_ID, name: "arc", rpcUrls: { default: { http: [arcRpc] } } },
    transport: http(arcRpc),
  });

  const registryKey = erc7930(ARC_CHAIN_ID, arcRegistry);
  console.log(`signer=${wallet} parent=${PARENT}`);
  console.log(`arc registry=${arcRegistry} → ERC-7930 ${registryKey}`);

  // Track the nonce locally: some public RPCs lag on eth_getTransactionCount
  // between rapidly-mined txs, which makes viem's auto-nonce reuse a value.
  let nonce = DRY_RUN ? 0 : await pub.getTransactionCount({ address: wallet });

  /** Sign + broadcast a {to,data,value} calldata object; wait for receipt. */
  async function send(label: string, cd: { to: string; data: string; value?: string }) {
    if (DRY_RUN) {
      console.log(`[dry-run] ${label}: to=${cd.to} value=${cd.value ?? "0"} data=${cd.data.slice(0, 26)}…`);
      return undefined;
    }
    const hash = await signer.sendTransaction({
      to: getAddress(cd.to),
      data: cd.data as `0x${string}`,
      value: BigInt(cd.value ?? "0"),
      nonce: nonce++,
    });
    const rcpt = await pub.waitForTransactionReceipt({ hash });
    if (rcpt.status !== "success") throw new Error(`${label} reverted: ${hash}`);
    console.log(`  ✓ ${label}  ${hash}`);
    return rcpt;
  }

  const PROXY_DEPLOYED = parseAbiItem(
    "event ProxyDeployed(address indexed deployer, address indexed proxyAddress, uint256 salt, address implementation)",
  );
  /** Extract the deployed proxy address from a VerifiableFactory deploy receipt. */
  function proxyFromReceipt(rcpt: any, factory: string): `0x${string}` {
    for (const log of rcpt.logs) {
      if (getAddress(log.address) !== getAddress(factory)) continue;
      try {
        const d = decodeEventLog({ abi: [PROXY_DEPLOYED], data: log.data, topics: log.topics });
        return (d.args as any).proxyAddress;
      } catch {
        /* not the event */
      }
    }
    throw new Error("ProxyDeployed event not found in deploy receipt");
  }

  // ENSv2 UserRegistry: read/extend a subname's expiry. renew() cannot reduce
  // expiry and reverts on an expired name (which must be re-registered), so it
  // is the safe idempotent way to push a live subname's TTL forward.
  const subregistryAbi = parseAbi([
    "function findExpiry(string label) view returns (uint64)",
    "function findTokenId(string label) view returns (uint256)",
    "function renew(uint256 anyId, uint64 newExpiry)",
  ]);
  async function findExpiry(subregistry: string, label: string): Promise<bigint> {
    return (await pub.readContract({
      address: getAddress(subregistry), abi: subregistryAbi, functionName: "findExpiry", args: [label],
    })) as bigint;
  }

  // ── Parent setup (one-time, idempotent) ──────────────────────────────────
  console.log("\n== parent setup ==");

  const resolverOut = ens(["resolver", "deploy", wallet, "--chain", "sepolia"]);
  const resolver = getAddress(resolverOut.resolver);
  if (resolverOut.alreadyDeployed) console.log(`  resolver exists: ${resolver}`);
  else await send("resolver deploy", resolverOut);

  // Register the parent only if still available. `price` errors on an
  // already-registered name, so gate the whole block on `available` first.
  const available = ens(["available", PARENT, "--chain", "sepolia"]);
  if (available.available) {
    const price = ens(["price", PARENT, "--chain", "sepolia"]);
    const needed = BigInt(price.total);
    const bal = (await pub.readContract({ address: USDC, abi: ERC20_ABI, functionName: "balanceOf", args: [wallet] })) as bigint;
    if (bal < needed && !DRY_RUN) {
      const data = encodeFunctionData({ abi: ERC20_ABI, functionName: "mint", args: [wallet, needed - bal] });
      await send("mint test-USDC", { to: USDC, data });
    }
    const registrar = getAddress(price.registrar);
    const allow = (await pub.readContract({ address: USDC, abi: ERC20_ABI, functionName: "allowance", args: [wallet, registrar] })) as bigint;
    if (allow < needed && !DRY_RUN) {
      const data = encodeFunctionData({ abi: ERC20_ABI, functionName: "approve", args: [registrar, needed] });
      await send("approve registrar", { to: USDC, data });
    }

    const commit = ens(["register", "commit", PARENT, "--owner", wallet, "--resolver", resolver, "--chain", "sepolia"]);
    await send("register commit", commit);
    if (!DRY_RUN) {
      console.log("  waiting 75s for commitment maturity…");
      await new Promise((r) => setTimeout(r, 75_000));
    }
    const reveal = ens(["register", "reveal", PARENT, "--owner", wallet, "--resolver", resolver, "--secret", commit.secret, "--chain", "sepolia"]);
    await send("register reveal", reveal);
  } else {
    console.log(`  ${PARENT} already registered`);
  }

  // Deploy + wire the parent subregistry so it can own subnames. The deploy
  // calldata does not return the proxy address (it's emitted in a ProxyDeployed
  // event), so after broadcasting we re-query deploy — which short-circuits to
  // `alreadySet` and hands back the registry address — before wiring it.
  const subregOut = ens(["subregistry", "deploy", PARENT, "--deployer", wallet, "--chain", "sepolia"]);
  let subregistryAddr: `0x${string}` | undefined;
  if (subregOut.alreadySet) {
    subregistryAddr = getAddress(subregOut.subregistry);
    console.log(`  subregistry exists: ${subregistryAddr}`);
  } else if (DRY_RUN) {
    console.log("[dry-run] subregistry deploy + set (proxy address known only after broadcast)");
    await send("subregistry deploy", subregOut);
  } else {
    const rcpt = await send("subregistry deploy", subregOut);
    subregistryAddr = proxyFromReceipt(rcpt, subregOut.factory);
    console.log(`  subregistry deployed: ${subregistryAddr}`);
    const setOut = ens(["subregistry", "set", PARENT, "--registry", subregistryAddr, "--chain", "sepolia"]);
    await send("subregistry set", setOut);
  }

  // ── Per-MCP loop ─────────────────────────────────────────────────────────
  const next = (await arc.readContract({ address: arcRegistry, abi: REGISTRY_ABI, functionName: "nextAgentId" })) as bigint;
  console.log(`\n== ${next - 1n} MCP(s) in Arc registry ==`);

  for (let id = 1n; id < next; id++) {
    const rec = (await arc.readContract({ address: arcRegistry, abi: REGISTRY_ABI, functionName: "getRecord", args: [id] })) as any;
    if (!rec.exists || !rec.ensName) continue;
    const subname: string = rec.ensName;
    const label = subname.slice(0, subname.indexOf("."));
    const capability = label.includes("-") ? label.slice(label.indexOf("-") + 1) : "";
    console.log(`\n#${id} ${subname} (${rec.name}/${capability})`);

    // Pull the capability scores + Walrus blob for agent-context. A failed eval
    // is a real signal worth publishing even when its composite score is 0.
    let scores: any = {};
    let walrusBlobId = "";
    for (const cap of capability ? [capability] : CAPABILITIES) {
      const s = (await arc.readContract({ address: arcRegistry, abi: REGISTRY_ABI, functionName: "getCapabilityScore", args: [id, cap] })) as any;
      if (s.compositeBps > 0 || s.walrusBlobId || s.failed) {
        scores = { data: s.dataScoreBps / 1e4, path: s.pathScoreBps / 1e4, tokenEfficiency: s.tokenEfficiencyBps / 1e4, composite: s.compositeBps / 1e4, failed: s.failed };
        walrusBlobId = s.walrusBlobId;
        break;
      }
    }

    const agentContext = JSON.stringify({ mcp: rec.name, capability, scores, walrusBlobId, agentId: id.toString() });
    const records = [
      { type: "text", key: "agent-endpoint[mcp]", value: rec.mcpEndpoint },
      { type: "text", key: "agent-context", value: agentContext },
      { type: "text", key: "goldenmcp/eval-blob", value: walrusBlobId ? `walrus://${walrusBlobId}` : "" },
      { type: "text", key: `agent-registration[${registryKey}][${id}]`, value: "1" },
    ].filter((r) => r.value !== "");

    // Create the subname with a TTL, or renew a live one to push its expiry
    // forward (re-eval refreshes freshness). Existence is gauged by the
    // subregistry's expiry (>0 = currently registered); findResolver can't be
    // used because ENSv2 falls back to the PARENT resolver for an uncreated
    // subname, so it would false-positive. `subname create` reverts on a live
    // label and renew() cannot reduce expiry, so each path is guarded.
    const newExpiry = BigInt(Math.floor(Date.now() / 1000) + TTL_SECONDS);
    const current = subregistryAddr ? await findExpiry(subregistryAddr, label) : 0n;
    if (current > 0n) {
      if (subregistryAddr && newExpiry > current) {
        const tokenId = (await pub.readContract({
          address: subregistryAddr, abi: subregistryAbi, functionName: "findTokenId", args: [label],
        })) as bigint;
        const data = encodeFunctionData({ abi: subregistryAbi, functionName: "renew", args: [tokenId, newExpiry] });
        await send(`renew (+${TTL_DAYS}d, expiry ${newExpiry})`, { to: subregistryAddr, data });
      } else {
        console.log(`  subname exists, expiry ${current} already >= target — no renew`);
      }
    } else {
      await send(`subname create (TTL ${TTL_DAYS}d)`, ens(["subname", "create", subname, "--owner", wallet, "--duration", String(TTL_SECONDS), "--chain", "sepolia"]));
    }

    const batch = ens(["set", "batch", subname, "--chain", "sepolia", "--data", JSON.stringify(records)]);
    await send("set records", batch);
  }

  console.log("\nDone.");
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
