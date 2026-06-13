import { createPublicClient, http, parseAbi } from "viem";

const REGISTRY_ABI = parseAbi([
  "function nextAgentId() view returns (uint256)",
  "function getRecord(uint256 agentId) view returns (string name, string mcpEndpoint, string agentUri, string ensName, string lastAttestationTx, bool exists)",
  "function getCapabilityScore(uint256 agentId, string capability) view returns (uint16 dataScoreBps, uint16 pathScoreBps, uint16 tokenScoreBps, uint16 compositeBps, bool failed, string walrusBlobId)",
]);

export interface LeaderboardEntry {
  mcp: string;
  capability: string;
  dataScore: number;
  pathScore: number;
  tokenEfficiency: number;
  composite: number;
  failed: boolean;
  walrusBlobId: string;
  ensName: string;
  attestationTx: string;
}

function getClient() {
  const rpc = process.env.NEXT_PUBLIC_ARC_RPC_URL;
  if (!rpc) throw new Error("NEXT_PUBLIC_ARC_RPC_URL is not set");
  return createPublicClient({ transport: http(rpc) });
}

function getRegistryAddress() {
  const addr = process.env.NEXT_PUBLIC_REGISTRY_ADDRESS;
  if (!addr) throw new Error("NEXT_PUBLIC_REGISTRY_ADDRESS is not set");
  return addr as `0x${string}`;
}

const CAPABILITIES = ["quote", "route", "trade", "swap"];

export async function fetchLeaderboard(): Promise<LeaderboardEntry[]> {
  const client = getClient();
  const registry = getRegistryAddress();
  const nextId = await client.readContract({
    address: registry,
    abi: REGISTRY_ABI,
    functionName: "nextAgentId",
  });
  const entries: LeaderboardEntry[] = [];
  for (let id = 1n; id < nextId; id++) {
    const rec = await client.readContract({
      address: registry,
      abi: REGISTRY_ABI,
      functionName: "getRecord",
      args: [id],
    });
    if (!rec[5]) continue;
    for (const cap of CAPABILITIES) {
      const score = await client.readContract({
        address: registry,
        abi: REGISTRY_ABI,
        functionName: "getCapabilityScore",
        args: [id, cap],
      });
      if (!score[5]) continue;
      entries.push({
        mcp: rec[0],
        capability: cap,
        dataScore: Number(score[0]) / 10000,
        pathScore: Number(score[1]) / 10000,
        tokenEfficiency: Number(score[2]) / 10000,
        composite: Number(score[3]) / 10000,
        failed: score[4],
        walrusBlobId: score[5],
        ensName: rec[3],
        attestationTx: rec[4],
      });
    }
  }
  return entries.sort((a, b) => b.composite - a.composite);
}

export async function fetchManifest(mcp: string, capability: string) {
  const entries = await fetchLeaderboard();
  const entry = entries.find((e) => e.mcp === mcp && e.capability === capability);
  if (!entry) throw new Error(`No score for ${mcp}/${capability}`);
  const aggregator = process.env.NEXT_PUBLIC_WALRUS_AGGREGATOR_URL;
  if (!aggregator) throw new Error("NEXT_PUBLIC_WALRUS_AGGREGATOR_URL is not set");
  const res = await fetch(`${aggregator}/v1/blobs/${entry.walrusBlobId}`);
  if (!res.ok) throw new Error(`Walrus fetch failed: ${res.status} ${await res.text()}`);
  return res.json();
}

export async function resolveENS(name: string) {
  const rpc = process.env.NEXT_PUBLIC_ENS_RPC_URL;
  if (!rpc) throw new Error("NEXT_PUBLIC_ENS_RPC_URL is not set");
  const { createPublicClient, http, namehash } = await import("viem");
  const { mainnet } = await import("viem/chains");
  const client = createPublicClient({ chain: mainnet, transport: http(rpc) });
  const resolver = await client.getEnsResolver({ name });
  if (!resolver) throw new Error(`No resolver for ${name}`);
  const node = namehash(name);
  const keys = ["agent-context", "agent-endpoint[mcp]", "goldenmcp/eval-blob"];
  const result: Record<string, string> = {};
  for (const key of keys) {
    const value = await client.readContract({
      address: resolver,
      abi: parseAbi(["function text(bytes32 node, string key) view returns (string)"]),
      functionName: "text",
      args: [node, key],
    });
    if (value) result[key] = value;
  }
  return result;
}
