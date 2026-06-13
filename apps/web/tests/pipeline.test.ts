import { describe, expect, test } from "bun:test";
import {
  PIPELINE_STEPS,
  applyStepUpdate,
  createInitialPipelineState,
  stepIndex,
  type PipelineStepId,
} from "../src/lib/pipeline";

describe("pipeline state", () => {
  test("defines five steps in order", () => {
    expect(PIPELINE_STEPS.map((s) => s.id)).toEqual([
      "user_prompt",
      "ens_discovery",
      "tee_sandbox",
      "execution_engine",
      "blockchain_proof",
    ]);
  });

  test("applyStepUpdate marks step complete with detail", () => {
    let state = createInitialPipelineState();
    state = applyStepUpdate(state, "user_prompt", "complete", { prompt: "Swap USDC" });
    const step = state.steps.find((s) => s.id === "user_prompt");
    expect(step?.status).toBe("complete");
    expect(step?.detail).toEqual({ prompt: "Swap USDC" });
  });

  test("applyStepUpdate marks error and stops progression", () => {
    let state = createInitialPipelineState();
    state = applyStepUpdate(state, "ens_discovery", "error", { error: "no vendors" });
    expect(state.failedStep).toBe("ens_discovery");
    expect(stepIndex("tee_sandbox")).toBeGreaterThan(stepIndex("ens_discovery"));
  });

  test("createInitialPipelineState starts all steps pending", () => {
    const state = createInitialPipelineState();
    for (const id of PIPELINE_STEPS.map((s) => s.id) as PipelineStepId[]) {
      expect(state.steps.find((s) => s.id === id)?.status).toBe("pending");
    }
  });
});
