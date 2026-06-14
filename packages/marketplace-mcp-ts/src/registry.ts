import { createPublicClient, http, type Address, type PublicClient } from "viem";
import { arcTestnet } from "viem/chains";

export const CAPABILITIES = ["quote", "route", "trade", "swap"] as const;

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

const ZERO_BYTES32 = "0x" + "0".repeat(64);

export interface IndexEntry {
  agent_id: number;
  mcp: string;
  capability: string;
  ens_name: string;
  mcp_endpoint: string;
  data_score: number;
  path_score: number;
  token_efficiency: number;
  composite: number;
  failed: boolean;
  walrus_blob_id: string;
  attestation_id: string | null;
  transcript_hash: string | null;
  manifest: unknown;
}

function formatBytes32(value: string): string | null {
  if (!value || value === ZERO_BYTES32) return null;
  return value;
}

async function downloadManifest(aggregatorUrl: string, blobId: string): Promise<unknown> {
  try {
    const res = await fetch(`${aggregatorUrl.replace(/\/$/, "")}/v1/blobs/${blobId}`);
    if (!res.ok) return {};
    return await res.json();
  } catch {
    return {};
  }
}

export class RegistryClient {
  private readonly client: PublicClient;
  private readonly registryAddress: Address;
  private readonly aggregatorUrl: string;

  constructor(opts?: { rpcUrl?: string; registryAddress?: string; aggregatorUrl?: string }) {
    const rpcUrl = opts?.rpcUrl ?? process.env.ARC_RPC_URL;
    const registryAddress = opts?.registryAddress ?? process.env.ARC_REGISTRY_ADDRESS;
    const aggregatorUrl = opts?.aggregatorUrl ?? process.env.WALRUS_AGGREGATOR_URL;
    if (!rpcUrl) throw new Error("ARC_RPC_URL is required");
    if (!registryAddress) throw new Error("ARC_REGISTRY_ADDRESS is required");
    if (!aggregatorUrl) throw new Error("WALRUS_AGGREGATOR_URL is required");
    this.client = createPublicClient({ chain: arcTestnet, transport: http(rpcUrl) });
    this.registryAddress = registryAddress as Address;
    this.aggregatorUrl = aggregatorUrl;
  }

  private read<T>(functionName: string, args: unknown[]): Promise<T> {
    return this.client.readContract({
      address: this.registryAddress,
      abi: REGISTRY_ABI,
      functionName: functionName as never,
      args: args as never,
    }) as Promise<T>;
  }

  async listIndex(maxId = 100): Promise<IndexEntry[]> {
    const nextId = Number(await this.read<bigint>("nextAgentId", []));
    const entries: IndexEntry[] = [];
    for (let agentId = 1; agentId < Math.min(nextId, maxId); agentId++) {
      const rec = await this.read<{
        name: string;
        mcpEndpoint: string;
        agentUri: string;
        ensName: string;
        lastAttestationId: string;
        lastTranscriptHash: string;
        exists: boolean;
      }>("getRecord", [BigInt(agentId)]);

      for (const capability of CAPABILITIES) {
        let score;
        try {
          score = await this.read<{
            dataScoreBps: number;
            pathScoreBps: number;
            tokenEfficiencyBps: number;
            compositeBps: number;
            failed: boolean;
            walrusBlobId: string;
          }>("getCapabilityScore", [BigInt(agentId), capability]);
        } catch {
          continue;
        }
        if (!score.walrusBlobId) continue;

        const manifest = await downloadManifest(this.aggregatorUrl, score.walrusBlobId);
        entries.push({
          agent_id: agentId,
          mcp: rec.name,
          capability,
          ens_name: rec.ensName,
          mcp_endpoint: rec.mcpEndpoint,
          data_score: score.dataScoreBps / 10000,
          path_score: score.pathScoreBps / 10000,
          token_efficiency: score.tokenEfficiencyBps / 10000,
          composite: score.compositeBps / 10000,
          failed: score.failed,
          walrus_blob_id: score.walrusBlobId,
          attestation_id: rec.lastAttestationId || null,
          transcript_hash: formatBytes32(rec.lastTranscriptHash),
          manifest,
        });
      }
    }
    return entries;
  }
}
