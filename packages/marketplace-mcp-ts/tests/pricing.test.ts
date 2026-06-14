import { test, expect } from "bun:test";
import { priceForThreshold, priceString } from "../src/pricing.ts";

test("priceForThreshold tiers from base", () => {
  expect(priceForThreshold(0, 0.01)).toBeCloseTo(0.01, 6);
  expect(priceForThreshold(0.5, 0.01)).toBeCloseTo(0.03, 6);
  expect(priceForThreshold(1, 0.01)).toBeCloseTo(0.05, 6);
});

test("priceForThreshold clamps out-of-range min_score", () => {
  expect(priceForThreshold(-1, 0.01)).toBeCloseTo(0.01, 6);
  expect(priceForThreshold(2, 0.01)).toBeCloseTo(0.05, 6);
});

test("priceString formats dollars", () => {
  expect(priceString(0, 0.01)).toBe("$0.0100");
  expect(priceString(1, 0.01)).toBe("$0.0500");
});
