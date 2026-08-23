import type { Genre } from "@/lib/types";

// Static mirror of backend/app/genres.py. Shipped with the page rather than
// fetched — this is the very first thing a phone paints after the QR scan,
// and a network round trip before the first tap would defeat the point.
//
// Deliberately interleaved north/south rather than grouped — the grid reads
// this order left-to-right, top-to-bottom, and a grouped order would put
// one region's buttons visually first/bigger every single time. `region` is
// kept on the type for internal use (analytics, catalog search bias) but is
// never rendered as a section label in the guest UI.
export const GENRES: Genre[] = [
  { key: "punjabi", label: "Punjabi", region: "north" },
  { key: "tamil", label: "Tamil", region: "south" },
  { key: "haryanvi", label: "Haryanvi", region: "north" },
  { key: "telugu", label: "Telugu", region: "south" },
  { key: "kannada", label: "Kannada", region: "south" },
  { key: "malayalam", label: "Malayalam", region: "south" },
  { key: "marathi", label: "Marathi", region: "other" },
  { key: "bollywood", label: "Bollywood", region: "north" },
  { key: "english", label: "English", region: "other" },
  { key: "edm", label: "EDM / Trap", region: "other" },
  // Catch-all so a guest whose song doesn't fit any bucket above can still
  // request it. Last on purpose -- it's the fallback, not a fifth option
  // worth equal billing with the rest of the grid.
  { key: "other", label: "More", region: "other" },
];

export function genreLabel(key: string): string {
  return GENRES.find((g) => g.key === key)?.label ?? key;
}

// One accent per genre, purely for visual identity on the genre grid and to
// tie a queued request's rank badge back to what it was requested as. A
// deliberately muted, coordinated set (moderate saturation, similar
// lightness) rather than a full-saturation rainbow -- meant to feel like a
// designed palette at a glance, not a kids'-app color wheel. "other" gets a
// neutral tone on purpose -- it isn't a real genre identity to color.
const GENRE_COLOR: Record<string, string> = {
  punjabi: "#ff8a63",
  tamil: "#2ec4b6",
  haryanvi: "#f0b94d",
  telugu: "#5b9bf0",
  kannada: "#d97757",
  malayalam: "#4fb88a",
  marathi: "#b18cf0",
  bollywood: "#f2739a",
  english: "#6fcf97",
  edm: "#4fd1e8",
  other: "#9aa1ac",
};
const DEFAULT_GENRE_COLOR = "#9aa1ac";

export function genreColor(key: string): string {
  return GENRE_COLOR[key] ?? DEFAULT_GENRE_COLOR;
}

/**
 * What a tap on the opening screen actually hands back to the rest of the
 * guest flow, regardless of whether the tile came from the static 9-genre
 * grid or a DJ's configured bucket list:
 * - `genre`: the real genre key stored on the submitted request (so it
 *   lands in the right DJ dashboard bucket) and used for the trending seed.
 * - `label`: what the next screen's header shows -- the bucket's own label
 *   ("South Indian") when in bucket mode, never a narrower key underneath it.
 * - `biasSearch`: whether catalog search should be nudged toward `genre`.
 *   False whenever a bucket spans more than one underlying language (e.g.
 *   "South Indian" = Tamil + Telugu) -- there's no single language to bias
 *   toward, so search runs unbiased on the typed text alone.
 */
export interface GenrePick {
  genre: string;
  label: string;
  biasSearch: boolean;
}
