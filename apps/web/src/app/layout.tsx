export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body style={{ fontFamily: "system-ui, sans-serif", margin: 0, background: "#0a0a0f", color: "#e8e8ef" }}>
        <nav style={{ padding: "1rem 2rem", borderBottom: "1px solid #222", display: "flex", gap: "1.5rem" }}>
          <a href="/" style={{ color: "#7eb8ff", textDecoration: "none" }}>GoldenMCP</a>
          <a href="/demo" style={{ color: "#aaa", textDecoration: "none" }}>Marketplace</a>
          <a href="/leaderboard" style={{ color: "#aaa", textDecoration: "none" }}>Leaderboard</a>
          <a href="/ens" style={{ color: "#aaa", textDecoration: "none" }}>ENS Resolver</a>
        </nav>
        <main style={{ padding: "2rem" }}>{children}</main>
      </body>
    </html>
  );
}
