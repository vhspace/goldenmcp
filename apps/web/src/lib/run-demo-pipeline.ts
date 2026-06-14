"use client";

import type { ParsedIntent } from "@/lib/intent";
import type {
  ExecutionResult,
  MarketplaceMcpResult,
  PipelineRunState,
  PipelineStepId,
  X402PriceResult,
} from "@/lib/pipeline";
import {
  applyStepUpdate,
  createInitialPipelineState,
  setActiveStep,
} from "@/lib/pipeline";

async function fetchPipelineStep<T>(
  step: string,
  body: Record<string, unknown>,
): Promise<{ status: string; detail?: T; error?: string }> {
  const res = await fetch(`/api/demo/pipeline/${step}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const json = await res.json().catch(() => ({}));
  if (!res.ok || json.status === "error") {
    throw new Error(json.error ?? `Pipeline step ${step} failed: HTTP ${res.status}`);
  }
  return json;
}

export async function runDemoPipeline(
  intent: ParsedIntent,
  onUpdate: (state: PipelineRunState) => void,
): Promise<PipelineRunState> {
  let state = createInitialPipelineState();

  const push = (next: PipelineRunState) => {
    state = next;
    onUpdate(state);
  };

  const runStep = async (
    id: PipelineStepId,
    runner: () => Promise<Record<string, unknown>>,
  ): Promise<boolean> => {
    push(setActiveStep(state, id));
    try {
      const detail = await runner();
      push(applyStepUpdate(state, id, "complete", detail));
      return true;
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      push(applyStepUpdate(state, id, "error", undefined, message));
      return false;
    }
  };

  // Step 1 — User @Permit trade intent (local parse)
  push(setActiveStep(state, "user_trade_intent"));
  push(
    applyStepUpdate(state, "user_trade_intent", "complete", {
      permit: "User @Permit",
      action: intent.action,
      assets: `${intent.assetsFrom} → ${intent.assetsTo}`,
      minReliabilityScore: intent.minReliabilityScore,
      rawPrompt: intent.rawPrompt,
      summary: `Trade request: ${intent.action} ${intent.assetsFrom} → ${intent.assetsTo}`,
    }),
  );

  let vendor: MarketplaceMcpResult | undefined;

  if (
    !(await runStep("marketplace_mcp", async () => {
      const res = await fetchPipelineStep<MarketplaceMcpResult>("marketplace-mcp", { intent });
      vendor = res.detail!;
      return { ...(res.detail as unknown as Record<string, unknown>) };
    }))
  ) {
    return state;
  }

  let execution: ExecutionResult | undefined;

  if (
    !(await runStep("x402_price", async () => {
      const res = await fetchPipelineStep<{ price: X402PriceResult; execution: ExecutionResult }>(
        "x402-price",
        { intent },
      );
      execution = res.detail!.execution;
      return { ...(res.detail!.price as unknown as Record<string, unknown>) };
    }))
  ) {
    return state;
  }

  if (vendor && execution) {
    await runStep("x402_settlement", async () => {
      const res = await fetchPipelineStep("x402-settlement", { vendor, execution });
      return { ...(res.detail as unknown as Record<string, unknown>) };
    });
  }

  return state;
}
