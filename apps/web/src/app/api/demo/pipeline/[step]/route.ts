import { NextResponse } from "next/server";
import type { ParsedIntent } from "@/lib/intent";
import type { EnsDiscoveryResult, ExecutionResult } from "@/lib/pipeline";
import {
  runBlockchainProofStep,
  runEnsDiscoveryStep,
  runExecutionStep,
  runTeeSandboxStep,
} from "@/lib/pipeline-server";

type StepName = "ens-discovery" | "tee-sandbox" | "execute" | "blockchain-proof";

interface StepRequestBody {
  intent?: ParsedIntent;
  vendor?: EnsDiscoveryResult;
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
      case "ens-discovery": {
        const intent = body.intent;
        if (!intent?.marketplaceCapability || typeof intent.minReliabilityScore !== "number") {
          return NextResponse.json({ error: "intent with capability and minReliabilityScore required" }, { status: 400 });
        }
        const result = await runEnsDiscoveryStep(
          intent.marketplaceCapability,
          intent.minReliabilityScore,
        );
        return NextResponse.json({ step, status: "complete", detail: result });
      }

      case "tee-sandbox": {
        if (!body.vendor) {
          return NextResponse.json({ error: "vendor context required" }, { status: 400 });
        }
        const result = await runTeeSandboxStep(body.vendor);
        return NextResponse.json({ step, status: "complete", detail: result });
      }

      case "execute": {
        const intent = body.intent;
        if (!intent?.marketplaceCapability || typeof intent.minReliabilityScore !== "number") {
          return NextResponse.json({ error: "intent required" }, { status: 400 });
        }
        const result = await runExecutionStep(
          intent.marketplaceCapability,
          intent.minReliabilityScore,
        );
        return NextResponse.json({ step, status: "complete", detail: result });
      }

      case "blockchain-proof": {
        if (!body.execution || !body.vendor) {
          return NextResponse.json({ error: "execution and vendor context required" }, { status: 400 });
        }
        const result = await runBlockchainProofStep(body.execution, body.vendor);
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
