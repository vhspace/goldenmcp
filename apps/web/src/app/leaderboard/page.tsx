import { fetchLeaderboard } from "@/lib/data";
import Link from "next/link";

export const dynamic = "force-dynamic";

export default async function LeaderboardPage() {
  let entries;
  let error = "";
  try {
    entries = await fetchLeaderboard();
  } catch (e) {
    error = e instanceof Error ? e.message : String(e);
    entries = [];
  }

  return (
    <div>
      <h1>MCP Leaderboard</h1>
      {error && <p style={{ color: "#f66" }}>Error: {error}</p>}
      {entries.length === 0 && !error && <p>No entries — deploy registry and run evals first.</p>}
      <table style={{ width: "100%", borderCollapse: "collapse", marginTop: "1rem" }}>
        <thead>
          <tr style={{ borderBottom: "1px solid #333", textAlign: "left" }}>
            <th style={{ padding: "0.5rem" }}>MCP</th>
            <th>Capability</th>
            <th>Data</th>
            <th>Path</th>
            <th>Token</th>
            <th>Composite</th>
            <th>Failed</th>
          </tr>
        </thead>
        <tbody>
          {entries.map((e) => (
            <tr key={`${e.mcp}-${e.capability}`} style={{ borderBottom: "1px solid #222" }}>
              <td style={{ padding: "0.5rem" }}>
                <Link href={`/mcp/${e.mcp}/${e.capability}`} style={{ color: "#7eb8ff" }}>
                  {e.mcp}
                </Link>
              </td>
              <td>{e.capability}</td>
              <td>{(e.dataScore * 100).toFixed(0)}%</td>
              <td>{(e.pathScore * 100).toFixed(0)}%</td>
              <td>{(e.tokenEfficiency * 100).toFixed(0)}%</td>
              <td>{(e.composite * 100).toFixed(0)}%</td>
              <td>{e.failed ? "YES" : "no"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
