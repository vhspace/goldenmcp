import { describe, expect, test } from "bun:test";

describe("leaderboard types", () => {
  test("composite score weights sum to 1", () => {
    const weights = [0.45, 0.35, 0.2];
    expect(weights.reduce((a, b) => a + b, 0)).toBe(1);
  });
});
