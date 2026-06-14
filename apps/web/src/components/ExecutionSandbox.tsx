"use client";

import { useState } from "react";
import {
  DEMO_PROMPTS,
  formatAssets,
  formatMinReliability,
  parseDemoPrompt,
  type ParsedIntent,
} from "@/lib/intent";
import type { PipelineRunState } from "@/lib/pipeline";
import { createInitialPipelineState } from "@/lib/pipeline";
import { runDemoPipeline } from "@/lib/run-demo-pipeline";
import { FlightTracker } from "@/components/FlightTracker";
import styles from "@/components/demo/demo-dashboard.module.css";

function IntentSummary({ intent }: { intent: ParsedIntent }) {
  return (
    <dl className={styles.intentGrid}>
      <dt>Action</dt>
      <dd>{intent.action}</dd>
      <dt>Assets</dt>
      <dd>{formatAssets(intent.assetsFrom, intent.assetsTo)}</dd>
      {intent.amountUsd !== null && (
        <>
          <dt>Amount</dt>
          <dd>${intent.amountUsd.toLocaleString()}</dd>
        </>
      )}
      <dt>Min reliability</dt>
      <dd>{formatMinReliability(intent.minReliabilityScore)}</dd>
      <dt>Objective</dt>
      <dd>{intent.objective}</dd>
      <dt>Capability</dt>
      <dd>
        <code>{intent.marketplaceCapability}</code>
      </dd>
    </dl>
  );
}

export function ExecutionSandbox() {
  const [selectedPrompt, setSelectedPrompt] = useState<string | null>(null);
  const [intent, setIntent] = useState<ParsedIntent | null>(null);
  const [parseError, setParseError] = useState("");
  const [pipeline, setPipeline] = useState<PipelineRunState | null>(null);
  const [loading, setLoading] = useState(false);

  function selectPrompt(text: string) {
    setParseError("");
    setPipeline(null);
    setSelectedPrompt(text);
    try {
      setIntent(parseDemoPrompt(text));
    } catch (err) {
      setIntent(null);
      setParseError(err instanceof Error ? err.message : String(err));
    }
  }

  async function handleStartWorkflow() {
    if (!intent) return;
    setLoading(true);
    setPipeline(createInitialPipelineState());
    try {
      await runDemoPipeline(intent, setPipeline);
    } catch (err) {
      setPipeline((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          failedStep: "marketplace_mcp",
          steps: prev.steps.map((s) =>
            s.status === "active"
              ? {
                  ...s,
                  status: "error" as const,
                  error: err instanceof Error ? err.message : String(err),
                }
              : s,
          ),
        };
      });
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className={styles.panel}>
      <div className={styles.segmentRow}>
        <div className={styles.segments} role="tablist" aria-label="Workflow mode">
          <span className={styles.segment}>Inspect</span>
          <span className={styles.segmentActive}>Marketplace</span>
          <span className={styles.segment}>x402</span>
        </div>
        <div className={styles.filters}>
          <span className={styles.filterChip}>lifi</span>
          <span className={styles.filterChip}>1inch</span>
          <span className={styles.filterChip}>min score ≥ 0.90</span>
        </div>
      </div>

      <h2 className={styles.panelTitle}>Execution Sandbox</h2>
      <p className={styles.panelSub}>
        User @Permit trade intent → Marketplace MCP → x402 price gate → USDC settlement on Arc.
      </p>

      <div className={styles.promptGrid}>
        {DEMO_PROMPTS.map((prompt) => {
          const active = selectedPrompt === prompt.text;
          return (
            <button
              key={prompt.id}
              type="button"
              onClick={() => selectPrompt(prompt.text)}
              className={active ? styles.promptBtnActive : styles.promptBtn}
            >
              {prompt.text}
            </button>
          );
        })}
      </div>

      {parseError && <p className={styles.parseError}>Intent parse error: {parseError}</p>}

      {intent && (
        <>
          <IntentSummary intent={intent} />
          <button
            type="button"
            onClick={handleStartWorkflow}
            disabled={loading}
            className={styles.primaryBtn}
          >
            {loading ? "Running pipeline…" : "Start Workflow"}
          </button>
        </>
      )}

      <FlightTracker pipeline={pipeline} />
    </section>
  );
}
