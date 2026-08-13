/**
 * `RequestAck.intent_summary` is a free-form string on the wire (see
 * backend/app/contracts.py) — something like "punjabi · bhangra · high energy".
 * The guest screen shows it as parsed-intent chips, so split defensively on
 * every separator the interpreter might plausibly emit and fall back to the
 * whole string as a single chip.
 */
export function intentChips(summary: string | null | undefined): string[] {
  if (!summary) return [];
  const parts = summary
    .split(/[·•|,;/\n]+/)
    .map((p) => p.trim().replace(/^[-–—\s]+|[-–—\s]+$/g, ""))
    .filter((p) => p.length > 0 && p.length <= 34);

  const source = parts.length > 0 ? parts : [summary.trim()];

  const seen = new Set<string>();
  const chips: string[] = [];
  for (const p of source) {
    const key = p.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    chips.push(p);
    if (chips.length === 6) break;
  }
  return chips;
}

/** "default" is the backend's placeholder event; anything else is a real venue. */
export function prettyEventName(eventId: string | null | undefined): string | null {
  if (!eventId || eventId === "default") return null;
  const cleaned = eventId.replace(/[_-]+/g, " ").trim();
  if (!cleaned) return null;
  return cleaned.replace(/\b\w/g, (c) => c.toUpperCase());
}
