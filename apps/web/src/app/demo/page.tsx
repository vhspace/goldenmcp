import { fetchVendorProfiles } from "@/lib/data";
import { VendorPerformanceCard } from "@/components/VendorPerformanceCard";
import { GOLDEN_SCORE_THRESHOLDS, METER_THRESHOLDS, type VendorProfile } from "@/lib/vendors";

export const dynamic = "force-dynamic";

export default async function DemoPage() {
  let vendors: VendorProfile[] = [];
  let error = "";

  try {
    vendors = await fetchVendorProfiles();
  } catch (e) {
    error = e instanceof Error ? e.message : String(e);
  }

  return (
    <div>
      <header style={{ marginBottom: "2rem" }}>
        <h1 style={{ margin: 0 }}>Global Overview Room</h1>
        <p style={{ color: "#aaa", marginTop: "0.5rem", maxWidth: "52rem" }}>
          Consumer-friendly MCP marketplace registry — vendors discovered via live ENS (ENSIP-25/26)
          with K=3 Golden Scores from Arc registry and Walrus manifests.
        </p>
      </header>

      {error && (
        <div
          style={{
            background: "#2a1010",
            border: "1px solid #f87171",
            borderRadius: "8px",
            padding: "1rem",
            marginBottom: "1.5rem",
            color: "#fca5a5",
          }}
        >
          <strong>Marketplace unavailable</strong>
          <p style={{ margin: "0.5rem 0 0", fontFamily: "monospace", fontSize: "0.85rem" }}>{error}</p>
        </div>
      )}

      {vendors.length === 0 && !error && (
        <p style={{ color: "#888" }}>No registered vendors — run evals and register MCPs on Arc first.</p>
      )}

      {vendors.length > 0 && (
        <>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))",
              gap: "1.25rem",
            }}
          >
            {vendors.map((vendor) => (
              <VendorPerformanceCard key={`${vendor.vendorName}-${vendor.mcp}`} vendor={vendor} />
            ))}
          </div>

          <aside
            style={{
              marginTop: "2.5rem",
              padding: "1rem",
              background: "#111",
              borderRadius: "8px",
              border: "1px solid #222",
              fontSize: "0.8rem",
              color: "#888",
            }}
          >
            <strong style={{ color: "#ccc" }}>Score thresholds</strong>
            <ul style={{ margin: "0.5rem 0 0", paddingLeft: "1.25rem" }}>
              <li>
                Golden Score: Excellent ≥ {GOLDEN_SCORE_THRESHOLDS.excellentMin * 100}%, Good ≥{" "}
                {GOLDEN_SCORE_THRESHOLDS.goodMin * 100}%, Warning ≥{" "}
                {GOLDEN_SCORE_THRESHOLDS.warningMin * 100}%
              </li>
              <li>
                Meters: Green ≥ {METER_THRESHOLDS.greenMin * 100}%, Yellow ≥{" "}
                {METER_THRESHOLDS.yellowMin * 100}%, Red below
              </li>
              <li>Cost Efficiency = token optimization · Reliability = data correctness · Latency from Inspect eval log stats</li>
            </ul>
          </aside>
        </>
      )}
    </div>
  );
}
