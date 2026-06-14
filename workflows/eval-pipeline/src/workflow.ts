import {
  CronCapability,
  HTTPCapability,
  HTTPClient,
  handler,
  ok,
  Runner,
  text,
  type HTTPPayload,
  type Runtime,
} from "@chainlink/cre-sdk";
import { bytesToString } from "viem";
import {
  getCaiApiKey,
  getEvalRunnerApiKey,
  parseCaiAttestation,
  publishByInferenceId,
  registerCaiSubmitted,
  requireCaiAttestationFields,
  runEvalScore,
  runPipeline,
  shouldSkipCai,
  submitCaiInference,
  writeAttestationToArc,
  writeScoreToArc,
  type CaiStatus,
} from "./pipeline";
import type { Config, PipelineTarget } from "./types";

const httpClient = new HTTPClient();

function benchmarkKey(mcp: string, capability: string): string {
  return `${mcp}/${capability}`;
}

function filterBenchmarks(
  config: Config,
  items: Array<{ mcp: string; capability: string }>,
): Array<{ mcp: string; capability: string }> {
  const allowlist = config.benchmarkAllowlist?.filter(Boolean) ?? [];
  if (allowlist.length === 0) {
    return items;
  }
  const allowed = new Set(allowlist);
  return items.filter((bench) => allowed.has(benchmarkKey(bench.mcp, bench.capability)));
}

/**
 * Handler A per-target work in async (callback) mode: score the MCP, then submit
 * the manifest to CAI with cre_callback = this workflow's HTTP trigger, and return.
 * CAI's completion POST starts a fresh HTTP-trigger execution (handler B).
 */
async function submitForAttestation(runtime: Runtime<Config>, target: PipelineTarget): Promise<string> {
  const config = runtime.config;
  const evalRunnerApiKey = getEvalRunnerApiKey(runtime);
  const scored = await runEvalScore(runtime, target, evalRunnerApiKey);

  const caiApiKey = getCaiApiKey(runtime);
  if (!caiApiKey) {
    throw new Error("CHAINLINK_CAI_API_KEY secret required for callback (async) attestation mode");
  }
  // CAI POSTs only its status (no URL/query) to the trigger, so we register the
  // inference_id -> run_id mapping with the eval-runner; handler B resolves it.
  const inferenceId = submitCaiInference(runtime, scored.manifest, caiApiKey, config.creCallbackUrl);
  registerCaiSubmitted(runtime, inferenceId, scored.run_id, evalRunnerApiKey);
  runtime.log(
    `submitForAttestation ${target.mcp}/${target.capability} run_id=${scored.run_id} inference_id=${inferenceId}`,
  );
  return `${target.mcp}/${target.capability}:queued:${inferenceId}`;
}

async function onCronTrigger(runtime: Runtime<Config>): Promise<string> {
  const config = runtime.config;
  runtime.log("GoldenMCP eval pipeline cron triggered");

  const benchmarksResponse = httpClient
    .sendRequest(runtime, {
      url: `${config.evalRunnerUrl.replace(/\/$/, "")}/benchmarks`,
      method: "GET",
    })
    .result();

  if (!ok(benchmarksResponse)) {
    throw new Error(
      `GET /benchmarks failed: HTTP ${benchmarksResponse.statusCode} — ${text(benchmarksResponse)}`,
    );
  }

  const benchmarks = JSON.parse(text(benchmarksResponse)) as {
    benchmarks?: Array<{ mcp: string; capability: string }>;
  };
  const allItems = benchmarks.benchmarks ?? [];
  const items = filterBenchmarks(config, allItems);
  if (items.length !== allItems.length) {
    runtime.log(
      `benchmarkAllowlist active — running ${items.length}/${allItems.length} benchmarks: ${items.map((b) => benchmarkKey(b.mcp, b.capability)).join(", ")}`,
    );
  } else {
    runtime.log(`Found ${items.length} benchmarks`);
  }

  if (config.useScoreOnly && items.length === 0) {
    throw new Error(
      "useScoreOnly=true but no benchmarks matched benchmarkAllowlist — set allowlist e.g. lifi/quote",
    );
  }

  // Async (callback) mode: submit CAI inference per target and return; the HTTP
  // trigger (handler B) finishes the pipeline when CAI calls back. Falls back to
  // the inline poll-based runPipeline when CAI / callback is unconfigured.
  const asyncMode = Boolean(config.creCallbackUrl?.trim()) && !shouldSkipCai(config, getCaiApiKey(runtime));

  const results: string[] = [];
  for (const bench of items) {
    runtime.log(`Processing ${bench.mcp}/${bench.capability} (${asyncMode ? "async-callback" : "inline"})`);
    const target: PipelineTarget = {
      mcp: bench.mcp,
      capability: bench.capability,
      agentId: config.defaultAgentId,
    };
    if (asyncMode) {
      results.push(await submitForAttestation(runtime, target));
    } else {
      const result = await runPipeline(runtime, target);
      results.push(`${bench.mcp}/${bench.capability}:${result.manifest.composite}`);
    }
  }

  return `Pipeline ${asyncMode ? "submitted" : "complete"}: ${results.join(", ")}`;
}

/**
 * Handler B: CAI's cre_callback POSTs the completed inference status here (the
 * trigger payload is only the body — no URL/query). Build the attestation from
 * the status, then resolve the run via the CAI inference_id (the eval-runner
 * holds the inference_id -> run_id map), publish to Walrus, and write to Arc.
 * This is a fresh execution started by the callback.
 */
async function onAttestationCallback(
  runtime: Runtime<Config>,
  payload: HTTPPayload,
): Promise<string> {
  const config = runtime.config;
  const wrapper = JSON.parse(bytesToString(payload.input)) as { input?: CaiStatus } & CaiStatus;
  // CAI wraps the status as {"input": <status>}; tolerate a bare status too.
  const status: CaiStatus = wrapper.input ?? wrapper;
  runtime.log(
    `Attestation callback: status=${status.status ?? "?"} inference_id=${status.id ?? "?"}`,
  );

  if (status.status !== "completed") {
    runtime.log(`CAI status is "${status.status}", not completed — skipping publish/write`);
    return JSON.stringify({ inference_id: status.id ?? null, status: status.status ?? null, action: "skipped" });
  }

  const attestation = requireCaiAttestationFields(parseCaiAttestation(status));
  runtime.log(
    `CAI attestation inference_id=${attestation.inference_id} transcript_hash=${attestation.transcript_hash ?? "(none)"}`,
  );

  const evalRunnerApiKey = getEvalRunnerApiKey(runtime);

  // 1) Record the attestation on-chain FIRST — it needs nothing from Walrus, so
  //    it lands immediately without waiting on the (slow) upload poll.
  const { attestationRecordTxHash } = await writeAttestationToArc(
    runtime,
    config.defaultAgentId,
    attestation,
  );

  // 2) Resolve the run via inference_id and publish manifest + eval log to Walrus.
  const published = publishByInferenceId(runtime, attestation.inference_id, evalRunnerApiKey, attestation);

  // 3) Write the score row with the Walrus blob pointer (needs the upload result).
  const { scoreTxHash } = await writeScoreToArc(
    runtime,
    config.defaultAgentId,
    published.capability,
    published.manifest,
    published.walrus_manifest_blob_id,
  );

  return JSON.stringify({
    run_id: published.runId,
    status: status.status,
    inference_id: attestation.inference_id,
    transcript_hash: attestation.transcript_hash ?? null,
    composite: published.manifest.composite,
    walrus_manifest_blob_id: published.walrus_manifest_blob_id,
    arc_attestation_tx: attestationRecordTxHash ?? null,
    arc_score_tx: scoreTxHash ?? null,
  });
}

const initWorkflow = (config: Config) => {
  const cron = new CronCapability();
  const http = new HTTPCapability();
  return [
    handler(cron.trigger({ schedule: config.schedule }), onCronTrigger),
    handler(http.trigger({ authorizedKeys: config.authorizedKeys ?? [] }), onAttestationCallback),
  ];
};

export async function main() {
  const runner = await Runner.newRunner<Config>();
  await runner.run(initWorkflow);
}
