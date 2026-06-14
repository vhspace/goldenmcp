import Link from "next/link";

export default function Home() {
  return (
    <div>
      <h1>GoldenMCP</h1>
      <p>Web3 MCP evaluation marketplace — Walrus-backed scores, ENS identity, Chainlink attestation, x402 on Arc.</p>
      <ul>
        <li><Link href="/demo">Marketplace</Link> — vendor performance cards (ENS + Golden Score)</li>
        <li><Link href="/leaderboard">Leaderboard</Link> — live scores from Arc registry + Walrus</li>
        <li><Link href="/ens">ENS Resolver</Link> — resolve MCP names to endpoints and eval blobs</li>
      </ul>
      <p style={{ color: "#888", marginTop: "2rem" }}>
        x402 lookup demo: <code>cd packages/marketplace-mcp-ts && bun demo/lookup_agent.ts --capability quote --min-score 0.9</code>
      </p>
    </div>
  );
}
