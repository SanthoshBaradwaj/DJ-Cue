"use client";

import { useState } from "react";
import type { EventRecord } from "@/lib/types";

/**
 * Pick which gig the dashboard is watching, or start a new one.
 *
 * Every request is tied to an event id (`Event` model) so a DJ's requests
 * from "Bellevue Aug 21" never bleed into next week's gig — this is the
 * control for that isolation, not just cosmetics.
 */
export default function EventSwitcher({
  events,
  activeEventId,
  onSelect,
  onCreate,
}: {
  events: EventRecord[];
  activeEventId: string | null;
  onSelect: (id: string) => void;
  onCreate: (name: string) => void;
}) {
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");

  const submitCreate = () => {
    const trimmed = name.trim();
    if (!trimmed) return;
    onCreate(trimmed);
    setName("");
    setCreating(false);
  };

  if (creating) {
    return (
      <form
        className="flex items-center gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          submitCreate();
        }}
      >
        <input
          autoFocus
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="e.g. Bellevue Aug 21"
          className="h-10 min-w-0 flex-1 rounded-lg border border-ink-line bg-ink-raised px-3 text-[13px] text-chalk outline-none focus-visible:ring-2 focus-visible:ring-cue-1/70 sm:h-9 sm:w-48 sm:flex-none"
        />
        <button
          type="submit"
          className="tap h-10 shrink-0 rounded-lg bg-cue-1 px-3 text-[13px] font-semibold text-white sm:h-9"
        >
          Start
        </button>
        <button
          type="button"
          onClick={() => setCreating(false)}
          className="tap h-10 shrink-0 rounded-lg border border-ink-line px-3 text-[13px] text-mist sm:h-9"
        >
          Cancel
        </button>
      </form>
    );
  }

  return (
    <div className="flex items-center gap-2">
      <select
        value={activeEventId ?? ""}
        onChange={(e) => onSelect(e.target.value)}
        className="h-10 min-w-0 flex-1 rounded-lg border border-ink-line bg-ink-raised px-2.5 text-[13px] font-medium text-chalk outline-none focus-visible:ring-2 focus-visible:ring-cue-1/70 sm:h-9 sm:max-w-[13rem] sm:flex-none"
      >
        {events.map((e) => (
          <option key={e.id} value={e.id}>
            {e.name}
            {e.status === "ended" ? " (ended)" : ""}
          </option>
        ))}
      </select>
      <button
        type="button"
        onClick={() => setCreating(true)}
        className="tap h-10 shrink-0 rounded-lg border border-ink-line px-3 text-[13px] font-semibold text-chalk transition-colors active:bg-ink-line/60 sm:h-9"
      >
        + New event
      </button>
    </div>
  );
}
