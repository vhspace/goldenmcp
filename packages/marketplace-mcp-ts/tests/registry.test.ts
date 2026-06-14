import { test, expect, mock, afterEach } from "bun:test";
import { RegistryClient } from "../src/registry.ts";

const realFetch = globalThis.fetch;
afterEach(() => {
  globalThis.fetch = realFetch;
});

function makeClient() {
  return new RegistryClient({
    rpcUrl: "http://rpc.invalid",
    registryAddress: "0x0000000000000000000000000000000000000001",
    aggregatorUrl: "http://walrus.invalid",
  });
}

const ZERO32 = "0x" + "0".repeat(64);

function stubReadContract(client: RegistryClient, impl: (fn: string, args: unknown[]) => unknown) {
  // Override the private viem client's readContract.
  (client as unknown as { client: { readContract: unknown } }).client = {
    readContract: ({ functionName, args }: { functionName: string; args: unknown[] }) =>
      Promise.resolve(impl(functionName, args)),
  };
}

test("listIndex shapes bps->float, attaches manifest, skips empty blob", async () => {
  const client = makeClient();
  stubReadContract(client, (fn, args) => {
    if (fn === "nextAgentId") return 2n; // one agent: id 1
    if (fn === "getRecord")
      return {
        name: "lifi",
        mcpEndpoint: "https://mcp.lifi",
        agentUri: "agent://lifi",
        ensName: "lifi.eth",
        lastAttestationId: "att-123",
        lastTranscriptHash: ZERO32,
        exists: true,
      };
    if (fn === "getCapabilityScore") {
      const cap = args[1] as string;
      if (cap === "quote")
        return {
          dataScoreBps: 8000,
          pathScoreBps: 9000,
          tokenEfficiencyBps: 7000,
          compositeBps: 8500,
          failed: false,
          walrusBlobId: "blob-quote",
        };
      // other capabilities: empty blob -> skipped
      return {
        dataScoreBps: 0,
        pathScoreBps: 0,
        tokenEfficiencyBps: 0,
        compositeBps: 0,
        failed: false,
        walrusBlobId: "",
      };
    }
    throw new Error(`unexpected fn ${fn}`);
  });

  globalThis.fetch = mock(async () =>
    Response.json({ manifest: "ok" }),
  ) as unknown as typeof fetch;

  const index = await client.listIndex();
  expect(index).toHaveLength(1);
  const entry = index[0]!;
  expect(entry.mcp).toBe("lifi");
  expect(entry.capability).toBe("quote");
  expect(entry.ens_name).toBe("lifi.eth");
  expect(entry.composite).toBeCloseTo(0.85, 6);
  expect(entry.data_score).toBeCloseTo(0.8, 6);
  expect(entry.attestation_id).toBe("att-123");
  expect(entry.transcript_hash).toBeNull(); // all-zero -> null
  expect(entry.walrus_blob_id).toBe("blob-quote");
  expect(entry.manifest).toEqual({ manifest: "ok" });
});

test("listIndex returns empty when no agents", async () => {
  const client = makeClient();
  stubReadContract(client, (fn) => {
    if (fn === "nextAgentId") return 1n; // range 1..1 -> none
    throw new Error("should not read records");
  });
  const index = await client.listIndex();
  expect(index).toEqual([]);
});
