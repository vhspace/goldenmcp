import { NextResponse } from "next/server";
import { evalRunnerUrl, marketplaceUrl } from "@/lib/web-env";

export async function POST(request: Request) {
  let body: { capability?: string; min_score?: number };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 });
  }

  const capability = body.capability?.trim();
  const minScore = body.min_score;

  if (!capability) {
    return NextResponse.json({ error: "capability is required" }, { status: 400 });
  }
  if (typeof minScore !== "number" || minScore < 0 || minScore > 1) {
    return NextResponse.json({ error: "min_score must be a number between 0 and 1" }, { status: 400 });
  }

  const runnerUrl = evalRunnerUrl();
  const marketUrl = marketplaceUrl();

  try {
    const healthRes = await fetch(`${runnerUrl}/health`, {
      signal: AbortSignal.timeout(5000),
    });
    if (!healthRes.ok) {
      return NextResponse.json(
        {
          error: `eval-runner health check failed: HTTP ${healthRes.status} ${await healthRes.text()}`,
        },
        { status: 502 },
      );
    }
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    return NextResponse.json(
      {
        error: `eval-runner unreachable at ${runnerUrl} — ${msg}. Set EVAL_RUNNER_PUBLIC_URL on Vercel.`,
      },
      { status: 502 },
    );
  }

  const lookupUrl = `${marketUrl}/tools/lookup`;

  try {
    const lookupRes = await fetch(lookupUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ capability, min_score: minScore }),
      signal: AbortSignal.timeout(30000),
    });

    const lookupBody = await lookupRes.json().catch(() => ({}));

    if (lookupRes.status === 402) {
      return NextResponse.json(lookupBody, { status: 402 });
    }

    if (!lookupRes.ok) {
      return NextResponse.json(
        {
          error: lookupBody.detail ?? lookupBody.error ?? `Marketplace lookup HTTP ${lookupRes.status}`,
          marketplace_url: lookupUrl,
        },
        { status: lookupRes.status },
      );
    }

    return NextResponse.json(lookupBody);
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    return NextResponse.json(
      {
        error: `Marketplace unreachable at ${lookupUrl} — ${msg}. Set MARKETPLACE_URL on Vercel.`,
      },
      { status: 502 },
    );
  }
}
