import { createPublicClient, http, parseAbi } from "viem";
import {
  aggregateVendorProfiles,
  extractLatencyMsFromEvalLog,
  type LeaderboardEntry,
  type VendorProfile,
} from "@/lib/vendors";

export type { LeaderboardEntry, VendorProfile };

const ZERO_BYTES32 = `0x${"0".repeat(64)}`;

/** Tuple ABI — viem mis-decodes flattened struct returns for getRecord/getCapabilityScore. */
const REGISTRY_ABI = [
  {
    type: "function",
    name: "nextAgentId",
    stateMutability: "view",
    inputs: [],
    outputs: [{ name: "", type: "uint256" }],
  },
  {
    type: "function",
    name: "getRecord",
    stateMutability: "view",
    inputs: [{ name: "agentId", type: "uint256" }],
    outputs: [
      {
        type: "tuple",
        name: "",
        components: [
          { name: "name", type: "string" },
          { name: "mcpEndpoint", type: "string" },
          { name: "agentUri", type: "string" },
          { name: "ensName", type: "string" },
          { name: "lastAttestationId", type: "string" },
          { name: "lastTranscriptHash", type: "bytes32" },
          { name: "exists", type: "bool" },
        ],
      },
    ],
  },
  {
    type: "function",
    name: "getCapabilityScore",
    stateMutability: "view",
    inputs: [
      { name: "agentId", type: "uint256" },
      { name: "capability", type: "string" },
    ],
    outputs: [
      {
        type: "tuple",
        name: "",
        components: [
          { name: "dataScoreBps", type: "uint16" },
          { name: "pathScoreBps", type: "uint16" },
          { name: "tokenEfficiencyBps", type: "uint16" },
          { name: "compositeBps", type: "uint16" },
          { name: "failed", type: "bool" },
          { name: "walrusBlobId", type: "string" },
        ],
      },
    ],
  },
] as const;

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
    if (!rec.exists) continue;
    for (const cap of CAPABILITIES) {
      let score;
      try {
        score = await client.readContract({
          address: registry,
          abi: REGISTRY_ABI,
          functionName: "getCapabilityScore",
          args: [id, cap],
        });
      } catch {
        continue;
      }
      if (!score.walrusBlobId) continue;
      entries.push({
        mcp: rec.name,
        capability: cap,
        dataScore: score.dataScoreBps / 10000,
        pathScore: score.pathScoreBps / 10000,
        tokenEfficiency: score.tokenEfficiencyBps / 10000,
        composite: score.compositeBps / 10000,
        failed: score.failed,
        walrusBlobId: score.walrusBlobId,
        ensName: rec.ensName,
        attestationRef: rec.lastAttestationId,
        transcriptHash:
          rec.lastTranscriptHash && rec.lastTranscriptHash !== ZERO_BYTES32
            ? rec.lastTranscriptHash
            : "",
      });
    }
  }
  return entries.sort((a, b) => b.composite - a.composite);
}

export interface ScoreManifest {
  failed?: boolean;
  fail_reason?: string | null;
  data_score?: number;
  path_score?: number;
  token_efficiency?: number;
  composite?: number;
  walrus_blob_id?: string | null;
  walrus_manifest_blob_id?: string | null;
  attestation?: Record<string, unknown> | null;
  attestation_id?: string | null;
  [key: string]: unknown;
}

export async function fetchManifest(mcp: string, capability: string): Promise<ScoreManifest> {
  const entries = await fetchLeaderboard();
  const entry = entries.find((e) => e.mcp === mcp && e.capability === capability);
  if (!entry) throw new Error(`No score for ${mcp}/${capability}`);
  return fetchWalrusJson(entry.walrusBlobId);
}

async function fetchWalrusJson(blobId: string): Promise<Record<string, unknown>> {
  const aggregator = process.env.NEXT_PUBLIC_WALRUS_AGGREGATOR_URL;
  if (!aggregator) {
    throw new Error("NEXT_PUBLIC_WALRUS_AGGREGATOR_URL is not set — cannot fetch Walrus manifests");
  }
  const res = await fetch(`${aggregator}/v1/blobs/${blobId}`);
  if (!res.ok) {
    throw new Error(`Walrus fetch failed for blob ${blobId}: HTTP ${res.status} ${await res.text()}`);
  }
  return res.json();
}

export async function fetchVendorProfiles(): Promise<VendorProfile[]> {
  const entries = await fetchLeaderboard();
  if (entries.length === 0) {
    throw new Error(
      "No vendors in Arc registry — deploy MCPRegistry, register MCPs with ENS names, and run evals",
    );
  }

  const profiles = aggregateVendorProfiles(entries);

  await Promise.all(
    profiles.map(async (profile) => {
      if (profile.vendorName.includes(".eth")) {
        try {
          const records = await resolveENS(profile.vendorName);
          profile.ensRecords = records;
          if (!records["agent-endpoint[mcp]"] && !records["agent-context"]) {
            profile.ensError = `ENSIP-25/26 records missing for ${profile.vendorName} — expected agent-context and agent-endpoint[mcp]`;
          }
        } catch (err) {
          profile.ensError = err instanceof Error ? err.message : String(err);
        }
      }

      try {
        const manifest = await fetchManifest(profile.mcp, profile.primaryCapability);
        const evalRef = manifest.walrus_blob_id;
        if (typeof evalRef !== "string" || !evalRef.trim()) {
          profile.latencyError = "manifest has no walrus_blob_id for eval log";
          return;
        }
        if (evalRef.startsWith("walrus://")) {
          profile.latencyError =
            "eval log stored at walrus:// indexed path — open Inspect View for full timing";
          return;
        }
        const evalLog = await fetchWalrusJson(evalRef);
        profile.latencyMs = extractLatencyMsFromEvalLog(evalLog);
        if (profile.latencyMs === null) {
          profile.latencyError = "eval log has no timing stats (stats.total_time missing)";
        }
      } catch (err) {
        profile.latencyError = err instanceof Error ? err.message : String(err);
      }
    }),
  );

  return profiles;
}

export async function resolveENS(name: string) {
  const rpc = process.env.NEXT_PUBLIC_ENS_RPC_URL;
  if (!rpc) throw new Error("NEXT_PUBLIC_ENS_RPC_URL is not set");
  const { createPublicClient, http, namehash } = await import("viem");
  const { sepolia } = await import("viem/chains");
  const client = createPublicClient({ chain: sepolia, transport: http(rpc) });
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
