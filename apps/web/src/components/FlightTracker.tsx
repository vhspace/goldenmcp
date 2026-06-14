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

  if (step.id === "ens_discovery" && typeof d.summary === "string") {
    return (
      <div style={{ marginTop: "0.5rem", fontSize: "0.8rem", color: "#aaa" }}>
        <p style={{ margin: 0, color: "#6ee7a8" }}>{d.summary}</p>
        {d.ensRecords && typeof d.ensRecords === "object" ? (
          <ul style={{ margin: "0.35rem 0 0", paddingLeft: "1.1rem" }}>
            {Object.keys(d.ensRecords as Record<string, string>).map((key) => (
              <li key={key}>{key}</li>
            ))}
          </ul>
        ) : null}
      </div>
    );
  }

  if (step.id === "tee_sandbox") {
    return (
      <div style={{ marginTop: "0.5rem", fontSize: "0.8rem" }}>
        <span
          style={{
            display: "inline-block",
            padding: "0.25rem 0.5rem",
            borderRadius: "4px",
            background: "#1a2a1a",
            border: "1px solid #34d399",
            color: "#6ee7a8",
            fontWeight: 600,
          }}
        >
          {String(d.badge ?? "Secured via Hardware TEE (Gemma Sandboxed)")}
        </span>
        {d.inferenceId ? (
          <p style={{ margin: "0.35rem 0 0", color: "#888" }}>
            inference <code>{String(d.inferenceId).slice(0, 16)}…</code>
          </p>
        ) : (
          <p style={{ margin: "0.35rem 0 0", color: "#fbbf24" }}>No CAI attestation on record yet</p>
        )}
      </div>
    );
  }

  if (step.id === "execution_engine" && d.paymentRequired) {
    return (
      <p style={{ margin: "0.5rem 0 0", color: "#fbbf24", fontSize: "0.8rem" }}>
        x402 payment gate — {String(d.priceUsdc ?? "?")} USDC on {String(d.network ?? "arc-testnet")}
      </p>
    );
  }

  if (step.id === "blockchain_proof" && typeof d.summary === "string") {
    return (
      <div style={{ marginTop: "0.5rem", fontSize: "0.8rem", color: "#aaa" }}>
        <p style={{ margin: 0 }}>{d.summary}</p>
        {d.registryAddress ? (
          <p style={{ margin: "0.25rem 0 0" }}>
            Registry{" "}
            <code>{String(d.registryAddress).slice(0, 10)}…</code>
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
      <h3 style={{ margin: "0 0 1rem", fontSize: "1rem", color: "#ccc" }}>Live Flight Tracker</h3>
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
