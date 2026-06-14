/** Natural-language demo prompt → orchestration intent (GH #81). */

export interface ParsedIntent {
  action: string;
  assetsFrom: string;
  assetsTo: string;
  amountUsd: number | null;
  minReliabilityScore: number;
  marketplaceCapability: "quote" | "route" | "trade" | "swap";
  objective: string;
  rawPrompt: string;
}

export interface DemoPrompt {
  id: string;
  text: string;
}

/** Pre-baked judge prompts — parsing derives fields from `text`, not from this metadata. */
export const DEMO_PROMPTS: DemoPrompt[] = [
  {
    id: "eth-quote",
    text: "Get best ETH/USDC quote with min reliability ≥ 0.15",
  },
];

/** Concierge chat quick prompts — quote flows that work today (registry has quote capability only). */
export const CHAT_DEMO_PROMPTS: DemoPrompt[] = [
  {
    id: "eth-lifi-quote",
    text: "Quote 0.001 ETH to USDC on Base using LI.FI get-quote. Skip marketplace lookup — call the vendor tool directly.",
  },
  {
    id: "marketplace-quote",
    text: "Find the best quote MCP for ETH/USDC with min reliability 0.15, then quote 0.001 ETH to USDC on the winner.",
  },
  {
    id: "probe-lifi",
    text: "Smoke test: probe_vendor_mcp for lifi only. No marketplace tools.",
  },
];

const TOKEN = "[A-Z]{2,10}";

function parseExplicitMinScore(text: string): number | null {
  const patterns = [
    /(?:≥|>=|at least|min(?:imum)?(?: reliability)?)\s*(0\.\d+|1(?:\.0)?)/i,
    /reliability\s*(?:≥|>=)\s*(0\.\d+|1(?:\.0)?)/i,
    /min[_\s-]?score\s*(?:of|:)?\s*(0\.\d+|1(?:\.0)?)/i,
  ];
  for (const pattern of patterns) {
    const match = text.match(pattern);
    if (match) return Math.min(1, Math.max(0, parseFloat(match[1])));
  }
  return null;
}

function inferMinScore(text: string): number {
  const explicit = parseExplicitMinScore(text);
  if (explicit !== null) return explicit;

  const lower = text.toLowerCase();
  if (/lowest execution time|fastest|lowest latency|optimize portfolio/.test(lower)) {
    return 0.9;
  }
  if (/best quote|reliable|trust/.test(lower)) {
    return 0.85;
  }
  return 0.8;
}

function parseAction(text: string): { action: string; capability: ParsedIntent["marketplaceCapability"] } {
  const lower = text.toLowerCase();
  if (/\bswap\b/.test(lower)) return { action: "DeFi Swap", capability: "swap" };
  if (/\btrade\b/.test(lower)) return { action: "DeFi Trade", capability: "trade" };
  if (/\broute\b/.test(lower)) return { action: "DeFi Route", capability: "route" };
  if (/\bquote\b/.test(lower)) return { action: "DeFi Quote", capability: "quote" };
  return { action: "DeFi Operation", capability: "quote" };
}

function parseAssetPair(text: string): { from: string; to: string } {
  const slash = text.match(new RegExp(`\\b(${TOKEN})\\s*/\\s*(${TOKEN})\\b`));
  if (slash) return { from: slash[1], to: slash[2] };

  const forPattern = text.match(
    new RegExp(`\\$?\\d+(?:\\.\\d+)?\\s*(${TOKEN})\\s+(?:for|to|→)\\s+(${TOKEN})\\b`, "i"),
  );
  if (forPattern) return { from: forPattern[1], to: forPattern[2] };

  const toPattern = text.match(new RegExp(`\\b(${TOKEN})\\s+(?:to|→)\\s+(${TOKEN})\\b`, "i"));
  if (toPattern) return { from: toPattern[1], to: toPattern[2] };

  throw new Error(`Could not parse asset pair from prompt: ${text}`);
}

function parseAmountUsd(text: string): number | null {
  const match = text.match(/\$\s*(\d+(?:\.\d+)?)/);
  if (match) return parseFloat(match[1]);

  const bare = text.match(new RegExp(`\\b(\\d+(?:\\.\\d+)?)\\s+(${TOKEN})\\s+(?:to|for|→)`, "i"));
  if (bare) return parseFloat(bare[1]);

  return null;
}

function parseObjective(text: string): string {
  const lower = text.toLowerCase();
  if (/lowest execution time|fastest/.test(lower)) return "Minimize execution time";
  if (/best quote/.test(lower)) return "Maximize quote quality";
  if (/route.*l2/.test(lower)) return "Optimal L2 routing";
  if (/optimize portfolio/.test(lower)) return "Portfolio optimization";
  return "Match capability to intent";
}

/** Parse a natural-language demo prompt into orchestration parameters. */
export function parseDemoPrompt(text: string): ParsedIntent {
  const trimmed = text.trim();
  if (!trimmed) throw new Error("Prompt text is empty");

  const { action, capability } = parseAction(trimmed);
  const { from, to } = parseAssetPair(trimmed);

  return {
    action,
    assetsFrom: from,
    assetsTo: to,
    amountUsd: parseAmountUsd(trimmed),
    minReliabilityScore: inferMinScore(trimmed),
    marketplaceCapability: capability,
    objective: parseObjective(trimmed),
    rawPrompt: trimmed,
  };
}

export function formatMinReliability(score: number): string {
  return `≥ ${score.toFixed(2)}`;
}

export function formatAssets(from: string, to: string): string {
  return `${from} → ${to}`;
}
