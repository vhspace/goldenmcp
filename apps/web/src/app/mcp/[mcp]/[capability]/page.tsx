import { fetchManifest } from "@/lib/data";

export const dynamic = "force-dynamic";

export default async function MCPDetailPage({
  params,
}: {
  params: Promise<{ mcp: string; capability: string }>;
}) {
  const { mcp, capability } = await params;
  let manifest;
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
            <dd>{(manifest.data_score * 100).toFixed(1)}%</dd>
            <dt>PathScore</dt>
            <dd>{(manifest.path_score * 100).toFixed(1)}%</dd>
            <dt>TokenEfficiency</dt>
            <dd>{(manifest.token_efficiency * 100).toFixed(1)}%</dd>
            <dt>Composite</dt>
            <dd>{(manifest.composite * 100).toFixed(1)}%</dd>
            <dt>Walrus Blob</dt>
            <dd>
              <code>{manifest.walrus_blob_id || manifest.walrus_manifest_blob_id}</code>
            </dd>
          </dl>
          <h2>Eval Report</h2>
          <pre style={{ background: "#111", padding: "1rem", overflow: "auto", fontSize: "0.85rem" }}>
            {JSON.stringify(manifest, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}
