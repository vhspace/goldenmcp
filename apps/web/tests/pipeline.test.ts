import { describe, expect, test } from "bun:test";
import {
  PIPELINE_STEPS,
  applyStepUpdate,
  createInitialPipelineState,
  stepIndex,
  type PipelineStepId,
} from "../src/lib/pipeline";

describe("pipeline state", () => {
  test("defines four use-case workflow steps in order", () => {
    expect(PIPELINE_STEPS.map((s) => s.id)).toEqual([
      "user_trade_intent",
      "marketplace_mcp",
      "x402_price",
      "x402_settlement",
    ]);
  });

  test("applyStepUpdate marks step complete with detail", () => {
    let state = createInitialPipelineState();
    state = applyStepUpdate(state, "user_trade_intent", "complete", { prompt: "Swap USDC" });
    const step = state.steps.find((s) => s.id === "user_trade_intent");
    expect(step?.status).toBe("complete");
    expect(step?.detail).toEqual({ prompt: "Swap USDC" });
  });

  test("applyStepUpdate marks error and stops progression", () => {
    let state = createInitialPipelineState();
    state = applyStepUpdate(state, "marketplace_mcp", "error", { error: "no vendors" });
    expect(state.failedStep).toBe("marketplace_mcp");
    expect(stepIndex("x402_price")).toBeGreaterThan(stepIndex("marketplace_mcp"));
  });

  test("createInitialPipelineState starts all steps pending", () => {
    const state = createInitialPipelineState();
    for (const id of PIPELINE_STEPS.map((s) => s.id) as PipelineStepId[]) {
      expect(state.steps.find((s) => s.id === id)?.status).toBe("pending");
    }
  });
});
