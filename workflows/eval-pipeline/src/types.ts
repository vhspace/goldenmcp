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
  /** Busy-wait between poll attempts in cre workflow simulate (runtime.sleep traps). */
  pollBusyWait?: boolean;
  /** When set, cron/simulate only runs these `mcp/capability` pairs (required for useScoreOnly fixture). */
  benchmarkAllowlist?: string[];
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
  attestation_id?: string | null;
  attestation_tx_hash?: string | null;
  walrus_manifest_blob_id?: string | null;
  walrus_blob_id?: string | null;
}

export interface PipelineResult {
  runId: string;
  mcp: string;
  capability: string;
  manifest: ScoreManifest;
  attestationId?: string;
  attestationTxHash?: string;
  walrusManifestBlobId?: string;
  walrusEvalBlobId?: string;
  walrusIndexBlobId?: string;
  arcScoreTxHash?: string;
  arcAttestationTxHash?: string;
  skippedCai: boolean;
  skippedArc: boolean;
}

export interface CaiAttestation {
  attestation_id?: string;
  attestation_tx_hash?: string;
}
