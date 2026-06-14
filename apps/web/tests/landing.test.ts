import { describe, expect, test } from "bun:test";
import {
  LANDING_CTA,
  LANDING_FEATURES,
  LANDING_HERO,
  LANDING_NAV,
  LANDING_SPONSOR_TRACKS,
  LANDING_VENDORS,
  LANDING_WHY,
} from "../src/lib/landing-content";

describe("landing content (GH #108)", () => {
  test("hero has headline and subcopy", () => {
    expect(LANDING_HERO.headline.length).toBeGreaterThan(20);
    expect(LANDING_HERO.subcopy).toMatch(/Walrus|ENS|x402|Arc/i);
  });

  test("nav links point to real app routes", () => {
    const hrefs = LANDING_NAV.map((l) => l.href);
    expect(hrefs).toContain("/demo");
    expect(hrefs).toContain("/leaderboard");
    expect(hrefs.every((h) => h.startsWith("/") || h.startsWith("#") || h.startsWith("http"))).toBe(true);
  });

  test("primary CTA enters demo", () => {
    expect(LANDING_CTA.primary.href).toBe("/demo");
    expect(LANDING_CTA.primary.label.length).toBeGreaterThan(0);
  });

  test("features highlight real GoldenMCP pillars", () => {
    const text = LANDING_FEATURES.map((f) => `${f.title} ${f.body}`).join(" ");
    expect(text).toMatch(/Inspect|ENS|Walrus|x402|Arc|CAI|TEE/i);
  });
});

describe("landing why section (GH #124)", () => {
  test("section has four feature cards", () => {
    expect(LANDING_WHY.sectionTitle).toMatch(/GoldenMCP/i);
    expect(LANDING_WHY.cards.length).toBe(4);
  });

  test("cards cover scores, x402, discovery, and attestation", () => {
    const text = LANDING_WHY.cards.map((c) => `${c.title} ${c.body}`).join(" ");
    expect(text).toMatch(/Golden Score|Inspect|x402|USDC|ENS|TEE|Chainlink/i);
    const visuals = LANDING_WHY.cards.map((c) => c.visual);
    expect(new Set(visuals).size).toBe(4);
  });

  test("nav includes features anchor", () => {
    expect(LANDING_NAV.some((l) => l.href === "#features")).toBe(true);
  });
});

describe("landing hackathon vendors (GH #124)", () => {
  test("lists five registered hackathon MCPs", () => {
    const ids = [
      ...LANDING_VENDORS.quadrants.map((v) => v.id),
      LANDING_VENDORS.centerVendor.id,
    ];
    expect(ids.sort()).toEqual(["1inch", "jupiter", "kyberswap", "lifi", "odos"]);
  });

  test("vendor copy references live eval stack", () => {
    const text = [
      LANDING_VENDORS.sectionLead,
      ...LANDING_VENDORS.quadrants.map((v) => v.body),
      LANDING_VENDORS.centerVendor.body,
    ].join(" ");
    expect(text).toMatch(/Arc|Inspect|Chainlink|x402|MCP/i);
  });

  test("nav includes vendors anchor", () => {
    expect(LANDING_NAV.some((l) => l.href === "#vendors")).toBe(true);
  });
});

describe("landing sponsor tracks (GH #124)", () => {
  test("lists four hackathon tracks", () => {
    expect(LANDING_SPONSOR_TRACKS.tracks.length).toBe(4);
    const ids = LANDING_SPONSOR_TRACKS.tracks.map((t) => t.id);
    expect(ids).toEqual(["ens", "chainlink", "arc", "ethglobal"]);
  });

  test("copy names real bounty integrations", () => {
    const text = [
      LANDING_SPONSOR_TRACKS.sectionLead,
      ...LANDING_SPONSOR_TRACKS.tracks.map((t) => `${t.name} ${t.integration}`),
    ].join(" ");
    expect(text).toMatch(/ENS|Chainlink|Arc|ETHGlobal|CAI|x402|ENSIP/i);
  });

  test("tracks link to sponsor sites", () => {
    for (const track of LANDING_SPONSOR_TRACKS.tracks) {
      expect(track.href).toMatch(/^https:\/\//);
      expect(track.logoSrc).toMatch(/^\/images\/sponsors\/.+\.svg$/);
    }
    expect(LANDING_SPONSOR_TRACKS.tracks.find((t) => t.id === "ens")?.href).toBe("https://ens.domains");
    expect(LANDING_SPONSOR_TRACKS.tracks.find((t) => t.id === "ethglobal")?.href).toContain("ethglobal.com");
  });

  test("nav includes tracks anchor", () => {
    expect(LANDING_NAV.some((l) => l.href === "#tracks")).toBe(true);
  });
});
