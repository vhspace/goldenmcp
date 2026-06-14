/** Vendor marketplace card helpers — pure functions for GH #80. */

export interface LeaderboardEntry {
  mcp: string;
  capability: string;
  dataScore: number;
  pathScore: number;
  tokenEfficiency: number;
  composite: number;
  failed: boolean;
  walrusBlobId: string;
  ensName: string;
  attestationRef: string;
  transcriptHash: string;
}

export type MeterColor = "green" | "yellow" | "red";
export type ScoreTier = "excellent" | "good" | "warning" | "critical";

export interface GoldenScoreBadge {
  percent: number;
  label: string;
  tier: ScoreTier;
}

export interface VendorProfile {
  vendorName: string;
  mcp: string;
  primaryCapability: string;
  goldenScore: number;
  costEfficiency: number;
  reliability: number;
  latencyMs: number | null;
  latencyError: string | null;
  failed: boolean;
  attested: boolean;
  walrusBlobId: string;
  ensRecords: Record<string, string> | null;
  ensError: string | null;
  // ENSv2 subname TTL: expiry timestamp (seconds) and whether it has lapsed.
  // An expired identity stops resolving until the next eval renews it.
  ensExpiry: number | null;
  ensStale: boolean;
}

/** Thresholds documented in the demo UI legend (GH #80). */
export const METER_THRESHOLDS = {
  greenMin: 0.85,
  yellowMin: 0.65,
} as const;

export const GOLDEN_SCORE_THRESHOLDS = {
  excellentMin: 0.9,
  goodMin: 0.75,
  warningMin: 0.5,
} as const;

export function meterColor(value: number): MeterColor {
  if (value >= METER_THRESHOLDS.greenMin) return "green";
  if (value >= METER_THRESHOLDS.yellowMin) return "yellow";
  return "red";
}

export function goldenScoreBadge(composite: number): GoldenScoreBadge {
  const percent = Math.round(Math.max(0, Math.min(1, composite)) * 100);
  if (composite >= GOLDEN_SCORE_THRESHOLDS.excellentMin) {
    return { percent, label: "Excellent", tier: "excellent" };
  }
  if (composite >= GOLDEN_SCORE_THRESHOLDS.goodMin) {
    return { percent, label: "Good", tier: "good" };
  }
  if (composite >= GOLDEN_SCORE_THRESHOLDS.warningMin) {
    return { percent, label: "Warning", tier: "warning" };
  }
  return { percent, label: "Critical", tier: "critical" };
}

export function vendorKey(entry: LeaderboardEntry): string {
  const name = entry.ensName?.trim();
  if (name) return name.toLowerCase();
  return `${entry.mcp}`.toLowerCase();
}

export function aggregateVendorProfiles(entries: LeaderboardEntry[]): VendorProfile[] {
  const byVendor = new Map<string, LeaderboardEntry[]>();
  for (const entry of entries) {
    const key = vendorKey(entry);
    const group = byVendor.get(key) ?? [];
    group.push(entry);
    byVendor.set(key, group);
  }

  const profiles: VendorProfile[] = [];
  for (const group of byVendor.values()) {
    const primary = group.reduce((best, cur) =>
      cur.composite > best.composite ? cur : best,
    );
    profiles.push({
      vendorName: primary.ensName?.trim() || primary.mcp,
      mcp: primary.mcp,
      primaryCapability: primary.capability,
      goldenScore: primary.composite,
      costEfficiency: primary.tokenEfficiency,
      reliability: primary.dataScore,
      latencyMs: null,
      latencyError: null,
      failed: primary.failed,
      attested: Boolean(primary.attestationRef?.trim()),
      walrusBlobId: primary.walrusBlobId,
      ensRecords: null,
      ensError: null,
      ensExpiry: null,
      ensStale: false,
    });
  }

  return profiles.sort((a, b) => b.goldenScore - a.goldenScore);
}

/** Extract eval wall-clock duration from a real Inspect eval log JSON object. */
export function extractLatencyMsFromEvalLog(log: Record<string, unknown>): number | null {
  const stats = log.stats;
  if (stats && typeof stats === "object" && stats !== null) {
    const totalTime = (stats as Record<string, unknown>).total_time;
    if (typeof totalTime === "number" && totalTime > 0) {
      return Math.round(totalTime * 1000);
    }
  }
  return null;
}

/** Map latency ms to a 0–1 meter (lower latency = higher score). */
export function latencyMeterValue(latencyMs: number): number {
  if (latencyMs <= 2000) return 0.95;
  if (latencyMs <= 5000) return 0.8;
  if (latencyMs <= 15000) return 0.65;
  if (latencyMs <= 30000) return 0.45;
  return 0.25;
}

export function formatLatencyMs(latencyMs: number | null): string {
  if (latencyMs === null) return "—";
  if (latencyMs < 1000) return `${latencyMs} ms`;
  return `${(latencyMs / 1000).toFixed(1)} s`;
}
