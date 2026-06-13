"use client";

import type { ParsedIntent } from "@/lib/intent";
import type {
  EnsDiscoveryResult,
  ExecutionResult,
  PipelineRunState,
  PipelineStepId,
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

  // Step 1 — user prompt (local parse, no network)
  push(setActiveStep(state, "user_prompt"));
  push(
    applyStepUpdate(state, "user_prompt", "complete", {
      action: intent.action,
      assets: `${intent.assetsFrom} → ${intent.assetsTo}`,
      minReliabilityScore: intent.minReliabilityScore,
      rawPrompt: intent.rawPrompt,
    }),
  );

  let vendor: EnsDiscoveryResult | undefined;

  if (
    !(await runStep("ens_discovery", async () => {
      const res = await fetchPipelineStep<EnsDiscoveryResult>("ens-discovery", { intent });
      vendor = res.detail!;
      return { ...(res.detail as unknown as Record<string, unknown>) };
    }))
  ) {
    return state;
  }

  if (
    !(await runStep("tee_sandbox", async () => {
      const res = await fetchPipelineStep("tee-sandbox", { vendor });
      return { ...(res.detail as unknown as Record<string, unknown>) };
    }))
  ) {
    return state;
  }

  let execution: ExecutionResult | undefined;

  if (
    !(await runStep("execution_engine", async () => {
      const res = await fetchPipelineStep<ExecutionResult>("execute", { intent });
      execution = res.detail!;
      return { ...(res.detail as unknown as Record<string, unknown>) };
    }))
  ) {
    return state;
  }

  await runStep("blockchain_proof", async () => {
    const res = await fetchPipelineStep("blockchain-proof", { vendor, execution });
    return { ...(res.detail as unknown as Record<string, unknown>) };
  });

  return state;
}
