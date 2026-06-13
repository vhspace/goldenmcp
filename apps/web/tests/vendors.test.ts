import { describe, expect, test } from "bun:test";
import {
  aggregateVendorProfiles,
  extractLatencyMsFromEvalLog,
  goldenScoreBadge,
  meterColor,
  type LeaderboardEntry,
} from "../src/lib/vendors";

describe("goldenScoreBadge", () => {
  test("excellent at 97%", () => {
    expect(goldenScoreBadge(0.97)).toEqual({
      percent: 97,
      label: "Excellent",
      tier: "excellent",
    });
  });

  test("warning at 58%", () => {
    expect(goldenScoreBadge(0.58)).toEqual({
      percent: 58,
      label: "Warning",
      tier: "warning",
    });
  });

  test("critical below 50%", () => {
    expect(goldenScoreBadge(0.42).tier).toBe("critical");
    expect(goldenScoreBadge(0.42).label).toBe("Critical");
  });
});

describe("meterColor", () => {
  test("green at or above 0.85", () => {
    expect(meterColor(0.9)).toBe("green");
  });

  test("yellow between 0.65 and 0.85", () => {
    expect(meterColor(0.7)).toBe("yellow");
  });

  test("red below 0.65", () => {
    expect(meterColor(0.5)).toBe("red");
  });
});

describe("aggregateVendorProfiles", () => {
  const entries: LeaderboardEntry[] = [
    {
      mcp: "lifi",
      capability: "quote",
      dataScore: 0.92,
      pathScore: 0.88,
      tokenEfficiency: 0.95,
      composite: 0.91,
      failed: false,
      walrusBlobId: "blob-a",
      ensName: "alpha-swaps.goldenmcp.eth",
      attestationRef: "inf-1",
      transcriptHash: "0xabc",
    },
    {
      mcp: "lifi",
      capability: "route",
      dataScore: 0.8,
      pathScore: 0.75,
      tokenEfficiency: 0.7,
      composite: 0.76,
      failed: false,
      walrusBlobId: "blob-b",
      ensName: "alpha-swaps.goldenmcp.eth",
      attestationRef: "",
      transcriptHash: "",
    },
    {
      mcp: "odos",
      capability: "quote",
      dataScore: 0.55,
      pathScore: 0.6,
      tokenEfficiency: 0.58,
      composite: 0.58,
      failed: false,
      walrusBlobId: "blob-c",
      ensName: "omega-liquidity.goldenmcp.eth",
      attestationRef: "",
      transcriptHash: "",
    },
  ];

  test("groups by ENS name and picks highest composite capability", () => {
    const profiles = aggregateVendorProfiles(entries);
    expect(profiles).toHaveLength(2);
    const alpha = profiles.find((p) => p.vendorName === "alpha-swaps.goldenmcp.eth");
    expect(alpha?.primaryCapability).toBe("quote");
    expect(alpha?.goldenScore).toBeCloseTo(0.91);
    expect(alpha?.costEfficiency).toBeCloseTo(0.95);
    expect(alpha?.reliability).toBeCloseTo(0.92);
  });
});

describe("extractLatencyMsFromEvalLog", () => {
  test("reads stats.total_time when present (seconds → ms)", () => {
    expect(extractLatencyMsFromEvalLog({ stats: { total_time: 12.4 } })).toBe(12400);
  });

  test("returns null when timing unavailable", () => {
    expect(extractLatencyMsFromEvalLog({ samples: [] })).toBeNull();
  });
});
