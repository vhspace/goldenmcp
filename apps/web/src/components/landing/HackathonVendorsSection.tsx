import Link from "next/link";
import { LANDING_VENDORS } from "@/lib/landing-content";
import styles from "./landing.module.css";

type VendorIcon = "bridge" | "aggregator" | "route" | "dex" | "solana";

function VendorIconGlyph({ icon }: { icon: VendorIcon }) {
  return (
    <span className={styles.vendorIcon} aria-hidden>
      {icon === "bridge" && (
        <svg viewBox="0 0 24 24" width="20" height="20" fill="none">
          <path d="M4 12h16M12 4v16" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
          <circle cx="6" cy="12" r="2" stroke="currentColor" strokeWidth="1.5" />
          <circle cx="18" cy="12" r="2" stroke="currentColor" strokeWidth="1.5" />
        </svg>
      )}
      {icon === "aggregator" && (
        <svg viewBox="0 0 24 24" width="20" height="20" fill="none">
          <circle cx="12" cy="12" r="3" stroke="currentColor" strokeWidth="1.5" />
          <path
            d="M12 3v3M12 18v3M3 12h3M18 12h3"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
          />
        </svg>
      )}
      {icon === "route" && (
        <svg viewBox="0 0 24 24" width="20" height="20" fill="none">
          <path
            d="M5 18c0-3 2-5 5-5h4c2 0 3-1 3-3s-1-3-3-3"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
          />
          <circle cx="5" cy="18" r="2" stroke="currentColor" strokeWidth="1.5" />
        </svg>
      )}
      {icon === "dex" && (
        <svg viewBox="0 0 24 24" width="20" height="20" fill="none">
          <path d="M6 16l6-12 6 12H6z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
          <path d="M9 13h6" stroke="currentColor" strokeWidth="1.5" />
        </svg>
      )}
      {icon === "solana" && (
        <svg viewBox="0 0 24 24" width="20" height="20" fill="none">
          <path
            d="M6 16l4-4-4-4M14 16l4-4-4-4"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      )}
    </span>
  );
}

function VendorCell({
  name,
  chain,
  capabilities,
  body,
  icon,
  ensName,
  href,
}: {
  name: string;
  chain: string;
  capabilities: string;
  body: string;
  icon: VendorIcon;
  ensName: string;
  href: string;
}) {
  return (
    <article className={styles.vendorCell}>
      <VendorIconGlyph icon={icon} />
      <h3>{name}</h3>
      <p className={styles.vendorMeta}>
        {chain} · {capabilities}
      </p>
      <p className={styles.vendorBody}>{body}</p>
      <Link href={href} className={styles.vendorEns}>
        {ensName}
      </Link>
    </article>
  );
}

export function HackathonVendorsSection() {
  const { sectionTitle, sectionLead, center, quadrants, centerVendor } = LANDING_VENDORS;

  return (
    <section id="vendors" className={styles.vendorsSection}>
      <h2 className={styles.vendorsTitle}>{sectionTitle}</h2>
      <p className={styles.vendorsLead}>{sectionLead}</p>

      <div className={styles.vendorsCrossWrap}>
        <div className={styles.vendorsCross}>
          {quadrants.map((vendor) => (
            <VendorCell key={vendor.id} {...vendor} />
          ))}
        </div>

        <div className={styles.vendorsCenterHub} aria-label={`${center.label} — ${centerVendor.name}`}>
          <div className={styles.vendorsCenterRing} aria-hidden />
          <div className={styles.vendorsCenterCore}>
            <VendorIconGlyph icon={centerVendor.icon} />
            <strong>{centerVendor.name}</strong>
            <span className={styles.vendorsCenterSub}>{centerVendor.chain}</span>
            <span className={styles.vendorsCenterCap}>{centerVendor.capabilities}</span>
          </div>
        </div>
      </div>

      <p className={styles.vendorsCenterBlurb}>{centerVendor.body}</p>
      <p className={styles.vendorsFootnote}>
        {center.sublabel} on Arc via{" "}
        <code className={styles.vendorsCode}>MCPRegistry</code> — view live Golden Scores on the{" "}
        <Link href="/leaderboard">leaderboard</Link> or run the{" "}
        <Link href="/demo">marketplace demo</Link>.
      </p>
    </section>
  );
}
