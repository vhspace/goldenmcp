"use client";

import { useEffect, useState } from "react";
import type { PipelineRunState, PipelineStepState } from "@/lib/pipeline";

const STATUS_COLORS = {
  pending: "#333",
  active: "#7eb8ff",
  complete: "#34d399",
  error: "#f87171",
} as const;

function SettlementPulse() {
  return (
    <div
      aria-hidden
      style={{
        marginTop: "0.5rem",
        height: "4px",
        borderRadius: "999px",
        background: "linear-gradient(90deg, #fbbf24, #fde68a, #fbbf24)",
        backgroundSize: "200% 100%",
        animation: "x402-pulse 1.4s ease-in-out infinite",
      }}
    />
  );
}

function TeeBadge({ inferenceId }: { inferenceId: string }) {
  return (
    <div style={{ marginTop: "0.5rem" }}>
      <span
        style={{
          display: "inline-block",
          padding: "0.25rem 0.5rem",
          borderRadius: "4px",
          background: "#1a2a1a",
          border: "1px solid #34d399",
          color: "#6ee7a8",
          fontWeight: 600,
          fontSize: "0.75rem",
        }}
      >
        Secured via Hardware TEE (Gemma Sandboxed)
      </span>
      <p style={{ margin: "0.35rem 0 0", color: "#888", fontSize: "0.75rem" }}>
        CAI inference <code>{inferenceId.slice(0, 18)}…</code>
      </p>
    </div>
  );
}

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
    const ensRecords =
      d.ensRecords && typeof d.ensRecords === "object"
        ? (d.ensRecords as Record<string, string>)
        : null;
    const selected = candidates.find((c: Record<string, unknown>) => c.mcp === d.mcp);
    const attestationRef =
      typeof selected?.attestationRef === "string" ? selected.attestationRef : "";

    return (
      <div style={{ marginTop: "0.5rem", fontSize: "0.8rem", color: "#aaa" }}>
        <p style={{ margin: 0, color: "#6ee7a8" }}>{d.summary}</p>
        {typeof d.ensName === "string" && d.ensName ? (
          <p style={{ margin: "0.35rem 0 0", color: "#888" }}>
            ENSIP-25/26 · <code>{d.ensName}</code>
          </p>
        ) : null}
        {ensRecords ? (
          <ul style={{ margin: "0.25rem 0 0", paddingLeft: "1.1rem" }}>
            {Object.keys(ensRecords).map((key) => (
              <li key={key}>{key}</li>
            ))}
          </ul>
        ) : null}
        {candidates.length > 0 ? (
          <ul style={{ margin: "0.35rem 0 0", paddingLeft: "1.1rem" }}>
            {candidates.map((c: Record<string, unknown>) => (
              <li key={String(c.mcp)}>
                {String(c.mcp)} — {Math.round(Number(c.composite) * 100)}%
              </li>
            ))}
          </ul>
        ) : null}
        {attestationRef ? <TeeBadge inferenceId={attestationRef} /> : null}
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
            Circle USDC micropayment on {String(d.network ?? "arc-testnet")}
            {d.payee ? (
              <>
                {" "}
                → <code>{String(d.payee).slice(0, 10)}…</code>
              </>
            ) : null}
          </p>
        ) : null}
      </div>
    );
  }

  if (step.id === "x402_settlement" && typeof d.summary === "string") {
    const paymentPending = d.status === "payment_required";
    return (
      <div style={{ marginTop: "0.5rem", fontSize: "0.8rem", color: "#aaa" }}>
        <p style={{ margin: 0 }}>{d.summary}</p>
        {paymentPending && d.priceUsdc !== null && d.priceUsdc !== undefined ? (
          <p style={{ margin: "0.35rem 0 0", color: "#fde68a" }}>
            ${String(d.priceUsdc)} USDC settlement loop on Arc
          </p>
        ) : null}
        {paymentPending ? <SettlementPulse /> : null}
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
  const isSettlementLoop =
    step.id === "x402_settlement" &&
    step.status === "complete" &&
    step.detail?.status === "payment_required";

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
            border: `1px solid ${isSettlementLoop ? "#fbbf24" : color}`,
            background: step.status === "active" ? "#12182a" : "#0d0d14",
            color: "#e8e8ef",
            cursor: "pointer",
            boxShadow:
              step.status === "active" || isSettlementLoop
                ? `0 0 12px ${isSettlementLoop ? "#fbbf2444" : `${color}44`}`
                : "none",
          }}
        >
          <div style={{ fontSize: "0.7rem", color: "#888", textTransform: "uppercase" }}>{step.shortLabel}</div>
          <div style={{ fontWeight: 600, fontSize: "0.85rem", marginTop: "0.15rem" }}>{step.label}</div>
          <div style={{ fontSize: "0.7rem", marginTop: "0.25rem", color: isSettlementLoop ? "#fde68a" : color }}>
            {isSettlementLoop ? "awaiting USDC" : step.status}
          </div>
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

  useEffect(() => {
    if (!pipeline?.activeStep) return;
    setExpanded((prev) => ({ ...prev, [pipeline.activeStep!]: true }));
  }, [pipeline?.activeStep]);

  if (!pipeline) return null;

  const hasStarted = pipeline.steps.some((s) => s.status !== "pending");

  if (!hasStarted) return null;

  return (
    <section style={{ marginTop: "1.5rem" }}>
      <style>{`
        @keyframes x402-pulse {
          0%, 100% { background-position: 0% 50%; opacity: 0.85; }
          50% { background-position: 100% 50%; opacity: 1; }
        }
      `}</style>
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
