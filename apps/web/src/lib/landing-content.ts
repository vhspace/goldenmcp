/** Marketing landing copy — GH #108 */

export const LANDING_NAV = [
  { label: "About", href: "#about" },
  { label: "Features", href: "#features" },
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
