import { LANDING_KEY_COMPONENTS } from "@/lib/landing-content";
import styles from "./landing.module.css";

function HeroGraphic() {
  return (
    <div className={styles.heroGraphic} aria-hidden>
      <div className={styles.hexGlow} />
      <svg className={styles.hexSvg} viewBox="0 0 200 200" fill="none">
        <polygon
          points="100,18 178,63 178,137 100,182 22,137 22,63"
          stroke="url(#hexStroke)"
          strokeWidth="1.5"
          fill="rgba(8,12,18,0.85)"
        />
        <polygon
          points="100,42 154,73 154,127 100,158 46,127 46,73"
          stroke="rgba(56,189,248,0.35)"
          strokeWidth="1"
          fill="rgba(12,18,28,0.9)"
        />
        <defs>
          <linearGradient id="hexStroke" x1="22" y1="18" x2="178" y2="182">
            <stop offset="0%" stopColor="#38bdf8" />
            <stop offset="100%" stopColor="#2dd4bf" />
          </linearGradient>
        </defs>
        <text
          x="100"
          y="108"
          textAnchor="middle"
          fill="#e2e8f0"
          fontSize="28"
          fontWeight="700"
          fontFamily="system-ui, sans-serif"
        >
          MCP
        </text>
      </svg>
      <div className={styles.hexBeamLeft} />
      <div className={styles.hexBeamRight} />
    </div>
  );
}

function SubPanelIcon({ id }: { id: string }) {
  if (id === "walrus") {
    return (
      <span className={styles.subPanelIcon} aria-hidden>
        <svg viewBox="0 0 24 24" width="18" height="18" fill="none">
          <ellipse cx="12" cy="14" rx="8" ry="4" stroke="currentColor" strokeWidth="1.5" />
          <path d="M4 14c0-4 3.5-7 8-7s8 3 8 7" stroke="currentColor" strokeWidth="1.5" />
        </svg>
      </span>
    );
  }
  return (
    <span className={styles.subPanelIcon} aria-hidden>
      <svg viewBox="0 0 24 24" width="18" height="18" fill="none">
        <path
          d="M12 3l7 4v10l-7 4-7-4V7l7-4z"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinejoin="round"
        />
        <path d="M12 12l7-4M12 12v9M12 12L5 8" stroke="currentColor" strokeWidth="1.5" />
      </svg>
    </span>
  );
}

function CardIcon({ icon }: { icon: "inspect" | "cai" | "x402" }) {
  return (
    <span className={styles.cardIcon} aria-hidden>
      {icon === "inspect" && (
        <svg viewBox="0 0 24 24" width="20" height="20" fill="none">
          <circle cx="12" cy="12" r="3" stroke="currentColor" strokeWidth="1.5" />
          <path
            d="M12 3v3M12 18v3M3 12h3M18 12h3M5.6 5.6l2.1 2.1M16.3 16.3l2.1 2.1M5.6 18.4l2.1-2.1M16.3 7.7l2.1-2.1"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
          />
        </svg>
      )}
      {icon === "cai" && (
        <svg viewBox="0 0 24 24" width="20" height="20" fill="none">
          <rect x="5" y="8" width="14" height="12" rx="2" stroke="currentColor" strokeWidth="1.5" />
          <path d="M9 8V6a3 3 0 016 0v2" stroke="currentColor" strokeWidth="1.5" />
          <circle cx="12" cy="14" r="1.5" fill="currentColor" />
        </svg>
      )}
      {icon === "x402" && (
        <svg viewBox="0 0 24 24" width="20" height="20" fill="none">
          <circle cx="12" cy="12" r="8" stroke="currentColor" strokeWidth="1.5" />
          <path d="M12 8v8M9 11h6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
        </svg>
      )}
    </span>
  );
}

export function KeyComponentsSection() {
  const { sectionTitle, hero, cards } = LANDING_KEY_COMPONENTS;

  return (
    <section id="components" className={styles.componentsSection}>
      <h2 className={styles.componentsTitle}>{sectionTitle}</h2>

      <article className={styles.heroCard}>
        <HeroGraphic />
        <div className={styles.heroContent}>
          <h3 className={styles.heroCardTitle}>{hero.title}</h3>
          <p className={styles.heroCardBody}>{hero.body}</p>
          <div className={styles.subPanelGrid}>
            {hero.subPanels.map((panel) => (
              <div key={panel.id} className={styles.subPanel}>
                <div className={styles.subPanelHead}>
                  <SubPanelIcon id={panel.id} />
                  <h4>{panel.title}</h4>
                </div>
                <p>{panel.body}</p>
              </div>
            ))}
          </div>
        </div>
      </article>

      <div className={styles.componentGrid}>
        {cards.map((card) => (
          <article key={card.id} className={styles.componentCard}>
            <CardIcon icon={card.icon} />
            <h3>{card.title}</h3>
            <p>{card.body}</p>
          </article>
        ))}
      </div>
    </section>
  );
}
