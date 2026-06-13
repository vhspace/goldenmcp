/** Server-side pipeline step runners — real Arc, ENS, Walrus, marketplace (GH #82). */

import {
  fetchLeaderboard,
  fetchManifest,
  resolveENS,
} from "@/lib/data";
import type {
  BlockchainProofResult,
  EnsDiscoveryResult,
  ExecutionResult,
  TeeSandboxResult,
} from "@/lib/pipeline";

export async function runEnsDiscoveryStep(
  capability: string,
  minScore: number,
): Promise<EnsDiscoveryResult> {
  const entries = await fetchLeaderboard();
  const matches = entries.filter(
    (e) =>
      e.capability === capability &&
      !e.failed &&
      e.composite >= minScore &&
      Boolean(e.ensName?.trim()),
  );
  matches.sort((a, b) => b.composite - a.composite);

  if (matches.length === 0) {
    throw new Error(
      `No ENS-registered vendors for capability=${capability} with composite ≥ ${minScore} — run evals and register MCPs on Arc`,
    );
  }

  const best = matches[0];
  const ensRecords = await resolveENS(best.ensName);
  if (!ensRecords["agent-endpoint[mcp]"] && !ensRecords["agent-context"]) {
    throw new Error(
      `ENSIP-25/26 records missing for ${best.ensName} — expected agent-context and agent-endpoint[mcp]`,
    );
  }

  const pct = Math.round(best.composite * 100);
  return {
    ensName: best.ensName,
    mcp: best.mcp,
    capability: best.capability,
    composite: best.composite,
    mcpEndpoint: ensRecords["agent-endpoint[mcp]"] ?? "",
    ensRecords,
    summary: `Found ${best.ensName} with verified ${pct}% Golden Score`,
  };
}

export async function runTeeSandboxStep(vendor: EnsDiscoveryResult): Promise<TeeSandboxResult> {
  const entries = await fetchLeaderboard();
  const entry = entries.find(
    (e) => e.mcp === vendor.mcp && e.capability === vendor.capability && e.ensName === vendor.ensName,
  );

  let manifestAttestation: Record<string, unknown> | null = null;
  try {
    const manifest = await fetchManifest(vendor.mcp, vendor.capability);
    if (manifest.attestation && typeof manifest.attestation === "object") {
      manifestAttestation = manifest.attestation as Record<string, unknown>;
    }
  } catch {
    // Manifest may be unavailable; fall back to onchain attestation ref only.
  }

  const inferenceId =
    (entry?.attestationRef?.trim() || (manifestAttestation?.inference_id as string | undefined)) ??
    null;
  const verdict = (manifestAttestation?.verdict as string | undefined) ?? null;
  const transcriptHash =
    entry?.transcriptHash?.trim() ||
    (manifestAttestation?.transcript_hash as string | undefined) ||
    null;

  return {
    secured: Boolean(inferenceId),
    badge: "Secured via Hardware TEE (Gemma Sandboxed)",
    inferenceId,
    verdict,
    transcriptHash,
  };
}

export async function runExecutionStep(
  capability: string,
  minScore: number,
): Promise<ExecutionResult> {
  const marketplaceUrl =
    process.env.MARKETPLACE_URL ??
    process.env.NEXT_PUBLIC_MARKETPLACE_URL ??
    "http://localhost:8091";

  const evalRunnerUrl =
    process.env.EVAL_RUNNER_URL ??
    `http://${process.env.EVAL_RUNNER_HOST ?? "127.0.0.1"}:${process.env.EVAL_RUNNER_PORT ?? "8090"}`;

  const healthRes = await fetch(`${evalRunnerUrl.replace(/\/$/, "")}/health`, {
    signal: AbortSignal.timeout(5000),
  });
  if (!healthRes.ok) {
    throw new Error(
      `eval-runner health check failed: HTTP ${healthRes.status} ${await healthRes.text()}`,
    );
  }

  const lookupUrl = `${marketplaceUrl.replace(/\/$/, "")}/tools/lookup`;
  const lookupRes = await fetch(lookupUrl, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ capability, min_score: minScore }),
    signal: AbortSignal.timeout(30000),
  });

  const body = (await lookupRes.json().catch(() => ({}))) as Record<string, unknown>;

  if (lookupRes.status === 402) {
    return {
      httpStatus: 402,
      paymentRequired: true,
      priceUsdc: typeof body.price_usdc === "number" ? body.price_usdc : null,
      capability,
      minScore,
      results: null,
      payee: typeof body.payee === "string" ? body.payee : undefined,
      network: typeof body.network === "string" ? body.network : undefined,
    };
  }

  if (!lookupRes.ok) {
    const msg =
      (typeof body.error === "string" && body.error) ||
      (typeof body.detail === "string" && body.detail) ||
      `HTTP ${lookupRes.status}`;
    throw new Error(`Marketplace lookup failed: ${msg}`);
  }

  const results = Array.isArray(body.results)
    ? (body.results as Record<string, unknown>[])
    : null;

  return {
    httpStatus: lookupRes.status,
    paymentRequired: false,
    priceUsdc: typeof body.price_paid_usdc === "number" ? body.price_paid_usdc : null,
    capability,
    minScore,
    results,
  };
}

export async function runBlockchainProofStep(
  execution: ExecutionResult,
  vendor: EnsDiscoveryResult,
): Promise<BlockchainProofResult> {
  const registryAddress = process.env.NEXT_PUBLIC_REGISTRY_ADDRESS ?? null;

  if (execution.paymentRequired) {
    return {
      kind: "x402_settlement",
      payee: execution.payee ?? null,
      network: execution.network ?? "arc-testnet",
      priceUsdc: execution.priceUsdc,
      walrusBlobId: null,
      composite: null,
      registryAddress,
      summary: `Circle USDC micropayment ${execution.priceUsdc ?? "?"} USDC pending via x402 on ${execution.network ?? "arc-testnet"}`,
    };
  }

  const top = execution.results?.[0];
  const walrusBlobId = (top?.walrus_blob_id as string | undefined) ?? null;
  const composite = typeof top?.composite === "number" ? top.composite : vendor.composite;

  return {
    kind: "onchain_scores",
    payee: null,
    network: "arc-testnet",
    priceUsdc: execution.priceUsdc,
    walrusBlobId,
    composite,
    registryAddress,
    summary: walrusBlobId
      ? `Score manifest on Walrus (${walrusBlobId.slice(0, 12)}…) · composite ${(composite * 100).toFixed(0)}%`
      : `Matched ${vendor.ensName} at composite ${(composite * 100).toFixed(0)}%`,
  };
}
