import { fetchManifest, type ScoreManifest } from "@/lib/data";

export const dynamic = "force-dynamic";

export default async function MCPDetailPage({
  params,
}: {
  params: Promise<{ mcp: string; capability: string }>;
}) {
  const { mcp, capability } = await params;
  let manifest: ScoreManifest | undefined;
  let error = "";
  try {
    manifest = await fetchManifest(mcp, capability);
  } catch (e) {
    error = e instanceof Error ? e.message : String(e);
  }

  return (
    <div>
      <h1>
        {mcp} / {capability}
      </h1>
      {error && <p style={{ color: "#f66" }}>Error: {error}</p>}
      {manifest && (
        <div>
          {manifest.failed && (
            <p style={{ color: "#f66", fontWeight: "bold" }}>
              BINARY FAIL: {manifest.fail_reason}
            </p>
          )}
          <dl>
            <dt>DataScore</dt>
            <dd>{((manifest.data_score ?? 0) * 100).toFixed(1)}%</dd>
            <dt>PathScore</dt>
            <dd>{((manifest.path_score ?? 0) * 100).toFixed(1)}%</dd>
            <dt>TokenEfficiency</dt>
            <dd>{((manifest.token_efficiency ?? 0) * 100).toFixed(1)}%</dd>
            <dt>Composite</dt>
            <dd>{((manifest.composite ?? 0) * 100).toFixed(1)}%</dd>
            <dt>Walrus Blob</dt>
            <dd>
              <code>{manifest.walrus_blob_id || manifest.walrus_manifest_blob_id}</code>
            </dd>
          </dl>
          <p style={{ margin: "1rem 0" }}>
            <a
              href={`/mcp/${mcp}/${capability}/eval`}
              style={{
                display: "inline-block",
                background: "#1d4ed8",
                color: "#fff",
                padding: "0.6rem 1rem",
                borderRadius: 6,
                textDecoration: "none",
                fontWeight: 600,
              }}
            >
              View Inspect Eval Log &rarr;
            </a>
            <span style={{ color: "#888", marginLeft: "0.75rem", fontSize: "0.85rem" }}>
              Opens the official Inspect AI viewer for the real <code>.eval</code> run.
            </span>
          </p>
          <h2>CAI Judge Report (Score Manifest)</h2>
          <p style={{ color: "#888", margin: "0 0 0.5rem", fontSize: "0.85rem" }}>
            Chainlink CAI judge attestation and computed scores — not the raw Inspect
            eval log (use the button above for that).
          </p>
          <pre style={{ background: "#111", padding: "1rem", overflow: "auto", fontSize: "0.85rem" }}>
            {JSON.stringify(manifest, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}
