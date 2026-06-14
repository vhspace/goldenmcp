import { Funnel_Display, Funnel_Sans } from "next/font/google";

/** Scoped to `/` landing — Funnel Sans body, Funnel Display headings. */
export const funnelSans = Funnel_Sans({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-funnel-sans",
});

export const funnelDisplay = Funnel_Display({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-funnel-display",
});

export const landingFontClassName = `${funnelSans.variable} ${funnelDisplay.variable}`;
