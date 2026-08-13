"use client";

import type { EventStats } from "@/lib/types";
import type { FeedStatus } from "./useDashboardFeed";
import { compressionPct } from "./theme";

function StatusPill({ status }: { status: FeedStatus }) {
  const live = status === "live";
  const polling = status === "polling";
  const color = live
    ? "var(--color-go)"
    : polling
      ? "var(--color-hold)"
      : "var(--color-mist)";
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
          <span
            className="absolute inset-0 rounded-full animate-pulse-ring"
            style={{ background: color }}
          />
        )}
        <span className="relative h-2 w-2 rounded-full" style={{ background: color }} />
      </span>
      <span
        className="text-[11px] font-bold tracking-[0.16em]"
        style={{ color }}
      >
        {label}
      </span>
    </div>
  );
}

function MicroStat({ value, label }: { value: string; label: string }) {
  return (
    <div className="flex flex-col items-end leading-tight">
      <span className="tnum text-sm font-semibold text-chalk/85">{value}</span>
      <span className="text-[10px] uppercase tracking-[0.14em] text-mist/60">
        {label}
      </span>
    </div>
  );
}

export function TopBar({
  eventName,
  stats,
  status,
}: {
  eventName: string;
  stats: EventStats;
  status: FeedStatus;
}) {
  const pct = compressionPct(stats);

  return (
    <header className="sticky top-0 z-30 shrink-0 border-b border-ink-line/80 bg-ink/85 backdrop-blur-xl">
      <div className="flex items-center gap-5 px-5 py-3.5 xl:gap-8 xl:px-8">
        {/* Identity */}
        <div className="flex min-w-0 shrink-0 items-center gap-3.5">
          <div className="flex items-baseline gap-[1px]">
            <span
              className="text-2xl font-black tracking-[-0.04em]"
              style={{ color: "var(--color-cue-1)" }}
            >
              C
            </span>
            <span className="text-2xl font-black tracking-[-0.04em] text-chalk">
              UE
            </span>
          </div>
          <span className="h-6 w-px bg-ink-line" aria-hidden="true" />
          <div className="min-w-0 leading-tight">
            <p className="truncate text-sm font-semibold text-chalk/90">
              {eventName}
            </p>
            <p className="text-[10px] uppercase tracking-[0.16em] text-mist/60">
              DJ Booth
            </p>
          </div>
        </div>

        {/* The thesis: raw noise on the left, actionable waves on the right. */}
        <div className="flex min-w-0 flex-1 items-center justify-center">
          <div className="flex items-center gap-4 sm:gap-5">
            <div className="flex flex-col items-end leading-none">
              <span className="tnum text-3xl font-bold text-chalk xl:text-[2.6rem]">
                {stats.total_requests}
              </span>
              <span className="mt-1 text-[10px] uppercase tracking-[0.18em] text-mist/70">
                requests
              </span>
            </div>

            <svg
              viewBox="0 0 34 12"
              className="h-3 w-8 shrink-0 text-mist/45"
              fill="none"
              aria-hidden="true"
            >
              <path
                d="M0 6h30m0 0l-5-4.5M30 6l-5 4.5"
                stroke="currentColor"
                strokeWidth="1.4"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>

            <div className="flex flex-col items-start leading-none">
              <span
                className="tnum text-3xl font-bold xl:text-[2.6rem]"
                style={{ color: "var(--color-cue-1)" }}
              >
                {stats.wave_count}
              </span>
              <span className="mt-1 text-[10px] uppercase tracking-[0.18em] text-mist/70">
                waves
              </span>
            </div>

            {pct !== null && (
              <div
                className="ml-1 hidden rounded-lg border px-3 py-1.5 sm:block"
                style={{
                  borderColor: "color-mix(in oklab, var(--color-cue-1) 34%, transparent)",
                  background: "color-mix(in oklab, var(--color-cue-1) 12%, transparent)",
                }}
              >
                <span className="tnum block text-base font-bold leading-none text-chalk">
                  {pct}%
                </span>
                <span className="mt-1 block text-[9px] uppercase tracking-[0.14em] text-mist/70">
                  compressed
                </span>
              </div>
            )}
          </div>
        </div>

        {/* Health */}
        <div className="flex shrink-0 items-center gap-5">
          <div className="hidden items-center gap-5 xl:flex">
            <MicroStat value={String(stats.unique_sessions)} label="listeners" />
            <MicroStat
              value={`${Math.round(stats.avg_interpret_ms)}ms`}
              label="interpret"
            />
            <MicroStat
              value={stats.llm_enabled ? "LLM" : "RULES"}
              label="engine"
            />
          </div>
          <StatusPill status={status} />
        </div>
      </div>
    </header>
  );
}
