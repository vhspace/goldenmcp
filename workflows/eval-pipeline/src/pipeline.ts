import {
  EVMClient,
  HTTPClient,
  ok,
  prepareReportRequest,
  text,
  TxStatus,
  type Runtime,
} from "@chainlink/cre-sdk";
import { encodeFunctionData, parseAbi, type Hex } from "viem";
import type {
  CaiAttestation,
  Config,
  PipelineResult,
  PipelineTarget,
  ScoreManifest,
} from "./types";

const httpClient = new HTTPClient();
const CRE_HTTP_TIMEOUT = "8s";

const MCP_REGISTRY_ABI = parseAbi([
  "function updateCapabilityScore(uint256 agentId, string capability, uint16 dataScoreBps, uint16 pathScoreBps, uint16 tokenEfficiencyBps, uint16 compositeBps, bool failed, string walrusBlobId) external",
  "function recordAttestation(uint256 agentId, string txHash) external",
]);

const MINIMAL_SCORE_TRANSCRIPT = {
  events: [
    { kind: "tool", tool_name: "get-chains", content: "{}" },
    { kind: "tool", tool_name: "get-tokens", content: "{}" },
    { kind: "tool", tool_name: "get-quote", content: '{"amount": 1}' },
  ],
  final_output: { amount: 1, token: "USDC" },
  total_tokens: 2000,
};

export interface EvalRunPollResult {
  run_id: string;
  status: string;
  manifest?: ScoreManifest;
  error?: string;
  walrus_manifest_blob_id?: string;
  walrus_eval_blob_id?: string;
  walrus_index_blob_id?: string;
}

export function scoreToBps(score: number): number {
  const clamped = Math.max(0, Math.min(1, score));
  return Math.round(clamped * 10000);
}

export function isCaiConfigured(config: Config, caiApiKey?: string): boolean {
  return Boolean(config.chainlinkCaiUrl?.trim() || caiApiKey?.trim());
}

export function shouldSkipCai(config: Config, caiApiKey?: string): boolean {
  return !isCaiConfigured(config, caiApiKey);
}

export function finalizeCaiPollStatus(status: string, error?: string): void {
  if (status === "failed") {
    throw new Error(`CAI inference failed: ${error ?? "unknown error"}`);
  }
  if (status !== "completed") {
    throw new Error(`CAI inference did not complete: status=${status}`);
  }
}

export function finalizeEvalRunPollStatus(
  status: string,
  targetStatus: string,
  error?: string,
): void {
  if (status === "failed") {
    throw new Error(`eval run failed: ${error ?? "unknown error"}`);
  }
  if (status !== targetStatus) {
    throw new Error(`eval run did not reach ${targetStatus}: status=${status}`);
  }
}

function extractAttestationFields(parsed: Record<string, unknown>): CaiAttestation {
  const attestation_id =
    typeof parsed.attestation_id === "string"
      ? parsed.attestation_id
      : typeof parsed.attestationId === "string"
        ? parsed.attestationId
        : undefined;
  const attestation_tx_hash =
    typeof parsed.attestation_tx_hash === "string"
      ? parsed.attestation_tx_hash
      : typeof parsed.attestationTxHash === "string"
        ? parsed.attestationTxHash
        : typeof parsed.tx_hash === "string"
          ? parsed.tx_hash
          : undefined;
  return { attestation_id, attestation_tx_hash };
}

export function parseCaiAttestation(output: string): CaiAttestation {
  const trimmed = output.trim();
  const attempts = [trimmed];
  const fenced = trimmed.match(/```(?:json)?\s*([\s\S]*?)```/);
  if (fenced?.[1]) {
    attempts.push(fenced[1].trim());
  }
  const brace = trimmed.match(/\{[\s\S]*\}/);
  if (brace?.[0]) {
    attempts.push(brace[0]);
  }

  for (const candidate of attempts) {
    try {
      const parsed = JSON.parse(candidate) as Record<string, unknown>;
      const fields = extractAttestationFields(parsed);
      if (fields.attestation_id || fields.attestation_tx_hash) {
        return fields;
      }
    } catch {
      // try next candidate
    }
  }

  return {};
}

function runtimeSleep(runtime: Runtime<Config>, ms: number): void {
  const maybeSleep = runtime as Runtime<Config> & { sleep?: (delayMs: number) => void };
  if (typeof maybeSleep.sleep === "function") {
    maybeSleep.sleep(ms);
  }
}

function authHeaders(token: string): Record<string, string> {
  return { Authorization: `Bearer ${token}` };
}

function jsonAuthHeaders(token: string): Record<string, string> {
  return {
    ...authHeaders(token),
    "Content-Type": "application/json",
  };
}

/** CRE HTTP capability expects request body as base64-encoded bytes on the wire. */
function encodeHttpBody(payload: string): string {
  return Buffer.from(payload, "utf8").toString("base64");
}

export function requireCaiAttestationFields(attestation: CaiAttestation): CaiAttestation {
  if (!attestation.attestation_id?.trim() && !attestation.attestation_tx_hash?.trim()) {
    throw new Error(
      "CAI inference completed but output contained no attestation_id or attestation_tx_hash",
    );
  }
  return attestation;
}

function requireHttpOk(
  response: ReturnType<ReturnType<HTTPClient["sendRequest"]>["result"]>,
  context: string,
  allowedStatuses: number[] = [200],
): string {
  if (!ok(response) || !allowedStatuses.includes(response.statusCode)) {
    const body = text(response);
    const snippet = body.length > 500 ? `${body.slice(0, 500)}…` : body;
    throw new Error(`${context}: HTTP ${response.statusCode} — ${snippet}`);
  }
  return text(response);
}

function getEvalRunnerApiKey(runtime: Runtime<Config>): string {
  try {
    const secret = runtime.getSecret({ id: "EVAL_RUNNER_API_KEY" }).result();
    if (secret.value?.trim()) {
      return secret.value.trim();
    }
  } catch (err) {
    runtime.log(`EVAL_RUNNER_API_KEY secret lookup failed: ${err}`);
  }

  const fallback = runtime.config.evalRunnerApiKey?.trim();
  if (fallback) {
    runtime.log("Using evalRunnerApiKey from workflow config (simulate fallback)");
    return fallback;
  }

  throw new Error(
    "EVAL_RUNNER_API_KEY secret or evalRunnerApiKey config is required for eval-runner requests",
  );
}

function getCaiApiKey(runtime: Runtime<Config>): string | undefined {
  try {
    const secret = runtime.getSecret({ id: "CHAINLINK_CAI_API_KEY" }).result();
    if (secret.value?.trim()) {
      return secret.value.trim();
    }
  } catch (err) {
    runtime.log(`CHAINLINK_CAI_API_KEY secret lookup failed: ${err}`);
  }
  return undefined;
}

function resolveChainSelector(config: Config): bigint {
  const selectorName = config.arcChainSelector?.trim() || "arc-testnet";
  const selector =
    EVMClient.SUPPORTED_CHAIN_SELECTORS[
      selectorName as keyof typeof EVMClient.SUPPORTED_CHAIN_SELECTORS
    ];
  if (!selector) {
    throw new Error(
      `Unsupported arcChainSelector=${selectorName} — set arcChainSelector to a CRE-supported network (default arc-testnet)`,
    );
  }
  return selector;
}

function parseEvalRunPoll(bodyText: string): EvalRunPollResult {
  return JSON.parse(bodyText) as EvalRunPollResult;
}

export function pollEvalRunUntilScored(
  runtime: Runtime<Config>,
  runId: string,
  apiKey: string,
): EvalRunPollResult {
  const config = runtime.config;
  const base = config.evalRunnerUrl.replace(/\/$/, "");
  let lastStatus = "queued";

  for (let attempt = 1; attempt <= config.inspectPollMaxAttempts; attempt++) {
    const pollResponse = httpClient
      .sendRequest(runtime, {
        url: `${base}/eval/runs/${encodeURIComponent(runId)}`,
        method: "GET",
        headers: authHeaders(apiKey),
        timeout: CRE_HTTP_TIMEOUT,
      })
      .result();
    const pollText = requireHttpOk(pollResponse, `eval/runs/${runId} attempt ${attempt}`);
    const pollParsed = parseEvalRunPoll(pollText);
    lastStatus = pollParsed.status;
    runtime.log(
      `inspect poll attempt=${attempt}/${config.inspectPollMaxAttempts} run_id=${runId} status=${lastStatus}`,
    );

    if (lastStatus === "scored") {
      if (!pollParsed.manifest) {
        throw new Error(`eval run scored but manifest missing run_id=${runId}`);
      }
      return pollParsed;
    }

    if (lastStatus === "failed") {
      finalizeEvalRunPollStatus(lastStatus, "scored", pollParsed.error);
    }

    if (attempt < config.inspectPollMaxAttempts) {
      runtimeSleep(runtime, config.inspectPollIntervalMs);
    }
  }

  finalizeEvalRunPollStatus(lastStatus, "scored");
}

export function pollEvalRunUntilPublished(
  runtime: Runtime<Config>,
  runId: string,
  apiKey: string,
): EvalRunPollResult {
  const config = runtime.config;
  const base = config.evalRunnerUrl.replace(/\/$/, "");
  let lastStatus = "publishing";

  for (let attempt = 1; attempt <= config.publishPollMaxAttempts; attempt++) {
    const pollResponse = httpClient
      .sendRequest(runtime, {
        url: `${base}/eval/runs/${encodeURIComponent(runId)}`,
        method: "GET",
        headers: authHeaders(apiKey),
        timeout: CRE_HTTP_TIMEOUT,
      })
      .result();
    const pollText = requireHttpOk(pollResponse, `eval/runs/${runId} attempt ${attempt}`);
    const pollParsed = parseEvalRunPoll(pollText);
    lastStatus = pollParsed.status;
    runtime.log(
      `publish poll attempt=${attempt}/${config.publishPollMaxAttempts} run_id=${runId} status=${lastStatus}`,
    );

    if (lastStatus === "published") {
      if (!pollParsed.manifest || !pollParsed.walrus_manifest_blob_id || !pollParsed.walrus_eval_blob_id) {
        throw new Error(`eval run published but walrus fields missing run_id=${runId}`);
      }
      return pollParsed;
    }

    if (lastStatus === "failed") {
      finalizeEvalRunPollStatus(lastStatus, "published", pollParsed.error);
    }

    if (attempt < config.publishPollMaxAttempts) {
      runtimeSleep(runtime, config.publishPollIntervalMs);
    }
  }

  finalizeEvalRunPollStatus(lastStatus, "published");
}

async function runEvalScore(
  runtime: Runtime<Config>,
  target: PipelineTarget,
  apiKey: string,
): Promise<{ run_id: string; manifest: ScoreManifest }> {
  const config = runtime.config;
  const base = config.evalRunnerUrl.replace(/\/$/, "");

  if (config.useScoreOnly) {
    runtime.log(
      `useScoreOnly=true — POST /eval/score for ${target.mcp}/${target.capability} (simulate path)`,
    );
    const body = JSON.stringify({
      mcp: target.mcp,
      capability: target.capability,
      transcript: MINIMAL_SCORE_TRANSCRIPT,
    });
    const response = httpClient
      .sendRequest(runtime, {
        url: `${base}/eval/score`,
        method: "POST",
        body: encodeHttpBody(body),
        headers: jsonAuthHeaders(apiKey),
        timeout: CRE_HTTP_TIMEOUT,
      })
      .result();
    const bodyText = requireHttpOk(response, `eval/score ${target.mcp}/${target.capability}`);
    const parsed = JSON.parse(bodyText) as { run_id: string; manifest: ScoreManifest };
    runtime.log(`eval/score run_id=${parsed.run_id} composite=${parsed.manifest.composite}`);
    return parsed;
  }

  runtime.log(`POST /eval/inspect (async) for ${target.mcp}/${target.capability}`);
  const inspectBody = JSON.stringify({
    mcp: target.mcp,
    capability: target.capability,
  });
  const response = httpClient
    .sendRequest(runtime, {
      url: `${base}/eval/inspect`,
      method: "POST",
      body: encodeHttpBody(inspectBody),
      headers: jsonAuthHeaders(apiKey),
      timeout: CRE_HTTP_TIMEOUT,
    })
    .result();
  const bodyText = requireHttpOk(response, `eval/inspect ${target.mcp}/${target.capability}`, [200, 202]);
  const accepted = JSON.parse(bodyText) as { run_id: string; status: string };
  if (!accepted.run_id) {
    throw new Error(`eval/inspect missing run_id: ${bodyText}`);
  }
  runtime.log(`eval/inspect queued run_id=${accepted.run_id} status=${accepted.status}`);

  const polled = pollEvalRunUntilScored(runtime, accepted.run_id, apiKey);
  runtime.log(
    `eval/inspect scored run_id=${accepted.run_id} composite=${polled.manifest?.composite}`,
  );
  return { run_id: accepted.run_id, manifest: polled.manifest! };
}

export async function caiAttest(
  runtime: Runtime<Config>,
  manifest: ScoreManifest,
  caiApiKey: string,
): Promise<CaiAttestation> {
  const config = runtime.config;
  const base = config.chainlinkCaiUrl.replace(/\/$/, "");
  const manifestJson = JSON.stringify(manifest);
  const manifestBase64 = Buffer.from(manifestJson, "utf8").toString("base64");

  const submitBody = JSON.stringify({
    model: "gemma4",
    prompt: [
      "Review the attached manifest.json GoldenMCP eval score manifest for consistency and integrity.",
      "Return JSON only with keys attestation_id (string) and attestation_tx_hash (0x-prefixed hex string when available).",
    ].join("\n"),
    resources: [
      {
        filename: "manifest.json",
        content_type: "application/json",
        content_base64: manifestBase64,
      },
    ],
  });

  runtime.log(`CAI POST /v1/inference model=gemma4 run_id=${manifest.run_id}`);
  const submitResponse = httpClient
    .sendRequest(runtime, {
      url: `${base}/v1/inference`,
      method: "POST",
      body: encodeHttpBody(submitBody),
      headers: {
        ...authHeaders(caiApiKey),
        "Content-Type": "application/json",
      },
      timeout: CRE_HTTP_TIMEOUT,
    })
    .result();

  const submitText = requireHttpOk(submitResponse, "CAI /v1/inference submit");
  const submitParsed = JSON.parse(submitText) as { id: string; status?: string };
  const inferenceId = submitParsed.id;
  if (!inferenceId) {
    throw new Error(`CAI submit missing inference id: ${submitText}`);
  }
  runtime.log(`CAI inference queued id=${inferenceId}`);

  let lastStatus = submitParsed.status ?? "queued";
  for (let attempt = 1; attempt <= config.caiPollMaxAttempts; attempt++) {
    const pollResponse = httpClient
      .sendRequest(runtime, {
        url: `${base}/v1/inference/${encodeURIComponent(inferenceId)}`,
        method: "GET",
        headers: authHeaders(caiApiKey),
        timeout: CRE_HTTP_TIMEOUT,
      })
      .result();
    const pollText = requireHttpOk(pollResponse, `CAI poll ${inferenceId} attempt ${attempt}`);
    const pollParsed = JSON.parse(pollText) as {
      status: string;
      output?: string;
      error?: string;
    };
    lastStatus = pollParsed.status;
    runtime.log(`CAI poll attempt=${attempt}/${config.caiPollMaxAttempts} status=${lastStatus}`);

    if (lastStatus === "completed") {
      const attestation = requireCaiAttestationFields(
        parseCaiAttestation(pollParsed.output ?? ""),
      );
      runtime.log(
        `CAI completed attestation_id=${attestation.attestation_id} attestation_tx_hash=${attestation.attestation_tx_hash ?? "(none)"}`,
      );
      return attestation;
    }

    if (lastStatus === "failed") {
      finalizeCaiPollStatus(lastStatus, pollParsed.error);
    }

    if (attempt < config.caiPollMaxAttempts) {
      runtimeSleep(runtime, config.caiPollIntervalMs);
    }
  }

  finalizeCaiPollStatus(lastStatus);
}

export async function publishToWalrus(
  runtime: Runtime<Config>,
  runId: string,
  apiKey: string,
  attestation?: CaiAttestation,
): Promise<{
  manifest: ScoreManifest;
  walrus_manifest_blob_id: string;
  walrus_eval_blob_id: string;
  walrus_index_blob_id?: string;
}> {
  const base = runtime.config.evalRunnerUrl.replace(/\/$/, "");
  const body = JSON.stringify({
    run_id: runId,
    attestation_id: attestation?.attestation_id,
    attestation_tx_hash: attestation?.attestation_tx_hash,
  });

  runtime.log(`POST /eval/publish (async) run_id=${runId}`);
  const response = httpClient
    .sendRequest(runtime, {
      url: `${base}/eval/publish`,
      method: "POST",
      body: encodeHttpBody(body),
      headers: jsonAuthHeaders(apiKey),
      timeout: CRE_HTTP_TIMEOUT,
    })
    .result();
  const bodyText = requireHttpOk(response, `eval/publish run_id=${runId}`, [200, 202]);
  const accepted = JSON.parse(bodyText) as { run_id?: string; status?: string };
  runtime.log(`eval/publish accepted run_id=${runId} status=${accepted.status ?? "published"}`);

  const polled = pollEvalRunUntilPublished(runtime, runId, apiKey);
  runtime.log(
    `Walrus publish run_id=${runId} manifest_blob=${polled.walrus_manifest_blob_id} eval_blob=${polled.walrus_eval_blob_id}`,
  );
  return {
    manifest: polled.manifest!,
    walrus_manifest_blob_id: polled.walrus_manifest_blob_id!,
    walrus_eval_blob_id: polled.walrus_eval_blob_id!,
    walrus_index_blob_id: polled.walrus_index_blob_id,
  };
}

function writeRegistryReport(
  runtime: Runtime<Config>,
  evmClient: EVMClient,
  registryAddress: string,
  callData: Hex,
  label: string,
): string {
  const signedReport = runtime.report(prepareReportRequest(callData)).result();
  const txResult = evmClient
    .writeReport(runtime, {
      receiver: registryAddress,
      report: signedReport,
      gasConfig: { gasLimit: "500000" },
    })
    .result();

  if (txResult.txStatus !== TxStatus.SUCCESS) {
    throw new Error(
      `${label} writeReport failed: txStatus=${txResult.txStatus} receiver=${registryAddress}`,
    );
  }

  const txHash = txResult.txHash ? Buffer.from(txResult.txHash).toString("hex") : "";
  runtime.log(`${label} tx hash=${txHash || "(empty)"} status=${txResult.txStatus}`);
  return txHash ? (txHash.startsWith("0x") ? txHash : `0x${txHash}`) : "";
}

export async function writeToArc(
  runtime: Runtime<Config>,
  agentId: number,
  capability: string,
  manifest: ScoreManifest,
  walrusBlobId: string,
  attestationTxHash?: string,
): Promise<{ scoreTxHash?: string; attestationRecordTxHash?: string }> {
  const registryAddress = runtime.config.arcRegistryAddress?.trim();
  if (!registryAddress) {
    runtime.log("arcRegistryAddress empty — skipping Arc registry write");
    return {};
  }

  const chainSelector = resolveChainSelector(runtime.config);
  const evmClient = new EVMClient(chainSelector);

  runtime.log(
    `Arc write agentId=${agentId} capability=${capability} registry=${registryAddress} walrus=${walrusBlobId}`,
  );

  const updateData = encodeFunctionData({
    abi: MCP_REGISTRY_ABI,
    functionName: "updateCapabilityScore",
    args: [
      BigInt(agentId),
      capability,
      scoreToBps(manifest.data_score),
      scoreToBps(manifest.path_score),
      scoreToBps(manifest.token_efficiency),
      scoreToBps(manifest.composite),
      manifest.failed,
      walrusBlobId,
    ],
  });

  const scoreTxHash = writeRegistryReport(
    runtime,
    evmClient,
    registryAddress,
    updateData,
    "updateCapabilityScore",
  );

  let attestationRecordTxHash: string | undefined;
  if (attestationTxHash?.trim()) {
    const recordData = encodeFunctionData({
      abi: MCP_REGISTRY_ABI,
      functionName: "recordAttestation",
      args: [BigInt(agentId), attestationTxHash.trim()],
    });
    attestationRecordTxHash = writeRegistryReport(
      runtime,
      evmClient,
      registryAddress,
      recordData,
      "recordAttestation",
    );
  }

  return { scoreTxHash, attestationRecordTxHash };
}

export async function runPipeline(
  runtime: Runtime<Config>,
  target: PipelineTarget,
): Promise<PipelineResult> {
  const config = runtime.config;
  const agentId = target.agentId ?? config.defaultAgentId;
  runtime.log(`runPipeline start mcp=${target.mcp} capability=${target.capability} agentId=${agentId}`);

  const evalRunnerApiKey = getEvalRunnerApiKey(runtime);
  const scored = await runEvalScore(runtime, target, evalRunnerApiKey);

  const caiApiKey = getCaiApiKey(runtime);
  let attestation: CaiAttestation | undefined;
  let skippedCai = false;

  if (shouldSkipCai(config, caiApiKey)) {
    skippedCai = true;
    runtime.log(
      "Skipping CAI attestation — chainlinkCaiUrl and CHAINLINK_CAI_API_KEY both unset (simulate without key)",
    );
  } else {
    if (!caiApiKey) {
      throw new Error(
        "CHAINLINK_CAI_API_KEY secret required when chainlinkCaiUrl is configured — refusing silent CAI skip",
      );
    }
    if (!config.chainlinkCaiUrl?.trim()) {
      throw new Error(
        "chainlinkCaiUrl config required when CHAINLINK_CAI_API_KEY is set — refusing silent CAI skip",
      );
    }
    attestation = await caiAttest(runtime, scored.manifest, caiApiKey);
  }

  const published = await publishToWalrus(
    runtime,
    scored.run_id,
    evalRunnerApiKey,
    attestation,
  );

  const walrusBlobId = published.walrus_manifest_blob_id;
  let skippedArc = false;
  let arcScoreTxHash: string | undefined;
  let arcAttestationTxHash: string | undefined;

  if (!config.arcRegistryAddress?.trim()) {
    skippedArc = true;
    runtime.log("arcRegistryAddress empty — skipping Arc registry write after Walrus publish");
  } else {
    const arcResult = await writeToArc(
      runtime,
      agentId,
      target.capability,
      published.manifest,
      walrusBlobId,
      attestation?.attestation_tx_hash,
    );
    arcScoreTxHash = arcResult.scoreTxHash;
    arcAttestationTxHash = arcResult.attestationRecordTxHash;
  }

  runtime.log(
    `runPipeline complete mcp=${target.mcp}/${target.capability} run_id=${scored.run_id} composite=${published.manifest.composite} skippedCai=${skippedCai} skippedArc=${skippedArc}`,
  );

  return {
    runId: scored.run_id,
    mcp: target.mcp,
    capability: target.capability,
    manifest: published.manifest,
    attestationId: attestation?.attestation_id,
    attestationTxHash: attestation?.attestation_tx_hash,
    walrusManifestBlobId: published.walrus_manifest_blob_id,
    walrusEvalBlobId: published.walrus_eval_blob_id,
    walrusIndexBlobId: published.walrus_index_blob_id,
    arcScoreTxHash,
    arcAttestationTxHash,
    skippedCai,
    skippedArc,
  };
}
