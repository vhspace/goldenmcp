# Marketing landing page (GH #108)

## Reference
Vertex-style dark DeFi hero: floating pill nav, centered headline, gradient bottom glow, dual CTAs.

## Implementation
- `/` → `LandingPage` component (full viewport, own nav)
- App routes (`/demo`, `/leaderboard`, `/ens`) keep compact `SiteNav` via `LayoutShell`
- Copy in `src/lib/landing-content.ts` — tested, no mock endpoints

## Acceptance
- [x] Hero + nav + feature sections
- [x] Enter Demo → `/demo`, secondary → `/leaderboard`
- [x] About / Features / Security anchor sections
- [ ] Optional: link Docs to GitHub README

## Follow-ups
- Custom domain on Vercel (GH #106)
- Mobile hamburger for nav links on small screens
