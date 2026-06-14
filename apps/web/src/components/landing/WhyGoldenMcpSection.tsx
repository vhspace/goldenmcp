import { LANDING_WHY } from "@/lib/landing-content";
import styles from "./landing.module.css";

function ScoresVisual() {
  return (
    <div className={styles.whyVisualInner} aria-hidden>
      <div className={`${styles.whyBubble} ${styles.whyBubbleSm}`} style={{ top: "12%", left: "8%" }}>
        91%
      </div>
      <div className={`${styles.whyBubble} ${styles.whyBubbleSm}`} style={{ top: "18%", right: "10%" }}>
        88%
      </div>
      <div className={`${styles.whyBubble} ${styles.whyBubbleSm}`} style={{ bottom: "16%", left: "14%" }}>
        94%
      </div>
      <div className={styles.whyGlassCenter}>
        <span className={styles.whyGlassLabel}>Golden Score</span>
        <strong>97%</strong>
        <span className={styles.whyGlassSub}>lifi · quote</span>
      </div>
    </div>
  );
}

function PricingVisual() {
  return (
    <div className={styles.whyVisualInner} aria-hidden>
      <div className={styles.whyOfferBadge}>BEST MCP</div>
      <div className={styles.whyPriceBar}>
        <span className={styles.whyPriceBrand}>
          Golden<span>MCP</span>
        </span>
        <span className={styles.whyPriceAmount}>$0.002 USDC</span>
      </div>
      <p className={styles.whyPriceHint}>x402 · min score ≥ 90%</p>
    </div>
  );
}

function CoverageVisual() {
  const nodes = ["Li.FI", "1inch", "Jupiter", "Odos"];
  return (
    <div className={styles.whyVisualInner} aria-hidden>
      <div className={styles.whyHubRow}>
        {nodes.map((label) => (
          <span key={label} className={styles.whyNode}>
            {label}
          </span>
        ))}
        <div className={styles.whyHubCore}>
          <span>MCP</span>
        </div>
      </div>
    </div>
  );
}

function TrustVisual() {
  return (
    <div className={styles.whyVisualInner} aria-hidden>
      <div className={`${styles.whyTrustSide} ${styles.whyTrustLeft}`}>
        <svg viewBox="0 0 16 16" width="14" height="14" fill="none" aria-hidden>
          <rect x="3" y="7" width="10" height="7" rx="1" stroke="currentColor" strokeWidth="1.2" />
          <path d="M5 7V5a3 3 0 016 0v2" stroke="currentColor" strokeWidth="1.2" />
        </svg>
        TEE Attested
      </div>
      <div className={styles.whyShield}>
        <svg viewBox="0 0 48 56" width="40" height="46" fill="none">
          <path
            d="M24 4L42 12v14c0 12-8 22-18 26C14 48 6 38 6 26V12L24 4z"
            stroke="currentColor"
            strokeWidth="2"
            fill="rgba(56,189,248,0.15)"
          />
          <path d="M16 28l6 6 12-14" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" />
        </svg>
        <span>PROTECTED</span>
      </div>
      <div className={`${styles.whyTrustSide} ${styles.whyTrustRight}`}>
        <svg viewBox="0 0 16 16" width="14" height="14" fill="none" aria-hidden>
          <path d="M3 8l4 4 6-7" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
        </svg>
        On-Chain Proof
      </div>
    </div>
  );
}

const VISUALS = {
  scores: ScoresVisual,
  pricing: PricingVisual,
  coverage: CoverageVisual,
  trust: TrustVisual,
} as const;

export function WhyGoldenMcpSection() {
  return (
    <section id="features" className={styles.whySection}>
      <h2 className={styles.whyTitle}>{LANDING_WHY.sectionTitle}</h2>
      <div className={styles.whyGrid}>
        {LANDING_WHY.cards.map((card) => {
          const Visual = VISUALS[card.visual];
          return (
            <article key={card.id} className={styles.whyCard}>
              <div className={styles.whyVisual}>
                <Visual />
              </div>
              <h3>{card.title}</h3>
              <p>{card.body}</p>
            </article>
          );
        })}
      </div>
    </section>
  );
}
