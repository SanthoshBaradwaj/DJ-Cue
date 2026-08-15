import type { Genre } from "@/lib/types";

// Static mirror of backend/app/genres.py. Shipped with the page rather than
// fetched — this is the very first thing a phone paints after the QR scan,
// and a network round trip before the first tap would defeat the point.
export const GENRES: Genre[] = [
  { key: "punjabi", label: "Punjabi", region: "north" },
  { key: "haryanvi", label: "Haryanvi", region: "north" },
  { key: "bollywood", label: "Bollywood", region: "north" },
  { key: "tamil", label: "Tamil", region: "south" },
  { key: "telugu", label: "Telugu", region: "south" },
];

export function genreLabel(key: string): string {
  return GENRES.find((g) => g.key === key)?.label ?? key;
}
