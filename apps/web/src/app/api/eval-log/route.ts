import { fetchManifest, resolveEvalLogUrl } from "@/lib/data";
import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";

/**
 * Stream the raw Inspect `.eval` log (a ZIP archive) for an MCP/capability.
 *
 * The Inspect bundled log viewer loads a log via its `?log_file=<url>` param.
 * We serve the bytes same-origin here so the viewer fetches without CORS and
 * so the manifest's `walrus://` indexed-path is resolved server-side.
 *
 * GET /api/eval-log?mcp=<name>&capability=<cap>
 */
export async function GET(request: NextRequest) {
  const mcp = request.nextUrl.searchParams.get("mcp");
  const capability = request.nextUrl.searchParams.get("capability");
  if (!mcp || !capability) {
    return NextResponse.json(
      { error: "mcp and capability query params required" },
      { status: 400 },
    );
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
