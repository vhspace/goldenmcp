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

function IntentSummary({ intent }: { intent: ParsedIntent }) {
  return (
    <div
      style={{
        marginTop: "1rem",
        padding: "1.25rem",
        background: "#0d0d14",
        border: "1px solid #3b3b50",
        borderRadius: "10px",
      }}
    >
      <h3 style={{ margin: "0 0 1rem", fontSize: "1rem", color: "#ccc" }}>Parsed Intent</h3>
      <dl style={{ margin: 0, display: "grid", gridTemplateColumns: "160px 1fr", gap: "0.6rem 1rem" }}>
        <dt style={{ color: "#888", margin: 0 }}>Action</dt>
        <dd style={{ margin: 0 }}>{intent.action}</dd>
        <dt style={{ color: "#888", margin: 0 }}>Assets</dt>
        <dd style={{ margin: 0 }}>{formatAssets(intent.assetsFrom, intent.assetsTo)}</dd>
        {intent.amountUsd !== null && (
          <>
            <dt style={{ color: "#888", margin: 0 }}>Amount</dt>
            <dd style={{ margin: 0 }}>${intent.amountUsd.toLocaleString()}</dd>
          </>
        )}
        <dt style={{ color: "#888", margin: 0 }}>Target Minimum Reliability Score</dt>
        <dd style={{ margin: 0 }}>{formatMinReliability(intent.minReliabilityScore)}</dd>
        <dt style={{ color: "#888", margin: 0 }}>Objective</dt>
        <dd style={{ margin: 0 }}>{intent.objective}</dd>
        <dt style={{ color: "#888", margin: 0 }}>Marketplace capability</dt>
        <dd style={{ margin: 0 }}>
          <code>{intent.marketplaceCapability}</code>
        </dd>
      </dl>
    </div>
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
          failedStep: "execution_engine",
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
    <section style={{ marginBottom: "3rem" }}>
      <header style={{ marginBottom: "1.25rem" }}>
        <h2 style={{ margin: 0, fontSize: "1.35rem" }}>Execution Sandbox</h2>
        <p style={{ color: "#aaa", marginTop: "0.35rem", maxWidth: "48rem" }}>
          Click a pre-baked demo prompt — orchestration parses intent into plain English, then runs the
          live pipeline with step-by-step flight tracking.
        </p>
      </header>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))",
          gap: "1rem",
        }}
      >
        {DEMO_PROMPTS.map((prompt) => {
          const active = selectedPrompt === prompt.text;
          return (
            <button
              key={prompt.id}
              type="button"
              onClick={() => selectPrompt(prompt.text)}
              style={{
                textAlign: "left",
                padding: "1rem",
                borderRadius: "10px",
                border: active ? "1px solid #7eb8ff" : "1px solid #2a2a38",
                background: active ? "#12182a" : "#101018",
                color: "#e8e8ef",
                cursor: "pointer",
                fontSize: "0.95rem",
                lineHeight: 1.45,
              }}
            >
              {prompt.text}
            </button>
          );
        })}
      </div>

      {parseError && (
        <p style={{ color: "#f87171", marginTop: "1rem", fontFamily: "monospace", fontSize: "0.85rem" }}>
          Intent parse error: {parseError}
        </p>
      )}

      {intent && (
        <>
          <IntentSummary intent={intent} />
          <button
            type="button"
            onClick={handleStartWorkflow}
            disabled={loading}
            style={{
              marginTop: "1rem",
              padding: "0.75rem 1.5rem",
              borderRadius: "8px",
              border: "none",
              background: loading ? "#444" : "#7eb8ff",
              color: "#0a0a0f",
              fontWeight: 600,
              cursor: loading ? "wait" : "pointer",
            }}
          >
            {loading ? "Running pipeline…" : "Start Workflow"}
          </button>
        </>
      )}

      <FlightTracker pipeline={pipeline} />
    </section>
  );
}
