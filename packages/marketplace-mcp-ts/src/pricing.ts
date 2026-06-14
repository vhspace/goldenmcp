export const BASE_USDC = Number(process.env.BASE_USDC ?? "0.01");

/** Tiered price in USDC: base * (1 + 4 * min_score). */
export function priceForThreshold(minScore: number, baseUsdc = BASE_USDC): number {
  const clamped = Math.max(0, Math.min(1, minScore));
  return baseUsdc * (1 + 4 * clamped);
}

/** Price as a dollar string for gateway.require(), e.g. "$0.0500". */
export function priceString(minScore: number, baseUsdc = BASE_USDC): string {
  return `$${priceForThreshold(minScore, baseUsdc).toFixed(4)}`;
}
