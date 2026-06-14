import { fetchManifest, resolveEvalLogUrl } from "@/lib/data";
import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

/**
 * Stream the raw Inspect `.eval` log (a ZIP archive) for an MCP/capability.
 *
 * The Inspect bundled viewer picks its parser by file extension — it only treats
 * the bytes as a ZIP when the URL ends in `.eval`, else it JSON-parses (and chokes
 * on the ZIP's `PK` magic). So the path must end in `.eval`, not a query string:
 *
 *   GET /api/eval-log/<mcp>/<capability>.eval
 */
export async function GET(
  _request: Request,
  context: { params: Promise<{ path: string[] }> },
) {
  const { path } = await context.params;
  if (!Array.isArray(path) || path.length !== 2) {
    return NextResponse.json(
      { error: "expected /api/eval-log/<mcp>/<capability>.eval" },
      { status: 400 },
    );
  }
  const mcp = path[0];
  const capability = path[1].replace(/\.eval$/, "");
  if (!mcp || !capability) {
    return NextResponse.json({ error: "mcp and capability required" }, { status: 400 });
  }
  try {
    const manifest = await fetchManifest(mcp, capability);
    const url = await resolveEvalLogUrl(manifest);
    const upstream = await fetch(url);
    if (!upstream.ok) {
      return NextResponse.json(
        { error: `Walrus fetch failed: HTTP ${upstream.status}` },
        { status: 502 },
      );
    }
    const body = await upstream.arrayBuffer();
    return new NextResponse(body, {
      status: 200,
      headers: {
        // .eval files are ZIP archives (inspect-ai >= 0.3).
        "Content-Type": "application/zip",
        "Content-Disposition": `inline; filename="${mcp}_${capability}.eval"`,
        "Cache-Control": "public, max-age=300",
      },
    });
  } catch (e) {
    const message = e instanceof Error ? e.message : String(e);
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
