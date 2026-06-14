/** Live demo use-case workflow flight tracker — GH #82 / usecase workflow. */

export type PipelineStepId =
  | "user_trade_intent"
  | "marketplace_mcp"
  | "x402_price"
  | "x402_settlement";

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

/** Use-case workflow: User @Permit → Marketplace MCP → Price → x402 settlement */
export const PIPELINE_STEPS: PipelineStepDefinition[] = [
  { id: "user_trade_intent", label: "User @Permit — I want to trade", shortLabel: "Permit" },
  { id: "marketplace_mcp", label: "Marketplace MCP", shortLabel: "Marketplace" },
  { id: "x402_price", label: "Price Gate", shortLabel: "Price" },
  { id: "x402_settlement", label: "x402 Settlement", shortLabel: "x402" },
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

export interface MarketplaceCandidate {
  mcp: string;
  ensName: string;
  capability: string;
  composite: number;
  attestationRef: string;
  walrusBlobId: string;
}

export interface MarketplaceMcpResult {
  ensName: string;
  mcp: string;
  capability: string;
  composite: number;
  mcpEndpoint: string;
  ensRecords: Record<string, string>;
  candidates: MarketplaceCandidate[];
  summary: string;
}

export interface X402PriceResult {
  minScore: number;
  priceUsdc: number | null;
  priceLabel: string;
  capability: string;
  payee: string | null;
  network: string;
  paymentRequired: boolean;
}

export interface X402SettlementResult {
  status: "payment_required" | "settled";
  payee: string | null;
  network: string;
  priceUsdc: number | null;
  registryAddress: string | null;
  demoRoute: string;
  mcpEndpoint: string | null;
  summary: string;
}

/** @deprecated Use MarketplaceMcpResult — kept for pipeline-server internals */
export type EnsDiscoveryResult = MarketplaceMcpResult;

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
