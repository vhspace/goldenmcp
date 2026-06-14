import Link from "next/link";
import { KeyComponentsSection } from "@/components/landing/KeyComponentsSection";
import { WhyGoldenMcpSection } from "@/components/landing/WhyGoldenMcpSection";
import {
  LANDING_CTA,
  LANDING_HERO,
  LANDING_NAV,
  LANDING_SECURITY,
} from "@/lib/landing-content";
import styles from "./landing.module.css";

export function LandingPage() {
  return (
    <div className={styles.page}>
      <div className={styles.glow} aria-hidden />
      <div className={styles.dotsLeft} aria-hidden />
      <div className={styles.dotsRight} aria-hidden />
      <div className={styles.arcLeft} aria-hidden />
      <div className={styles.arcRight} aria-hidden />

      <header className={styles.navBar}>
        <Link href="/" className={styles.brand}>
          Golden<span className={styles.brandAccent}>MCP</span>
        </Link>
        <nav className={styles.navLinks} aria-label="Primary">
          {LANDING_NAV.map((link) =>
            link.href.startsWith("#") ? (
              <a key={link.href} href={link.href} className={styles.navLink}>
                {link.label}
              </a>
            ) : (
              <Link key={link.href} href={link.href} className={styles.navLink}>
                {link.label}
              </Link>
            ),
          )}
        </nav>
        <Link href={LANDING_CTA.nav.href} className={styles.navCta}>
          {LANDING_CTA.nav.label}
        </Link>
      </header>

      <section className={styles.hero}>
        <h1 className={styles.headline}>{LANDING_HERO.headline}</h1>
        <p className={styles.subcopy}>{LANDING_HERO.subcopy}</p>
        <div className={styles.actions}>
          <Link href={LANDING_CTA.primary.href} className={styles.primaryBtn}>
            {LANDING_CTA.primary.label}
          </Link>
          <Link href={LANDING_CTA.secondary.href} className={styles.secondaryBtn}>
            {LANDING_CTA.secondary.label}
          </Link>
        </div>
      </section>

      <div className={styles.sections}>
        <section id="about">
          <h2 className={styles.sectionTitle}>About GoldenMCP</h2>
          <p className={styles.sectionLead}>
            A hackathon-grade evaluation marketplace for Web3 MCP servers — judges and agents discover
            vendors by live Golden Score, ENS identity, and x402-gated lookup on Arc.
          </p>
        </section>

        <KeyComponentsSection />

        <WhyGoldenMcpSection />

        <section id="security" className={styles.security}>
          <h3>{LANDING_SECURITY.title}</h3>
          <p>{LANDING_SECURITY.body}</p>
        </section>
      </div>
    </div>
  );
}
