import Link from "next/link";
import { GoldenMcpLogo } from "@/components/GoldenMcpLogo";

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
        alignItems: "center",
        gap: "1.5rem",
        flexWrap: "wrap",
      }}
    >
      <GoldenMcpLogo size="sm" />
      {LINKS.map((link) => (
        <Link key={link.href} href={link.href} style={{ color: "#aaa", textDecoration: "none" }}>
          {link.label}
        </Link>
      ))}
    </nav>
  );
}
