"use client";

import type { EventRecord, EventStats } from "@/lib/types";
import type { FeedStatus } from "./useDashboardFeed";
import EventSwitcher from "./EventSwitcher";

function StatusPill({ status }: { status: FeedStatus }) {
  const live = status === "live";
  const polling = status === "polling";
  const color = live ? "var(--color-go)" : polling ? "var(--color-hold)" : "var(--color-mist)";
  const label = live ? "LIVE" : polling ? "POLLING" : "CONNECTING";

  return (
    <div
      className="inline-flex shrink-0 items-center gap-2 rounded-full border px-3 py-1.5"
      style={{
        borderColor: `color-mix(in oklab, ${color} 38%, transparent)`,
        background: `color-mix(in oklab, ${color} 11%, transparent)`,
      }}
      role="status"
      aria-live="polite"
      aria-label={`Feed status: ${label}`}
    >
      <span className="relative flex h-2 w-2">
        {live && (
          <span className="absolute inset-0 rounded-full animate-pulse-ring" style={{ background: color }} />
        )}
        <span className="relative h-2 w-2 rounded-full" style={{ background: color }} />
      </span>
      <span className="text-[11px] font-bold tracking-[0.16em]" style={{ color }}>
        {label}
      </span>
    </div>
  );
}

function MicroStat({ value, label }: { value: string; label: string }) {
  return (
    <div className="flex flex-col items-end leading-tight">
      <span className="tnum text-sm font-semibold text-chalk/85">{value}</span>
      <span className="text-[10px] uppercase tracking-[0.14em] text-mist/60">{label}</span>
    </div>
  );
}

export function TopBar({
  events,
  activeEventId,
  onSelectEvent,
  onCreateEvent,
  stats,
  status,
}: {
  events: EventRecord[];
  activeEventId: string | null;
  onSelectEvent: (id: string) => void;
  onCreateEvent: (name: string) => void;
  stats: EventStats | null;
  status: FeedStatus;
}) {
  return (
    <header className="sticky top-0 z-30 shrink-0 border-b border-ink-line/80 bg-ink/85 backdrop-blur-xl">
      <div className="flex flex-wrap items-center gap-4 px-5 py-3.5 xl:gap-6 xl:px-8">
        <div className="flex min-w-0 shrink-0 items-center gap-3.5">
          <div className="flex items-baseline gap-[1px]">
            <span className="text-2xl font-black tracking-[-0.04em]" style={{ color: "var(--color-cue-1)" }}>
              DJ
            </span>
            <span className="text-2xl font-black tracking-[-0.04em] text-chalk">-CUE</span>
          </div>
          <span className="h-6 w-px bg-ink-line" aria-hidden="true" />
          <EventSwitcher
            events={events}
            activeEventId={activeEventId}
            onSelect={onSelectEvent}
            onCreate={onCreateEvent}
          />
        </div>

        <div className="ml-auto flex shrink-0 items-center gap-5">
          {stats && (
            <div className="hidden items-center gap-5 sm:flex">
              <MicroStat value={String(stats.total_requests)} label="requests" />
              <MicroStat value={String(stats.unique_songs)} label="songs" />
              <MicroStat value={String(stats.unique_sessions)} label="phones" />
            </div>
          )}
          <StatusPill status={status} />
        </div>
      </div>
    </header>
  );
}
