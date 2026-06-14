/** Marketing landing copy — GH #108 */

export const LANDING_NAV = [
  { label: "About", href: "#about" },
  { label: "Components", href: "#components" },
  { label: "Features", href: "#features" },
  { label: "Vendors", href: "#vendors" },
  { label: "Security", href: "#security" },
  { label: "Demo", href: "/demo" },
  { label: "Leaderboard", href: "/leaderboard" },
  { label: "ENS", href: "/ens" },
] as const;

export const LANDING_HERO = {
  headline: "Web3 MCP Evaluation Marketplace Bridging Live Evals, ENS Identity, and Arc Settlement",
  subcopy:
    "Golden scores from Inspect evals against live MCP servers — Walrus-backed manifests, Chainlink CAI attestation in TEE, and x402 USDC discovery on Arc.",
};

export const LANDING_CTA = {
  primary: { label: "Enter Demo", href: "/demo" },
  secondary: { label: "View Leaderboard", href: "/leaderboard" },
  nav: { label: "Join Demo", href: "/demo" },
};

export const LANDING_FEATURES = [
  {
    id: "evals",
    title: "Live Inspect Evals",
    body: "K=3 Golden Scores on data accuracy, tool path, and token efficiency — no mocks, no recorded fixtures.",
  },
  {
    id: "identity",
    title: "ENS + Arc Registry",
    body: "ENSIP-25/26 agent records and on-chain MCPRegistry scores on Arc testnet for verifiable vendor identity.",
  },
  {
    id: "settlement",
    title: "x402 USDC Gate",
    body: "Marketplace lookup returns HTTP 402 until Circle USDC micropayment settles on Arc — pay for proven quality.",
  },
] as const;

export const LANDING_SECURITY = {
  title: "Secured via Hardware TEE",
  body: "Chainlink Confidential AI attests eval manifests in Gemma sandbox — inference IDs and transcript hashes land on-chain.",
};

/** Vertex-style key components — GH #124 */
export const LANDING_KEY_COMPONENTS = {
  sectionTitle: "Platform Key Components",
  hero: {
    title: "GoldenMCP Evaluation Layer",
    body:
      "At the heart of the marketplace is the GoldenMCP evaluation layer — a live scoring ledger for Web3 MCP servers. " +
      "Inspect evals against real endpoints produce K=3 Golden Scores; manifests land on Walrus, attestations and capability " +
      "scores sync to Arc, and ENS records bind identity to proven quality.",
    subPanels: [
      {
        id: "walrus",
        title: "Walrus Storage",
        body:
          "Score manifests and raw Inspect .eval logs publish to Walrus testnet. Registry entries and ENS text records point at walrus:// blob IDs — no substituted fixtures at runtime.",
      },
      {
        id: "arc",
        title: "Arc Registry",
        body:
          "MCPRegistry on Arc testnet stores composite capability scores, attestation inference IDs, and transcript hashes. USDC is native gas — the same chain settles x402 marketplace payments.",
      },
    ],
  },
  cards: [
    {
      id: "inspect",
      title: "Inspect AI Evals",
      body:
        "K=3 model ensemble scores live MCP tool paths on data accuracy, path correctness, and token efficiency. Benchmarks target Li.FI, 1inch, and other Web3 MCPs with real HTTP connectors — not mocks.",
      icon: "inspect" as const,
    },
    {
      id: "cai",
      title: "Chainlink CRE + CAI",
      body:
        "The CRE workflow orchestrates eval-runner, Walrus upload, and onchain writes. Confidential AI attests manifests in a hardware TEE — inference IDs and response digests become the on-chain proof.",
      icon: "cai" as const,
    },
    {
      id: "x402",
      title: "x402 USDC Marketplace",
      body:
        "Marketplace lookup returns HTTP 402 until Circle USDC micropayment settles on Arc. Agents pay for proven Golden Score tiers and receive ENS-verified MCP endpoints ranked by capability.",
      icon: "x402" as const,
    },
  ],
} as const;

/** "Why GoldenMCP?" bento feature grid — GH #124 */
export const LANDING_WHY = {
  sectionTitle: "Why GoldenMCP?",
  cards: [
    {
      id: "scores",
      title: "Live Golden Scores",
      body:
        "Rank Li.FI, 1inch, and other Web3 MCPs by composite K=3 scores from real Inspect evals — data accuracy, tool path, and token efficiency measured against live endpoints.",
      visual: "scores" as const,
    },
    {
      id: "pricing",
      title: "Pay-for-Quality Lookup",
      body:
        "x402 micropayments gate marketplace discovery — agents pay USDC on Arc only when they need a proven vendor, with price tiers tied to minimum Golden Score thresholds.",
      visual: "pricing" as const,
    },
    {
      id: "coverage",
      title: "Unified MCP Discovery",
      body:
        "One marketplace spans swap, quote, route, and trade capabilities across EVM and Solana MCPs. ENS subnames and Arc registry records tie each vendor to Walrus eval evidence.",
      visual: "coverage" as const,
    },
    {
      id: "trust",
      title: "TEE-Attested Trust",
      body:
        "Chainlink Confidential AI attests score manifests in hardware TEE. Inference IDs and transcript hashes land on Arc — judges and agents verify quality without trusting a central operator.",
      visual: "trust" as const,
    },
  ],
} as const;

/** Hackathon MCP vendors on Arc registry — GH #124 */
export const LANDING_VENDORS = {
  sectionTitle: "Evaluated MCP Vendors",
  sectionLead:
    "Five live Web3 MCP servers registered on Arc for the hackathon — scored via Inspect evals, attested by Chainlink CAI, and discoverable through the x402 marketplace.",
  center: {
    label: "GoldenMCP",
    sublabel: "5 live vendors",
  },
  /** Quadrant order: top-left, top-right, bottom-left, bottom-right; center is separate. */
  quadrants: [
    {
      id: "lifi",
      name: "Li.FI",
      chain: "EVM · Base",
      capabilities: "quote · route",
      body:
        "Official LI.FI HTTP MCP — live token resolution and swap quotes on Base mainnet. Golden benchmarks exercise get-token → get-quote tool paths.",
      icon: "bridge" as const,
      ensName: "lifi.goldenmcp.eth",
      href: "/leaderboard",
    },
    {
      id: "1inch",
      name: "1inch",
      chain: "EVM · Base",
      capabilities: "quote · swap",
      body:
        "1inch Business MCP over Streamable HTTP — stateless quote and swap-framed safety evals against the public protocol endpoint.",
      icon: "aggregator" as const,
      ensName: "1inch.goldenmcp.eth",
      href: "/leaderboard",
    },
    {
      id: "odos",
      name: "Odos",
      chain: "EVM · multi-chain",
      capabilities: "quote · swap",
      body:
        "Odos MCP via @iqai/mcp-odos stdio connector — smart-order routing quotes scored on data accuracy and forbidden-action safety policies.",
      icon: "route" as const,
      ensName: "odos.goldenmcp.eth",
      href: "/leaderboard",
    },
    {
      id: "kyberswap",
      name: "KyberSwap",
      chain: "EVM · multi-chain",
      capabilities: "quote · route",
      body:
        "KyberSwap MCP from github.com/KyberNetwork/kyberswap-mcp — DMM aggregator quotes and route optimization under live eval rotation.",
      icon: "dex" as const,
      ensName: "kyberswap.goldenmcp.eth",
      href: "/leaderboard",
    },
  ],
  centerVendor: {
    id: "jupiter",
    name: "Jupiter",
    chain: "Solana",
    capabilities: "quote · positions",
    body:
      "Jupiter MCP via jupiter-mcp-server — Solana-native swap quotes and position reads, scored on a separate non-EVM track from Base EVM vendors.",
    icon: "solana" as const,
    ensName: "jupiter.goldenmcp.eth",
    href: "/leaderboard",
  },
} as const;
