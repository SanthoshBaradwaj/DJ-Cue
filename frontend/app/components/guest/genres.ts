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
  { key: "marathi", label: "Marathi", region: "other" },
  { key: "bollywood", label: "Bollywood", region: "north" },
  { key: "english", label: "English", region: "other" },
  { key: "edm", label: "EDM / Trap", region: "other" },
];

export function genreLabel(key: string): string {
  return GENRES.find((g) => g.key === key)?.label ?? key;
}
