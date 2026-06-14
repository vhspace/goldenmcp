/** Live demo pipeline flight tracker — GH #82. */

export type PipelineStepId =
  | "user_prompt"
  | "ens_discovery"
  | "tee_sandbox"
  | "execution_engine"
  | "blockchain_proof";

export type PipelineStepStatus = "pending" | "active" | "complete" | "error";

export interface PipelineStepDefinition {
  id: PipelineStepId;
  label: string;
  shortLabel: string;
}

export interface PipelineStepState {
  id: PipelineStepId;
  label: string;
  shortLabel: string;
  status: PipelineStepStatus;
  detail: Record<string, unknown> | null;
  error: string | null;
}

export interface PipelineRunState {
  steps: PipelineStepState[];
  activeStep: PipelineStepId | null;
  failedStep: PipelineStepId | null;
}

export const PIPELINE_STEPS: PipelineStepDefinition[] = [
  { id: "user_prompt", label: "User Prompt", shortLabel: "Prompt" },
  { id: "ens_discovery", label: "ENS Discovery", shortLabel: "ENS" },
  { id: "tee_sandbox", label: "TEE Sandbox Eval", shortLabel: "TEE" },
  { id: "execution_engine", label: "Execution Engine", shortLabel: "Execute" },
  { id: "blockchain_proof", label: "Blockchain Proof", shortLabel: "Proof" },
];

export function stepIndex(id: PipelineStepId): number {
  return PIPELINE_STEPS.findIndex((s) => s.id === id);
}

export function createInitialPipelineState(): PipelineRunState {
  return {
    steps: PIPELINE_STEPS.map((def) => ({
      id: def.id,
      label: def.label,
      shortLabel: def.shortLabel,
      status: "pending",
      detail: null,
      error: null,
    })),
    activeStep: null,
    failedStep: null,
  };
}

export function setActiveStep(state: PipelineRunState, id: PipelineStepId): PipelineRunState {
  return {
    ...state,
    activeStep: id,
    steps: state.steps.map((step) =>
      step.id === id
        ? { ...step, status: "active", error: null }
        : step.status === "complete"
          ? step
          : { ...step, status: step.status === "active" ? "pending" : step.status },
    ),
  };
}

export function applyStepUpdate(
  state: PipelineRunState,
  id: PipelineStepId,
  status: "complete" | "error",
  detail?: Record<string, unknown>,
  error?: string,
): PipelineRunState {
  const failedStep = status === "error" ? id : state.failedStep;
  return {
    ...state,
    activeStep: status === "error" ? null : state.activeStep === id ? null : state.activeStep,
    failedStep,
    steps: state.steps.map((step) =>
      step.id === id
        ? {
            ...step,
            status,
            detail: detail ?? null,
            error: error ?? null,
          }
        : step,
    ),
  };
}

export interface EnsDiscoveryResult {
  ensName: string;
  mcp: string;
  capability: string;
  composite: number;
  mcpEndpoint: string;
  ensRecords: Record<string, string>;
  summary: string;
}

export interface TeeSandboxResult {
  secured: boolean;
  badge: string;
  inferenceId: string | null;
  verdict: string | null;
  transcriptHash: string | null;
}

export interface ExecutionResult {
  httpStatus: number;
  paymentRequired: boolean;
  priceUsdc: number | null;
  capability: string;
  minScore: number;
  results: Record<string, unknown>[] | null;
  payee?: string;
  network?: string;
}

export interface BlockchainProofResult {
  kind: "x402_settlement" | "onchain_scores";
  payee: string | null;
  network: string | null;
  priceUsdc: number | null;
  walrusBlobId: string | null;
  composite: number | null;
  registryAddress: string | null;
  summary: string;
}

export interface PipelineContext {
  intent: Record<string, unknown>;
  vendor?: EnsDiscoveryResult;
  tee?: TeeSandboxResult;
  execution?: ExecutionResult;
}
