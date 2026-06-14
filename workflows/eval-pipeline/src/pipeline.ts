import {
  EVMClient,
  HTTPClient,
  ok,
  prepareReportRequest,
  text,
  TxStatus,
  type Runtime,
} from "@chainlink/cre-sdk";
import { encodeFunctionData, parseAbi, sha256, stringToHex, type Hex } from "viem";
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
  "function recordAttestation(uint256 agentId, string inferenceId, bytes32 transcriptHash) external",
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
  mcp?: string;
  capability?: string;
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

/** Completed CAI status object as returned by GET /v1/inference/{id}. */
export interface CaiStatus {
  id?: string;
  status?: string;
  model?: string;
  output?: string;
  error?: string;
  completed_at?: string;
  usage?: { prompt_tokens?: number; completion_tokens?: number };
  resources?: { response_digest?: string }[];
}

/** Normalize a 32-byte hex digest (with/without 0x) to a 0x bytes32 value, else undefined. */
export function toBytes32(hex: string | undefined): string | undefined {
  if (!hex) return undefined;
  const h = hex.replace(/^0[xX]/, "");
  if (h.length !== 64 || !/^[0-9a-fA-F]+$/.test(h)) return undefined;
  return `0x${h.toLowerCase()}`;
}

/**
 * Build the attestation from a completed CAI status object. The TEE inference
 * itself is the attestation: a known model ran on the manifest inside the
 * enclave. The inference id is the handle, the output is the verdict, and the
 * resource response_digest is the verifiable transcript hash (per Chainlink's
 * official undercollateralized-loan example). Falls back to sha256(output)
 * when the API omits a response digest.
 */
export function parseCaiAttestation(status: CaiStatus, fallbackModel = "gemma4"): CaiAttestation {
  const output = typeof status.output === "string" ? status.output : "";
  const responseDigest = toBytes32(status.resources?.[0]?.response_digest);
  const transcriptHash = responseDigest ?? (output ? sha256(stringToHex(output)) : undefined);
  return {
    inference_id: typeof status.id === "string" ? status.id : "",
    model: typeof status.model === "string" && status.model ? status.model : fallbackModel,
    verdict: output,
    transcript_hash: transcriptHash,
    completed_at: typeof status.completed_at === "string" ? status.completed_at : undefined,
    prompt_tokens: status.usage?.prompt_tokens,
    completion_tokens: status.usage?.completion_tokens,
  };
}

function runtimeSleep(runtime: Runtime<Config>, ms: number): void {
  // cre workflow simulate (v1.18) traps on runtime.sleep(); busy-wait for simulate targets.
  if (runtime.config.useScoreOnly || runtime.config.pollBusyWait) {
    const deadline = runtime.now().getTime() + ms;
    while (runtime.now().getTime() < deadline) {
      // busy-wait between poll attempts in local simulate only
    }
    return;
  }
  runtime.sleep(ms);
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

const BASE64_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

/** WASM-safe base64 of UTF-8 bytes (QuickJS has no Node Buffer). */
export function bytesToBase64(bytes: Uint8Array): string {
  let out = "";
  for (let i = 0; i < bytes.length; i += 3) {
    const b0 = bytes[i];
    const b1 = i + 1 < bytes.length ? bytes[i + 1] : 0;
    const b2 = i + 2 < bytes.length ? bytes[i + 2] : 0;
    out += BASE64_ALPHABET[b0 >> 2];
    out += BASE64_ALPHABET[((b0 & 3) << 4) | (b1 >> 4)];
    out += i + 1 < bytes.length ? BASE64_ALPHABET[((b1 & 15) << 2) | (b2 >> 6)] : "=";
    out += i + 2 < bytes.length ? BASE64_ALPHABET[b2 & 63] : "=";
  }
  return out;
}

/** WASM-safe lowercase hex of raw bytes. */
export function bytesToHex(bytes: Uint8Array): string {
  let out = "";
  for (let i = 0; i < bytes.length; i++) {
    out += bytes[i].toString(16).padStart(2, "0");
  }
  return out;
}

/** CRE HTTP capability expects request body as base64-encoded bytes on the wire. */
function encodeHttpBody(payload: string): string {
  return bytesToBase64(new TextEncoder().encode(payload));
}

export function requireCaiAttestationFields(attestation: CaiAttestation): CaiAttestation {
  if (!attestation.inference_id?.trim()) {
    throw new Error("CAI inference completed but response contained no inference id");
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

export function getEvalRunnerApiKey(runtime: Runtime<Config>): string {
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

export function getCaiApiKey(runtime: Runtime<Config>): string | undefined {
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

export async function runEvalScore(
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

export const CAI_MODEL = "gemma4";

/** The verdict prompt sent to the CAI TEE for a score manifest. */
export function caiReviewPrompt(): string {
  return [
    "You are reviewing a GoldenMCP eval score manifest produced for an MCP server.",
    "Assess whether the scores in manifest.json are internally consistent and the composite is plausible.",
    "Reply with a short verdict: state PASS or FAIL and one sentence of reasoning.",
  ].join("\n");
}

/**
 * Submit a score manifest to the CAI TEE for attestation and return the
 * inference id. When `callbackUrl` is set, CAI POSTs `{input: <status>}` to it
 * once on completion (the async path — the workflow does not poll). The CAI
 * status has no run_id, so callers encode it in the callback URL query string.
 */
export function submitCaiInference(
  runtime: Runtime<Config>,
  manifest: ScoreManifest,
  caiApiKey: string,
  callbackUrl?: string,
): string {
  const base = runtime.config.chainlinkCaiUrl.replace(/\/$/, "");
  const manifestBase64 = bytesToBase64(new TextEncoder().encode(JSON.stringify(manifest)));

  const submitBody: Record<string, unknown> = {
    model: CAI_MODEL,
    prompt: caiReviewPrompt(),
    resources: [
      {
        filename: "manifest.json",
        content_type: "application/json",
        content_base64: manifestBase64,
      },
    ],
  };
  if (callbackUrl) {
    submitBody.cre_callback = { url: callbackUrl };
  }

  runtime.log(`CAI POST /v1/inference model=${CAI_MODEL} run_id=${manifest.run_id}`);
  const submitResponse = httpClient
    .sendRequest(runtime, {
      url: `${base}/v1/inference`,
      method: "POST",
      body: encodeHttpBody(JSON.stringify(submitBody)),
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
  return inferenceId;
}

export async function caiAttest(
  runtime: Runtime<Config>,
  manifest: ScoreManifest,
  caiApiKey: string,
): Promise<CaiAttestation> {
  const config = runtime.config;
  const base = config.chainlinkCaiUrl.replace(/\/$/, "");
  const model = CAI_MODEL;

  // Inline (poll) path: submit without a callback, then poll to completion.
  const inferenceId = submitCaiInference(runtime, manifest, caiApiKey);

  let lastStatus = "queued";
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
    const pollParsed = JSON.parse(pollText) as CaiStatus;
    lastStatus = pollParsed.status ?? "queued";
    runtime.log(`CAI poll attempt=${attempt}/${config.caiPollMaxAttempts} status=${lastStatus}`);

    if (lastStatus === "completed") {
      const attestation = requireCaiAttestationFields(
        parseCaiAttestation({ ...pollParsed, id: pollParsed.id ?? inferenceId }, model),
      );
      runtime.log(
        `CAI completed inference_id=${attestation.inference_id} model=${attestation.model} verdict_len=${attestation.verdict.length}`,
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
    attestation: attestation ?? null,
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

/**
 * Register a CAI inference_id -> run_id mapping with the eval-runner (handler A,
 * right after submitting to CAI). The CRE HTTP trigger only receives the CAI
 * status, so this mapping is how handler B recovers the run.
 */
export function registerCaiSubmitted(
  runtime: Runtime<Config>,
  inferenceId: string,
  runId: string,
  apiKey: string,
): void {
  const base = runtime.config.evalRunnerUrl.replace(/\/$/, "");
  const response = httpClient
    .sendRequest(runtime, {
      url: `${base}/eval/cai-submitted`,
      method: "POST",
      body: encodeHttpBody(JSON.stringify({ inference_id: inferenceId, run_id: runId })),
      headers: jsonAuthHeaders(apiKey),
      timeout: CRE_HTTP_TIMEOUT,
    })
    .result();
  requireHttpOk(response, `eval/cai-submitted inference_id=${inferenceId}`);
  runtime.log(`registered inference_id=${inferenceId} -> run_id=${runId}`);
}

/**
 * Publish by CAI inference_id (handler B). The eval-runner resolves run_id from
 * the inference index, applies the attestation, uploads to Walrus, and returns
 * the manifest + mcp/capability so the caller can do the Arc write.
 */
export function publishByInferenceId(
  runtime: Runtime<Config>,
  inferenceId: string,
  apiKey: string,
  attestation: CaiAttestation,
): {
  runId: string;
  mcp: string;
  capability: string;
  manifest: ScoreManifest;
  walrus_manifest_blob_id: string;
  walrus_eval_blob_id: string;
  walrus_index_blob_id?: string;
} {
  const base = runtime.config.evalRunnerUrl.replace(/\/$/, "");
  const body = JSON.stringify({ inference_id: inferenceId, attestation });

  runtime.log(`POST /eval/publish (by inference_id=${inferenceId})`);
  const response = httpClient
    .sendRequest(runtime, {
      url: `${base}/eval/publish`,
      method: "POST",
      body: encodeHttpBody(body),
      headers: jsonAuthHeaders(apiKey),
      timeout: CRE_HTTP_TIMEOUT,
    })
    .result();
  const bodyText = requireHttpOk(response, `eval/publish inference_id=${inferenceId}`, [200, 202]);
  const accepted = JSON.parse(bodyText) as { run_id?: string; status?: string };
  const runId = accepted.run_id;
  if (!runId) {
    throw new Error(`eval/publish did not resolve a run_id for inference_id=${inferenceId}`);
  }
  runtime.log(`eval/publish resolved inference_id=${inferenceId} -> run_id=${runId} status=${accepted.status ?? "?"}`);

  const polled = pollEvalRunUntilPublished(runtime, runId, apiKey);
  return {
    runId,
    mcp: polled.mcp ?? polled.manifest!.mcp,
    capability: polled.capability ?? polled.manifest!.capability,
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

  const txHash = txResult.txHash ? bytesToHex(new Uint8Array(txResult.txHash)) : "";
  runtime.log(`${label} tx hash=${txHash || "(empty)"} status=${txResult.txStatus}`);
  return txHash ? (txHash.startsWith("0x") ? txHash : `0x${txHash}`) : "";
}

/** Resolve the Arc registry address + EVM client, or null when Arc writes are disabled. */
function resolveArcClient(
  runtime: Runtime<Config>,
): { registryAddress: string; evmClient: EVMClient } | null {
  const registryAddress = runtime.config.arcRegistryAddress?.trim();
  if (!registryAddress) {
    runtime.log("arcRegistryAddress empty — skipping Arc registry write");
    return null;
  }
  return { registryAddress, evmClient: new EVMClient(resolveChainSelector(runtime.config)) };
}

/**
 * Write the attestation to Arc (recordAttestation: inference_id + transcript_hash).
 * Depends on NOTHING from Walrus, so handler B calls this first — the attestation
 * lands on-chain without waiting on the Walrus upload.
 */
export async function writeAttestationToArc(
  runtime: Runtime<Config>,
  agentId: number,
  attestation: CaiAttestation,
): Promise<{ attestationRecordTxHash?: string }> {
  const arc = resolveArcClient(runtime);
  if (!arc || !attestation.inference_id?.trim()) return {};

  const ZERO_BYTES32 = `0x${"0".repeat(64)}` as Hex;
  const transcriptHash = (attestation.transcript_hash?.trim() || ZERO_BYTES32) as Hex;
  runtime.log(`Arc recordAttestation agentId=${agentId} inference_id=${attestation.inference_id}`);
  const recordData = encodeFunctionData({
    abi: MCP_REGISTRY_ABI,
    functionName: "recordAttestation",
    args: [BigInt(agentId), attestation.inference_id.trim(), transcriptHash],
  });
  const attestationRecordTxHash = writeRegistryReport(
    runtime,
    arc.evmClient,
    arc.registryAddress,
    recordData,
    "recordAttestation",
  );
  return { attestationRecordTxHash };
}

/** Write the capability score + Walrus blob pointer to Arc (updateCapabilityScore). */
export async function writeScoreToArc(
  runtime: Runtime<Config>,
  agentId: number,
  capability: string,
  manifest: ScoreManifest,
  walrusBlobId: string,
): Promise<{ scoreTxHash?: string }> {
  const arc = resolveArcClient(runtime);
  if (!arc) return {};

  runtime.log(
    `Arc updateCapabilityScore agentId=${agentId} capability=${capability} walrus=${walrusBlobId}`,
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
    arc.evmClient,
    arc.registryAddress,
    updateData,
    "updateCapabilityScore",
  );
  return { scoreTxHash };
}

/** Combined score + attestation write (inline runPipeline fallback path). */
export async function writeToArc(
  runtime: Runtime<Config>,
  agentId: number,
  capability: string,
  manifest: ScoreManifest,
  walrusBlobId: string,
  attestation?: CaiAttestation,
): Promise<{ scoreTxHash?: string; attestationRecordTxHash?: string }> {
  const { scoreTxHash } = await writeScoreToArc(runtime, agentId, capability, manifest, walrusBlobId);
  const { attestationRecordTxHash } = attestation
    ? await writeAttestationToArc(runtime, agentId, attestation)
    : {};
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
      attestation,
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
    attestationInferenceId: attestation?.inference_id,
    walrusManifestBlobId: published.walrus_manifest_blob_id,
    walrusEvalBlobId: published.walrus_eval_blob_id,
    walrusIndexBlobId: published.walrus_index_blob_id,
    arcScoreTxHash,
    arcAttestationTxHash,
    skippedCai,
    skippedArc,
  };
}
