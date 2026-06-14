/** An HTTP-trigger authorized signer key. Empty list ([]) accepts any sender in simulation. */
export interface AuthorizedKey {
  type?: string;
  publicKey?: string;
}

export interface Config {
  schedule: string;
  evalRunnerUrl: string;
  evalRunnerApiKey: string;
  chainlinkCaiUrl: string;
  walrusAggregatorUrl: string;
  arcRegistryAddress: string;
  arcChainSelector: string;
  defaultAgentId: number;
  useScoreOnly: boolean;
  /**
   * When set, the cron handler submits CAI inference with this URL as the
   * cre_callback target (the workflow's own HTTP trigger) and returns, instead
   * of polling inline. The HTTP-trigger handler then publishes + writes to Arc.
   */
  creCallbackUrl?: string;
  /** Authorized senders for the HTTP trigger; [] accepts any in simulation. */
  authorizedKeys?: AuthorizedKey[];
  /** Busy-wait between poll attempts in cre workflow simulate (runtime.sleep traps). */
  pollBusyWait?: boolean;
  /** When set, cron/simulate only runs these `mcp/capability` pairs (required for useScoreOnly fixture). */
  benchmarkAllowlist?: string[];
  /**
   * Run ONE benchmark per cron fire via the eval-runner's round-robin cursor
   * (GET /benchmarks/next), cycling through all benchmarks across fires. Keeps
   * each execution under the CRE HTTP-call cap. Ignores benchmarkAllowlist.
   */
  rotateBenchmarks?: boolean;
  caiPollMaxAttempts: number;
  caiPollIntervalMs: number;
  inspectPollMaxAttempts: number;
  inspectPollIntervalMs: number;
  publishPollMaxAttempts: number;
  publishPollIntervalMs: number;
}

export interface PipelineTarget {
  mcp: string;
  capability: string;
  agentId?: number;
}

export interface ScoreManifest {
  mcp: string;
  capability: string;
  run_id: string;
  failed: boolean;
  fail_reason?: string | null;
  data_score: number;
  path_score: number;
  token_efficiency: number;
  composite: number;
  /** CAI inference id, mirrored onchain as the attestation reference. */
  attestation_id?: string | null;
  attestation?: CaiAttestation | null;
  walrus_manifest_blob_id?: string | null;
  walrus_blob_id?: string | null;
}

export interface PipelineResult {
  runId: string;
  mcp: string;
  capability: string;
  manifest: ScoreManifest;
  attestationInferenceId?: string;
  walrusManifestBlobId?: string;
  walrusEvalBlobId?: string;
  walrusIndexBlobId?: string;
  arcScoreTxHash?: string;
  arcAttestationTxHash?: string;
  skippedCai: boolean;
  skippedArc: boolean;
}

/** A completed Confidential AI (TEE) inference — this IS the attestation. */
export interface CaiAttestation {
  inference_id: string;
  model: string;
  verdict: string;
  /** 0x-prefixed bytes32 response digest from the TEE; the onchain transcript hash. */
  transcript_hash?: string;
  completed_at?: string;
  prompt_tokens?: number;
  completion_tokens?: number;
}
