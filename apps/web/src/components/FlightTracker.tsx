"use client";

import { useState } from "react";
import type { PipelineRunState, PipelineStepState } from "@/lib/pipeline";

const STATUS_COLORS = {
  pending: "#333",
  active: "#7eb8ff",
  complete: "#34d399",
  error: "#f87171",
} as const;

function StepDetail({ step }: { step: PipelineStepState }) {
  if (step.status === "error") {
    return (
      <p style={{ margin: "0.5rem 0 0", color: "#f87171", fontSize: "0.8rem", fontFamily: "monospace" }}>
        {step.error}
      </p>
    );
  }
  if (!step.detail) return null;

  const d = step.detail;

  if (step.id === "user_trade_intent" && typeof d.summary === "string") {
    return (
      <div style={{ marginTop: "0.5rem", fontSize: "0.8rem", color: "#aaa" }}>
        <p style={{ margin: 0, color: "#6ee7a8" }}>{d.summary}</p>
        {d.permit ? (
          <p style={{ margin: "0.25rem 0 0", color: "#888" }}>
            {String(d.permit)} · min score {String(d.minReliabilityScore ?? "?")}
          </p>
        ) : null}
      </div>
    );
  }

  if (step.id === "marketplace_mcp" && typeof d.summary === "string") {
    const candidates = Array.isArray(d.candidates) ? d.candidates : [];
    return (
      <div style={{ marginTop: "0.5rem", fontSize: "0.8rem", color: "#aaa" }}>
        <p style={{ margin: 0, color: "#6ee7a8" }}>{d.summary}</p>
        {candidates.length > 0 ? (
          <ul style={{ margin: "0.35rem 0 0", paddingLeft: "1.1rem" }}>
            {candidates.map((c: Record<string, unknown>) => (
              <li key={String(c.mcp)}>
                {String(c.mcp)} — {Math.round(Number(c.composite) * 100)}%
              </li>
            ))}
          </ul>
        ) : null}
      </div>
    );
  }

  if (step.id === "x402_price") {
    return (
      <div style={{ marginTop: "0.5rem", fontSize: "0.8rem" }}>
        <span
          style={{
            display: "inline-block",
            padding: "0.25rem 0.5rem",
            borderRadius: "4px",
            background: "#2a2410",
            border: "1px solid #fbbf24",
            color: "#fde68a",
            fontWeight: 600,
          }}
        >
          {String(d.priceLabel ?? "x402 price gate")}
        </span>
        {d.paymentRequired ? (
          <p style={{ margin: "0.35rem 0 0", color: "#888" }}>
            USDC on {String(d.network ?? "arc-testnet")}
          </p>
        ) : null}
      </div>
    );
  }

  if (step.id === "x402_settlement" && typeof d.summary === "string") {
    return (
      <div style={{ marginTop: "0.5rem", fontSize: "0.8rem", color: "#aaa" }}>
        <p style={{ margin: 0 }}>{d.summary}</p>
        {d.demoRoute ? (
          <p style={{ margin: "0.25rem 0 0", color: "#6ee7a8" }}>
            Demo route → <code>{String(d.demoRoute)}</code>
          </p>
        ) : null}
        {d.registryAddress ? (
          <p style={{ margin: "0.25rem 0 0" }}>
            ERC-8004 registry <code>{String(d.registryAddress).slice(0, 10)}…</code>
          </p>
        ) : null}
      </div>
    );
  }

  return (
    <pre
      style={{
        marginTop: "0.5rem",
        fontSize: "0.7rem",
        overflow: "auto",
        color: "#888",
        maxHeight: "120px",
      }}
    >
      {JSON.stringify(step.detail, null, 2)}
    </pre>
  );
}

function PipelineNode({
  step,
  expanded,
  onToggle,
  isLast,
}: {
  step: PipelineStepState;
  expanded: boolean;
  onToggle: () => void;
  isLast: boolean;
}) {
  const color = STATUS_COLORS[step.status];

  return (
    <div style={{ display: "flex", alignItems: "flex-start", flex: isLast ? "0 0 auto" : "1 1 0" }}>
      <div style={{ flex: 1, minWidth: 0 }}>
        <button
          type="button"
          onClick={onToggle}
          style={{
            width: "100%",
            textAlign: "left",
            padding: "0.75rem",
            borderRadius: "10px",
            border: `1px solid ${color}`,
            background: step.status === "active" ? "#12182a" : "#0d0d14",
            color: "#e8e8ef",
            cursor: "pointer",
            boxShadow: step.status === "active" ? `0 0 12px ${color}44` : "none",
          }}
        >
          <div style={{ fontSize: "0.7rem", color: "#888", textTransform: "uppercase" }}>{step.shortLabel}</div>
          <div style={{ fontWeight: 600, fontSize: "0.85rem", marginTop: "0.15rem" }}>{step.label}</div>
          <div style={{ fontSize: "0.7rem", marginTop: "0.25rem", color }}>{step.status}</div>
        </button>
        {expanded && <StepDetail step={step} />}
      </div>
      {!isLast && (
        <div
          style={{
            alignSelf: "center",
            padding: "0 0.35rem",
            color: "#444",
            fontSize: "1.25rem",
            flexShrink: 0,
          }}
          aria-hidden
        >
          →
        </div>
      )}
    </div>
  );
}

export function FlightTracker({ pipeline }: { pipeline: PipelineRunState | null }) {
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});

  if (!pipeline) return null;

  const hasStarted = pipeline.steps.some((s) => s.status !== "pending");

  if (!hasStarted) return null;

  return (
    <section style={{ marginTop: "1.5rem" }}>
      <h3 style={{ margin: "0 0 1rem", fontSize: "1rem", color: "#ccc" }}>Usecase Workflow — Live Flight Tracker</h3>
      <div
        style={{
          display: "flex",
          gap: "0.25rem",
          overflowX: "auto",
          paddingBottom: "0.5rem",
        }}
      >
        {pipeline.steps.map((step, index) => (
          <PipelineNode
            key={step.id}
            step={step}
            expanded={Boolean(expanded[step.id])}
            onToggle={() => setExpanded((prev) => ({ ...prev, [step.id]: !prev[step.id] }))}
            isLast={index === pipeline.steps.length - 1}
          />
        ))}
      </div>
      {pipeline.failedStep && (
        <p style={{ color: "#f87171", fontSize: "0.85rem", marginTop: "0.75rem" }}>
          Pipeline halted at {pipeline.failedStep.replace(/_/g, " ")}
        </p>
      )}
    </section>
  );
}
