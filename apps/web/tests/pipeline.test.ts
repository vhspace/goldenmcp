import { describe, expect, test } from "bun:test";
import {
  PIPELINE_STEPS,
  applyStepUpdate,
  createInitialPipelineState,
  isFreshPipelineState,
  parseX402PriceStepDetail,
  setActiveStep,
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

describe("flight tracker acceptance (GH #82)", () => {
  test("fresh pipeline state resets between demo runs", () => {
    let state = createInitialPipelineState();
    state = setActiveStep(state, "marketplace_mcp");
    state = applyStepUpdate(state, "marketplace_mcp", "error", undefined, "Arc unavailable");
    expect(state.failedStep).toBe("marketplace_mcp");

    state = createInitialPipelineState();
    expect(isFreshPipelineState(state)).toBe(true);
  });

  test("steps advance sequentially via setActiveStep without skipping", () => {
    let state = createInitialPipelineState();
    for (const def of PIPELINE_STEPS) {
      state = setActiveStep(state, def.id);
      expect(state.activeStep).toBe(def.id);
      state = applyStepUpdate(state, def.id, "complete", { ok: true });
      expect(state.steps.find((s) => s.id === def.id)?.status).toBe("complete");
    }
    expect(state.failedStep).toBeNull();
  });

  test("parseX402PriceStepDetail extracts price and execution from API response", () => {
    const parsed = parseX402PriceStepDetail({
      price: {
        priceLabel: "≥ 90% score · $0.0500 USDC",
        paymentRequired: true,
        network: "arc-testnet",
      },
      execution: {
        httpStatus: 402,
        paymentRequired: true,
        priceUsdc: 0.05,
        capability: "quote",
        minScore: 0.9,
        results: null,
        payee: "0xpayee",
        network: "arc-testnet",
      },
    });
    expect(parsed.price.priceLabel).toContain("USDC");
    expect(parsed.execution.httpStatus).toBe(402);
    expect(parsed.execution.payee).toBe("0xpayee");
  });

  test("parseX402PriceStepDetail rejects malformed API response", () => {
    expect(() => parseX402PriceStepDetail({ price: {} })).toThrow(/execution/);
  });
});
