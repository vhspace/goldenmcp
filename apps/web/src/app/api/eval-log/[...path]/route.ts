import { fetchManifest, resolveEvalLogUrl } from "@/lib/data";
import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

/**
 * Stream the raw Inspect `.eval` log (a ZIP archive) for an MCP/capability.
 *
 *   GET /api/eval-log/<mcp>/<capability>.eval
 *
 * Two viewer requirements drive this route:
 *  - The viewer picks ZIP vs JSON parsing by URL extension, so the path ends in
 *    `.eval` (not a query string).
 *  - The viewer reads the ZIP via HTTP Range requests: it fetches Content-Length,
 *    then requests byte ranges for the end-of-central-directory + entries. So we
 *    must advertise Content-Length + Accept-Ranges and honor Range with a 206.
 *
 * Walrus blobs aren't range-addressable here, so we buffer the whole `.eval`
 * (they are small — tens of KB) and slice locally.
 */
function baseHeaders(mcp: string, capability: string, length: number): HeadersInit {
  return {
    "Content-Type": "application/zip",
    "Content-Disposition": `inline; filename="${mcp}_${capability}.eval"`,
    "Accept-Ranges": "bytes",
    "Cache-Control": "public, max-age=300",
    "Content-Length": String(length),
  };
}

export async function GET(
  request: Request,
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
    const full = new Uint8Array(await upstream.arrayBuffer());
    const total = full.byteLength;

    // Honor a single byte range (the viewer's ZIP reader uses `bytes=start-end`).
    const range = request.headers.get("range");
    const match = range && /^bytes=(\d*)-(\d*)$/.exec(range.trim());
    if (match) {
      const startRaw = match[1];
      const endRaw = match[2];
      let start = startRaw ? Number(startRaw) : 0;
      let end = endRaw ? Number(endRaw) : total - 1;
      if (!startRaw && endRaw) {
        // suffix range: last N bytes
        start = Math.max(0, total - Number(endRaw));
        end = total - 1;
      }
      if (Number.isNaN(start) || Number.isNaN(end) || start > end || start >= total) {
        return new NextResponse(null, {
          status: 416,
          headers: { "Content-Range": `bytes */${total}`, "Accept-Ranges": "bytes" },
        });
      }
      end = Math.min(end, total - 1);
      const slice = full.subarray(start, end + 1);
      return new NextResponse(slice, {
        status: 206,
        headers: {
          ...baseHeaders(mcp, capability, slice.byteLength),
          "Content-Range": `bytes ${start}-${end}/${total}`,
        },
      });
    }

    return new NextResponse(full, {
      status: 200,
      headers: baseHeaders(mcp, capability, total),
    });
  } catch (e) {
    const message = e instanceof Error ? e.message : String(e);
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
