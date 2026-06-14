import { NextResponse } from "next/server";
import type { ParsedIntent } from "@/lib/intent";
import type { ExecutionResult, MarketplaceMcpResult } from "@/lib/pipeline";
import {
  runMarketplaceMcpStep,
  runX402PriceStep,
  runX402SettlementStep,
} from "@/lib/pipeline-server";

type StepName = "marketplace-mcp" | "x402-price" | "x402-settlement";

interface StepRequestBody {
  intent?: ParsedIntent;
  vendor?: MarketplaceMcpResult;
  execution?: ExecutionResult;
}

export async function POST(
  request: Request,
  context: { params: Promise<{ step: string }> },
) {
  const { step } = await context.params;

  let body: StepRequestBody;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 });
  }

  try {
    switch (step as StepName) {
      case "marketplace-mcp": {
        const intent = body.intent;
        if (!intent?.marketplaceCapability || typeof intent.minReliabilityScore !== "number") {
          return NextResponse.json(
            { error: "intent with capability and minReliabilityScore required" },
            { status: 400 },
          );
        }
        const result = await runMarketplaceMcpStep(
          intent.marketplaceCapability,
          intent.minReliabilityScore,
        );
        return NextResponse.json({ step, status: "complete", detail: result });
      }

      case "x402-price": {
        const intent = body.intent;
        if (!intent?.marketplaceCapability || typeof intent.minReliabilityScore !== "number") {
          return NextResponse.json({ error: "intent required" }, { status: 400 });
        }
        const result = await runX402PriceStep(
          intent.marketplaceCapability,
          intent.minReliabilityScore,
        );
        return NextResponse.json({ step, status: "complete", detail: result });
      }

      case "x402-settlement": {
        if (!body.execution || !body.vendor) {
          return NextResponse.json(
            { error: "execution and vendor context required" },
            { status: 400 },
          );
        }
        const result = await runX402SettlementStep(body.execution, body.vendor);
        return NextResponse.json({ step, status: "complete", detail: result });
      }

      default:
        return NextResponse.json({ error: `Unknown pipeline step: ${step}` }, { status: 404 });
    }
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    return NextResponse.json({ step, status: "error", error: message }, { status: 502 });
  }
}
