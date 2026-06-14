import { describe, expect, test } from "bun:test";
import { fetchLeaderboard } from "../src/lib/data";

const rpc = process.env.NEXT_PUBLIC_ARC_RPC_URL;
const registry = process.env.NEXT_PUBLIC_REGISTRY_ADDRESS;

describe("fetchLeaderboard (Arc registry integration)", () => {
  test.skipIf(!rpc || !registry)(
    "decodes getRecord and getCapabilityScore from live MCPRegistry",
    async () => {
      const entries = await fetchLeaderboard();
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
