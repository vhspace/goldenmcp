import Link from "next/link";
import {
  formatLatencyMs,
  goldenScoreBadge,
  latencyMeterValue,
  meterColor,
  type VendorProfile,
} from "@/lib/vendors";

const METER_COLORS: Record<ReturnType<typeof meterColor>, string> = {
  green: "#34d399",
  yellow: "#fbbf24",
  red: "#f87171",
};

const TIER_COLORS: Record<ReturnType<typeof goldenScoreBadge>["tier"], string> = {
  excellent: "#34d399",
  good: "#7eb8ff",
  warning: "#fbbf24",
  critical: "#f87171",
};

function ScoreMeter({
  label,
  value,
  display,
}: {
  label: string;
  value: number;
  display: string;
}) {
  const color = METER_COLORS[meterColor(value)];
  const pct = Math.round(Math.max(0, Math.min(1, value)) * 100);
  return (
    <div style={{ marginTop: "0.75rem" }}>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.8rem", color: "#aaa" }}>
        <span>{label}</span>
        <span>{display}</span>
      </div>
      <div
        style={{
          marginTop: "0.25rem",
          height: "8px",
          borderRadius: "4px",
          background: "#222",
          overflow: "hidden",
        }}
      >
        <div
          style={{
            width: `${pct}%`,
            height: "100%",
            background: color,
            borderRadius: "4px",
          }}
        />
      </div>
    </div>
  );
}

export function VendorPerformanceCard({ vendor }: { vendor: VendorProfile }) {
  const badge = goldenScoreBadge(vendor.goldenScore);
  const latencyValue =
    vendor.latencyMs !== null ? latencyMeterValue(vendor.latencyMs) : null;

  return (
    <article
      style={{
        background: "linear-gradient(145deg, #12121a 0%, #0d0d14 100%)",
        border: "1px solid #2a2a38",
        borderRadius: "12px",
        padding: "1.25rem",
        display: "flex",
        flexDirection: "column",
        minHeight: "280px",
      }}
    >
      <header>
        <h2 style={{ margin: 0, fontSize: "1.1rem", fontWeight: 600 }}>{vendor.vendorName}</h2>
        <p style={{ margin: "0.25rem 0 0", color: "#888", fontSize: "0.85rem" }}>
          {vendor.mcp} · {vendor.primaryCapability}
          {vendor.attested && (
            <span style={{ marginLeft: "0.5rem", color: "#34d399" }}>✓ TEE attested</span>
          )}
        </p>
      </header>

      <div
        style={{
          margin: "1.25rem 0",
          textAlign: "center",
          padding: "1rem",
          borderRadius: "8px",
          background: "#0a0a10",
          border: `1px solid ${TIER_COLORS[badge.tier]}33`,
        }}
      >
        <div
          style={{
            fontSize: "2.5rem",
            fontWeight: 700,
            color: TIER_COLORS[badge.tier],
            lineHeight: 1,
          }}
        >
          {badge.percent}%
        </div>
        <div style={{ color: TIER_COLORS[badge.tier], fontWeight: 600, marginTop: "0.25rem" }}>
          Golden Score · {badge.label}
        </div>
        {vendor.failed && (
          <div style={{ color: "#f87171", fontSize: "0.8rem", marginTop: "0.5rem" }}>Binary fail</div>
        )}
      </div>

      <ScoreMeter
        label="Cost Efficiency"
        value={vendor.costEfficiency}
        display={`${Math.round(vendor.costEfficiency * 100)}%`}
      />
      {latencyValue !== null ? (
        <ScoreMeter
          label="Latency"
          value={latencyValue}
          display={formatLatencyMs(vendor.latencyMs)}
        />
      ) : (
        <p style={{ color: "#f87171", fontSize: "0.75rem", marginTop: "0.75rem" }}>
          Latency unavailable: {vendor.latencyError ?? "eval log has no timing stats"}
        </p>
      )}
      <ScoreMeter
        label="Reliability"
        value={vendor.reliability}
        display={`${Math.round(vendor.reliability * 100)}%`}
      />

      {vendor.ensError && (
        <p style={{ color: "#f87171", fontSize: "0.75rem", marginTop: "0.75rem" }}>ENS: {vendor.ensError}</p>
      )}
      {vendor.ensRecords && (
        <p style={{ color: "#6ee7a8", fontSize: "0.75rem", marginTop: "0.5rem" }}>
          ENS verified · {Object.keys(vendor.ensRecords).join(", ")}
        </p>
      )}

      <footer style={{ marginTop: "auto", paddingTop: "1rem" }}>
        <Link
          href={`/mcp/${vendor.mcp}/${vendor.primaryCapability}`}
          style={{ color: "#7eb8ff", fontSize: "0.85rem", textDecoration: "none" }}
        >
          View eval report →
        </Link>
      </footer>
    </article>
  );
}
