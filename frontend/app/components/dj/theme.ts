// Visual vocabulary for the DJ dashboard. Colour is used only to rank: the
// hottest wave is cue-1, and every wave steps down from there. Nothing here
// invents a token — it all resolves against app/globals.css.

import type { EventStats, Wave } from "@/lib/types";

/** Rank -> accent. Anything past 5th place shares the muted tail colour. */
export const WAVE_ACCENTS = [
  "var(--color-cue-1)",
  "var(--color-cue-2)",
  "var(--color-cue-3)",
  "var(--color-cue-4)",
  "var(--color-cue-5)",
] as const;

export function waveAccent(rank: number): string {
  return WAVE_ACCENTS[Math.min(Math.max(rank, 0), WAVE_ACCENTS.length - 1)];
}

/** `color-mix` wrapper so tinted fills read as one line at the call site. */
export function tint(accent: string, pct: number): string {
  return `color-mix(in oklab, ${accent} ${pct}%, transparent)`;
}

export function clamp01(n: number): number {
  if (!Number.isFinite(n)) return 0;
  return Math.min(1, Math.max(0, n));
}

/**
 * `share` is documented as a fraction but a backend that ships percentages
 * would silently blow the bar off the card, so normalise defensively and fall
 * back to deriving it from the raw counts.
 */
export function waveShare(wave: Wave, totalRequests: number): number {
  const raw = wave.share;
  if (Number.isFinite(raw) && raw > 0) {
    return clamp01(raw > 1 ? raw / 100 : raw);
  }
  if (totalRequests > 0) return clamp01(wave.raw_count / totalRequests);
  return 0;
}

/**
 * The compression headline is the product thesis, so it must never render NaN.
 * `compression_ratio` could plausibly arrive as waves/requests (0..1) or as a
 * fold factor (11.75x); both collapse to the same percentage, and if it is
 * missing entirely we derive it from the counts we already show.
 */
export function compressionPct(stats: EventStats): number | null {
  const { total_requests: total, wave_count: waves, compression_ratio: r } = stats;
  let ratio: number | null = null;
  if (Number.isFinite(r) && r > 0) ratio = r > 1 ? 1 / r : r;
  else if (total > 0 && waves > 0) ratio = waves / total;
  if (ratio === null) return null;
  return Math.round(clamp01(1 - ratio) * 100);
}

export function fmtDuration(sec: number): string {
  if (!Number.isFinite(sec) || sec < 0) return "0:00";
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return `${m}:${String(s).padStart(2, "0")}`;
}

/** Backends disagree about epoch units; accept either without a stale bar. */
export function toMillis(ts: number | null | undefined): number | null {
  if (ts === null || ts === undefined || !Number.isFinite(ts)) return null;
  return ts > 1e11 ? ts : ts * 1000;
}
