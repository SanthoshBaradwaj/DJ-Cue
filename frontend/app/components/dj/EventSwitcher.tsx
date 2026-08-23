"use client";

import type { EventRecord } from "@/lib/types";

/**
 * Pick which gig the dashboard is watching.
 *
 * Every request is tied to an event id (`Event` model) so a DJ's requests
 * from "Bellevue Aug 21" never bleed into next week's gig — this is the
 * control for that isolation, not just cosmetics.
 *
 * Creating new events from the UI is deliberately not exposed yet; a single
 * default event is provisioned server-side for now.
 */
export default function EventSwitcher({
  events,
  activeEventId,
  onSelect,
}: {
  events: EventRecord[];
  activeEventId: string | null;
  onSelect: (id: string) => void;
}) {
  return (
    <select
      value={activeEventId ?? ""}
      onChange={(e) => onSelect(e.target.value)}
      className="h-10 min-w-0 flex-1 rounded-lg border border-ink-line bg-ink-raised px-2.5 text-[15px] font-medium text-chalk outline-none focus-visible:ring-2 focus-visible:ring-cue-1/70 sm:h-9 sm:max-w-[13rem] sm:flex-none"
    >
      {events.map((e) => (
        <option key={e.id} value={e.id}>
          {e.name}
          {e.status === "ended" ? " (ended)" : ""}
        </option>
      ))}
    </select>
  );
}
