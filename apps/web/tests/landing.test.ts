import { describe, expect, test } from "bun:test";
import {
  LANDING_CTA,
  LANDING_FEATURES,
  LANDING_HERO,
  LANDING_KEY_COMPONENTS,
  LANDING_NAV,
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

describe("landing key components (GH #124)", () => {
  test("section has hero and three pillar cards", () => {
    expect(LANDING_KEY_COMPONENTS.sectionTitle.length).toBeGreaterThan(5);
    expect(LANDING_KEY_COMPONENTS.hero.subPanels.length).toBe(2);
    expect(LANDING_KEY_COMPONENTS.cards.length).toBe(3);
  });

  test("copy references real GoldenMCP stack", () => {
    const text = [
      LANDING_KEY_COMPONENTS.hero.title,
      LANDING_KEY_COMPONENTS.hero.body,
      ...LANDING_KEY_COMPONENTS.hero.subPanels.map((p) => `${p.title} ${p.body}`),
      ...LANDING_KEY_COMPONENTS.cards.map((c) => `${c.title} ${c.body}`),
    ].join(" ");
    expect(text).toMatch(/Walrus|Arc|Inspect|Chainlink|CAI|x402|USDC|ENS/i);
  });

  test("nav includes components anchor", () => {
    expect(LANDING_NAV.some((l) => l.href === "#components")).toBe(true);
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
