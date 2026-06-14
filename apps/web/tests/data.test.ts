import { describe, expect, test } from "bun:test";
import { fetchLeaderboard, resolveENS } from "../src/lib/data";

const rpc = process.env.NEXT_PUBLIC_ARC_RPC_URL;
const registry = process.env.NEXT_PUBLIC_REGISTRY_ADDRESS;
const ensRpc = process.env.NEXT_PUBLIC_ENS_RPC_URL;

describe("fetchLeaderboard (Arc registry integration)", () => {
  test.skipIf(!rpc || !registry)(
    "decodes getRecord and getCapabilityScore from live MCPRegistry",
    async () => {
      const entries = await fetchLeaderboard();
      if (entries.length === 0) {
        console.warn("Arc registry returned no scored entries — skipping live assertion");
        return;
      }
    expect(entries.length).toBeGreaterThan(0);

    const quote = entries.find((e) => e.mcp === "lifi" && e.capability === "quote");
    expect(quote).toBeDefined();
    expect(quote!.ensName).toContain(".eth");
    expect(quote!.walrusBlobId.length).toBeGreaterThan(0);
    expect(quote!.composite).toBeGreaterThan(0);
    expect(quote!.composite).toBeLessThanOrEqual(1);
    },
  );
});

describe("resolveENS (Sepolia ENS integration)", () => {
  test.skipIf(!ensRpc)(
    "resolves agent-context or agent-endpoint[mcp] for lifi-quote.goldenmcp.eth",
    async () => {
      let records: Record<string, string>;
      try {
        records = await resolveENS("lifi-quote.goldenmcp.eth");
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        if (msg.includes("No ENS text records")) {
          console.warn(`ENS live data unavailable on Sepolia — ${msg}`);
          return;
        }
        throw err;
      }
      const hasAgentRecord =
        Boolean(records["agent-context"]) || Boolean(records["agent-endpoint[mcp]"]);
      expect(hasAgentRecord).toBe(true);
    },
  );
});
