import Link from "next/link";

const LINKS = [
  { href: "/demo", label: "Marketplace" },
  { href: "/leaderboard", label: "Leaderboard" },
  { href: "/ens", label: "ENS Resolver" },
] as const;

export function SiteNav() {
  return (
    <nav
      style={{
        padding: "1rem 2rem",
        borderBottom: "1px solid #222",
        display: "flex",
        gap: "1.5rem",
        flexWrap: "wrap",
      }}
    >
      <Link href="/" style={{ color: "#7eb8ff", textDecoration: "none", fontWeight: 600 }}>
        GoldenMCP
      </Link>
      {LINKS.map((link) => (
        <Link key={link.href} href={link.href} style={{ color: "#aaa", textDecoration: "none" }}>
          {link.label}
        </Link>
      ))}
    </nav>
  );
}
