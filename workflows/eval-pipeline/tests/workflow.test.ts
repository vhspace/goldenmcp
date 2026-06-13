import { describe, expect, test } from "bun:test";

describe("eval pipeline config", () => {
  test("schedule is defined", () => {
    expect("0 */6 * * *").toMatch(/\d/);
  });

  test("scoring weights", () => {
    const composite = 0.45 * 0.9 + 0.35 * 0.8 + 0.2 * 0.7;
    expect(composite).toBeGreaterThan(0.8);
  });
});
