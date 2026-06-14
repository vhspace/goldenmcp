import { describe, expect, test } from "bun:test";
import { CHAT_DEMO_PROMPTS, parseDemoPrompt } from "../src/lib/intent";

describe("parseDemoPrompt", () => {
  test("parses portfolio swap prompt into structured intent", () => {
    const prompt =
      "Optimize portfolio: Swap $100 USDC for GHO at the absolute lowest execution time.";
    const intent = parseDemoPrompt(prompt);

    expect(intent.action).toBe("DeFi Swap");
    expect(intent.assetsFrom).toBe("USDC");
    expect(intent.assetsTo).toBe("GHO");
    expect(intent.amountUsd).toBe(100);
    expect(intent.minReliabilityScore).toBeGreaterThanOrEqual(0.9);
    expect(intent.marketplaceCapability).toBe("swap");
    expect(intent.objective).toMatch(/execution time/i);
  });

  test("parses quote prompt with explicit min score", () => {
    const prompt = "Get best ETH/USDC quote with min reliability ≥ 0.15";
    const intent = parseDemoPrompt(prompt);

    expect(intent.action).toBe("DeFi Quote");
    expect(intent.assetsFrom).toBe("ETH");
    expect(intent.assetsTo).toBe("USDC");
    expect(intent.minReliabilityScore).toBeCloseTo(0.15);
    expect(intent.marketplaceCapability).toBe("quote");
  });

  test("parses route optimization prompt", () => {
    const prompt = "Route 500 DAI to USDC on L2 with reliability at least 0.92";
    const intent = parseDemoPrompt(prompt);

    expect(intent.action).toBe("DeFi Route");
    expect(intent.assetsFrom).toBe("DAI");
    expect(intent.assetsTo).toBe("USDC");
    expect(intent.minReliabilityScore).toBeCloseTo(0.92);
    expect(intent.marketplaceCapability).toBe("route");
  });

  test("chat demo prompts are defined for concierge quick actions", () => {
    expect(CHAT_DEMO_PROMPTS.length).toBeGreaterThan(0);
    for (const prompt of CHAT_DEMO_PROMPTS) {
      expect(prompt.id.length).toBeGreaterThan(0);
      expect(prompt.text.trim().length).toBeGreaterThan(0);
    }
  });
});
