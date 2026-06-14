"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import styles from "./demo-dashboard.module.css";

const SIDE_NAV = [
  { href: "/demo", label: "Marketplace", icon: "◫" },
  { href: "/leaderboard", label: "Leaderboard", icon: "▤" },
  { href: "/ens", label: "ENS Resolver", icon: "◎" },
  { href: "/", label: "Home", icon: "⌂" },
] as const;

interface DemoDashboardLayoutProps {
  children: React.ReactNode;
  rightRail?: React.ReactNode;
}

export function DemoDashboardLayout({ children, rightRail }: DemoDashboardLayoutProps) {
  const pathname = usePathname();

  return (
    <div className={styles.shell}>
      <aside className={styles.sidebar}>
        <Link href="/" className={styles.brand}>
          Golden<span className={styles.brandAccent}>MCP</span>
        </Link>
        <nav className={styles.sideNav} aria-label="Demo dashboard">
          {SIDE_NAV.map((item) => {
            const active = pathname === item.href || (item.href === "/demo" && pathname.startsWith("/demo"));
            return (
              <Link
                key={item.href}
                href={item.href}
                className={active ? `${styles.sideLink} ${styles.sideLinkActive}` : styles.sideLink}
              >
                <span className={styles.sideIcon} aria-hidden>
                  {item.icon}
                </span>
                {item.label}
              </Link>
            );
          })}
        </nav>
        <div className={styles.sideFooter}>
          <p className={styles.sideFooterTitle}>Judge demo mode</p>
          <p className={styles.sideFooterText}>
            Live Arc registry, Walrus manifests, and x402 marketplace lookup — no mock vendors.
          </p>
        </div>
      </aside>

      <div className={styles.mainColumn}>
        <header className={styles.topBar}>
          <div className={styles.topLinks}>
            <Link href="/demo" className={styles.topLink}>
              All MCPs
            </Link>
            <Link href="/leaderboard" className={styles.topLink}>
              Scores
            </Link>
            <Link href="/demo" className={styles.topLink}>
              Trade
            </Link>
            <Link href="/ens" className={styles.topLink}>
              Identity
            </Link>
          </div>
          <div className={styles.topUtilities}>
            <span>Arc testnet</span>
            <span>·</span>
            <span>x402 USDC</span>
          </div>
        </header>

        <div className={styles.contentRow}>
          <main className={styles.main}>{children}</main>
          {rightRail ? <aside className={styles.rightRail}>{rightRail}</aside> : null}
        </div>
      </div>
    </div>
  );
}

export { styles as demoDashboardStyles };
