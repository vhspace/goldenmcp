import { fetchManifest, resolveEvalLogUrl, type ScoreManifest } from "@/lib/data";

export const dynamic = "force-dynamic";

// Set NEXT_PUBLIC_INSPECT_VIEWER_URL to a hosted `inspect view bundle` viewer
// (its index.html). If unset, defaults to a self-hosted bundle committed under
// apps/web/public/inspect-viewer/ (see footer note for how to generate it).
// The bundled viewer deep-links a single log via the `?log_file=<url>` param.
function inspectViewerBase(): string {
  return (
    process.env.NEXT_PUBLIC_INSPECT_VIEWER_URL?.trim() ||
    "/inspect-viewer/index.html"
  );
}

export default async function EvalViewerPage({
  params,
}: {
  params: Promise<{ mcp: string; capability: string }>;
}) {
  const { mcp, capability } = await params;
  let manifest: ScoreManifest | undefined;
  let logUrl = "";
  let error = "";
  try {
    manifest = await fetchManifest(mcp, capability);
    logUrl = await resolveEvalLogUrl(manifest);
  } catch (e) {
    error = e instanceof Error ? e.message : String(e);
  }

  // Same-origin proxy so the Inspect viewer can fetch the .eval without CORS
  // and so walrus:// indexed paths resolve server-side.
  const proxyLogUrl = `/api/eval-log?mcp=${encodeURIComponent(mcp)}&capability=${encodeURIComponent(
    capability,
  )}`;
  const viewerSrc = `${inspectViewerBase()}?log_file=${encodeURIComponent(proxyLogUrl)}`;

  return (
    <div>
      <p style={{ marginBottom: "0.5rem" }}>
        <a href={`/mcp/${mcp}/${capability}`} style={{ color: "#7eb8ff" }}>
          &larr; Back to {mcp} / {capability}
        </a>
      </p>
      <h1 style={{ marginTop: 0 }}>
        Inspect Eval Log — {mcp} / {capability}
      </h1>

      {error && (
        <div
          style={{
            background: "#2a1010",
            border: "1px solid #f87171",
            borderRadius: 8,
            padding: "1rem",
            marginBottom: "1rem",
          }}
        >
          <strong>Could not resolve the eval log.</strong>
          <p style={{ margin: "0.5rem 0 0", color: "#f9a8a8" }}>{error}</p>
        </div>
      )}

      {!error && (
        <>
          <p style={{ color: "#aaa", margin: "0 0 0.75rem" }}>
            Rendering the official Inspect AI log viewer for the real{" "}
            <code>.eval</code> log on Walrus.{" "}
            <a href={logUrl} style={{ color: "#7eb8ff" }} target="_blank" rel="noreferrer">
              Download raw .eval
            </a>
          </p>
          <iframe
            src={viewerSrc}
            title="Inspect eval log viewer"
            style={{
              width: "100%",
              height: "80vh",
              border: "1px solid #222",
              borderRadius: 8,
              background: "#fff",
            }}
          />
          <p style={{ color: "#666", fontSize: "0.8rem", marginTop: "0.5rem" }}>
            Viewer:{" "}
            <code>{inspectViewerBase()}</code>. To self-host, run{" "}
            <code>inspect view bundle --log-dir logs --output-dir apps/web/public/inspect-viewer</code>{" "}
            and commit the output, or set <code>NEXT_PUBLIC_INSPECT_VIEWER_URL</code>.
          </p>
        </>
      )}
    </div>
  );
}
