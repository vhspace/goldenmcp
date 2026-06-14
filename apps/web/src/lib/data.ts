import { createPublicClient, http, parseAbi } from "viem";
import {
  aggregateVendorProfiles,
  extractLatencyMsFromEvalLog,
  type LeaderboardEntry,
  type VendorProfile,
} from "@/lib/vendors";

export type { LeaderboardEntry, VendorProfile };

const REGISTRY_ABI = parseAbi([
  "function nextAgentId() view returns (uint256)",
  "function getRecord(uint256 agentId) view returns ((string name, string mcpEndpoint, string agentUri, string ensName, string lastAttestationId, bytes32 lastTranscriptHash, bool exists))",
  "function getCapabilityScore(uint256 agentId, string capability) view returns ((uint16 dataScoreBps, uint16 pathScoreBps, uint16 tokenEfficiencyBps, uint16 compositeBps, bool failed, string walrusBlobId))",
]);

function firstEnv(...keys: string[]): string | undefined {
  for (const key of keys) {
    const value = process.env[key]?.trim();
    if (value) return value;
  }
  return undefined;
}

function getClient() {
  const rpc = firstEnv("NEXT_PUBLIC_ARC_RPC_URL", "ARC_RPC_URL", "ARC_TESTNET_RPC_URL");
  if (!rpc) {
    throw new Error(
      "NEXT_PUBLIC_ARC_RPC_URL is not set (also tried ARC_RPC_URL, ARC_TESTNET_RPC_URL)",
    );
  }
  return createPublicClient({ transport: http(rpc) });
}

function getRegistryAddress() {
  const addr = firstEnv("NEXT_PUBLIC_REGISTRY_ADDRESS", "ARC_REGISTRY_ADDRESS");
  if (!addr) {
    throw new Error(
      "NEXT_PUBLIC_REGISTRY_ADDRESS is not set (also tried ARC_REGISTRY_ADDRESS)",
    );
  }
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
      const score = await client.readContract({
        address: registry,
        abi: REGISTRY_ABI,
        functionName: "getCapabilityScore",
        args: [id, cap],
      });
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
          rec.lastTranscriptHash && rec.lastTranscriptHash !== `0x${"0".repeat(64)}`
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

function walrusAggregator(): string {
  const aggregator = firstEnv("NEXT_PUBLIC_WALRUS_AGGREGATOR_URL", "WALRUS_AGGREGATOR_URL");
  if (!aggregator) {
    throw new Error(
      "NEXT_PUBLIC_WALRUS_AGGREGATOR_URL is not set (also tried WALRUS_AGGREGATOR_URL)",
    );
  }
  return aggregator.replace(/\/$/, "");
}

async function fetchWalrusJson(blobId: string): Promise<Record<string, unknown>> {
  const res = await fetch(`${walrusAggregator()}/v1/blobs/${blobId}`);
  if (!res.ok) {
    throw new Error(`Walrus fetch failed for blob ${blobId}: HTTP ${res.status} ${await res.text()}`);
  }
  return res.json();
}

/**
 * Resolve the actual Inspect `.eval` log to a concrete Walrus blob URL.
 *
 * The manifest's `walrus_blob_id` points at the eval log in one of two forms
 * (see packages/inspect-web3 pipeline.py):
 *   1. a direct Walrus blob id (no slashes) — fetchable at /v1/blobs/{id}; or
 *   2. an indexed logical path `walrus://evals/goldenmcp/..._run.eval` that
 *      must be resolved through the WalrusFileSystem index blob.
 *
 * For case (2) we load the index JSON (its blob id comes from WALRUS_INDEX_BLOB_ID)
 * and map the logical path -> concrete blob id. Returns the aggregator HTTP URL
 * for the raw `.eval` bytes, or throws with an actionable message.
 */
export async function resolveEvalLogUrl(manifest: ScoreManifest): Promise<string> {
  const ref = manifest.walrus_blob_id;
  if (typeof ref !== "string" || !ref.trim()) {
    throw new Error("manifest has no walrus_blob_id (no eval log reference)");
  }
  const aggregator = walrusAggregator();

  // Case 1: direct blob id (single path segment, no scheme/slashes).
  if (!ref.startsWith("walrus://") && !ref.includes("/")) {
    return `${aggregator}/v1/blobs/${ref}`;
  }

  // Case 2: walrus:// indexed logical path -> resolve via the index blob.
  const indexBlobId = firstEnv("WALRUS_INDEX_BLOB_ID", "NEXT_PUBLIC_WALRUS_INDEX_BLOB_ID");
  if (!indexBlobId) {
    throw new Error(
      `eval log is at indexed path "${ref}" but WALRUS_INDEX_BLOB_ID is not set — ` +
        "set the Walrus index blob id (printed by post_eval_walrus as walrus_index_blob_id) to resolve it",
    );
  }
  const logical = ref.replace(/^walrus:\/\//, "").replace(/^\/+/, "").replace(/\/+$/, "");
  const index = (await fetchWalrusJson(indexBlobId)) as {
    files?: Record<string, { blob_id?: string }>;
  };
  const entry = index.files?.[logical];
  if (!entry?.blob_id) {
    throw new Error(`Walrus index has no entry for "${logical}" (index blob ${indexBlobId})`);
  }
  return `${aggregator}/v1/blobs/${entry.blob_id}`;
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
        // TTL freshness: an expired ENSv2 subname identity has lapsed since its
        // last eval (0 = never registered → not marked stale, just unregistered).
        const expiry = await ensSubnameExpiry(profile.vendorName);
        if (expiry !== null && expiry > 0) {
          profile.ensExpiry = expiry;
          profile.ensStale = expiry <= Math.floor(Date.now() / 1000);
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
  const rpc = firstEnv("NEXT_PUBLIC_ENS_RPC_URL", "ENS_RPC_URL");
  if (!rpc) throw new Error("NEXT_PUBLIC_ENS_RPC_URL is not set (also tried ENS_RPC_URL)");
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

// Sepolia ENSv2 .eth registry — walked to find a parent's subregistry.
const V2_ETH_REGISTRY =
  process.env.NEXT_PUBLIC_ENS_V2_REGISTRY ?? "0xDEDB92913A25abE1f7BCDD85D8A344a43B398B67";

/**
 * Read an ENSv2 subname's TTL expiry by walking the registry hierarchy:
 * .eth registry → getSubregistry(parentLabel) → findExpiry(childLabel).
 * Returns the unix-seconds expiry, or null if the name isn't a 3-label
 * `child.parent.eth` or has no subregistry. expiry === 0 means never registered.
 */
export async function ensSubnameExpiry(name: string): Promise<number | null> {
  const rpc = firstEnv("NEXT_PUBLIC_ENS_RPC_URL", "ENS_RPC_URL");
  if (!rpc) return null;
  const labels = name.split(".");
  if (labels.length !== 3 || labels[2] !== "eth") return null;
  const [childLabel, parentLabel] = labels;
  const { createPublicClient, http } = await import("viem");
  const { sepolia } = await import("viem/chains");
  const client = createPublicClient({ chain: sepolia, transport: http(rpc) });
  const abi = parseAbi([
    "function getSubregistry(string label) view returns (address)",
    "function findExpiry(string label) view returns (uint64)",
  ]);
  try {
    const subregistry = (await client.readContract({
      address: V2_ETH_REGISTRY as `0x${string}`,
      abi,
      functionName: "getSubregistry",
      args: [parentLabel],
    })) as `0x${string}`;
    if (BigInt(subregistry) === 0n) return null;
    const expiry = (await client.readContract({
      address: subregistry,
      abi,
      functionName: "findExpiry",
      args: [childLabel],
    })) as bigint;
    return Number(expiry);
  } catch {
    return null;
  }
}
