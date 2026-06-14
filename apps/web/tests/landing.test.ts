import { describe, expect, test } from "bun:test";
import {
  LANDING_CTA,
  LANDING_FEATURES,
  LANDING_HERO,
  LANDING_NAV,
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
