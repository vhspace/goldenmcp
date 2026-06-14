import { LANDING_SPONSOR_TRACKS } from "@/lib/landing-content";
import styles from "./landing.module.css";

export function SponsorTracksSection() {
  const { sectionTitle, sectionLead, tracks } = LANDING_SPONSOR_TRACKS;

  return (
    <section id="tracks" className={styles.tracksSection}>
      <h2 className={styles.tracksTitle}>{sectionTitle}</h2>
      <p className={styles.tracksLead}>{sectionLead}</p>

      <ul className={styles.tracksRow} aria-label="Hackathon sponsor tracks">
        {tracks.map((track) => (
          <li key={track.id}>
            <a
              href={track.href}
              className={styles.trackLink}
              target="_blank"
              rel="noopener noreferrer"
              aria-label={`${track.name} — ${track.integration}`}
            >
              <div className={styles.trackLogoWell}>
                <img
                  src={track.logoSrc}
                  alt={`${track.name} logo`}
                  className={styles.trackLogoImg}
                  loading="lazy"
                />
              </div>
              <div className={styles.trackBody}>
                <span className={styles.trackName}>{track.name}</span>
                <span className={styles.trackIntegration}>{track.integration}</span>
                <span className={styles.trackCta}>
                  Visit site
                  <svg viewBox="0 0 16 16" width="12" height="12" aria-hidden>
                    <path
                      d="M4 12L12 4M12 4H6M12 4v6"
                      stroke="currentColor"
                      strokeWidth="1.5"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      fill="none"
                    />
                  </svg>
                </span>
              </div>
            </a>
          </li>
        ))}
      </ul>
    </section>
  );
}
