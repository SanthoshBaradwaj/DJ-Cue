"use client";

import { useEffect, useState } from "react";
import type { DJState } from "@/lib/types";
import { EnergyBar, SectionLabel } from "./Primitives";
import { clamp01, fmtDuration, tint, toMillis } from "./theme";
import type { TickerItem } from "./useDashboardFeed";

function NowPlaying({ dj }: { dj: DJState }) {
  const [now, setNow] = useState(() => Date.now());
  const track = dj.current_track;

  useEffect(() => {
    if (!track) return;
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, [track]);

  if (!track) {
    return (
      <div className="card p-4">
        <SectionLabel>Now Playing</SectionLabel>
        <p className="mt-3 text-sm text-mist/70">
          Nothing cued yet. Tap <span className="font-semibold text-go">Play</span> on
          a recommendation to start the set.
        </p>
      </div>
    );
  }

  const startedAt = toMillis(dj.started_at);
  const elapsed = startedAt ? Math.max(0, (now - startedAt) / 1000) : 0;
  const pct = track.duration_sec > 0 ? clamp01(elapsed / track.duration_sec) : 0;
  const remaining = Math.max(0, track.duration_sec - elapsed);

  return (
    <div
      className="card relative overflow-hidden p-4"
      style={{ borderColor: tint("var(--color-go)", 26) }}
    >
      <div className="flex items-center justify-between">
        <SectionLabel>Now Playing</SectionLabel>
        <span className="flex items-center gap-1.5">
          <span className="relative flex h-1.5 w-1.5">
            <span className="absolute inset-0 rounded-full bg-go animate-pulse-ring" />
            <span className="relative h-1.5 w-1.5 rounded-full bg-go" />
          </span>
          <span className="tnum text-[11px] font-semibold text-go">
            -{fmtDuration(remaining)}
          </span>
        </span>
      </div>

      <h3 className="mt-3 truncate text-[17px] font-semibold leading-snug text-chalk">
        {track.title}
      </h3>
      <p className="truncate text-[13px] text-mist">{track.artist}</p>

      <div className="mt-3 flex items-center gap-3 text-[12px]">
        <span className="tnum font-semibold text-chalk/85">
          {track.bpm}
          <span className="ml-1 text-[10px] uppercase tracking-[0.12em] text-mist/70">
            bpm
          </span>
        </span>
        <span className="h-3 w-px bg-ink-line" aria-hidden="true" />
        <EnergyBar energy={track.energy} accent="var(--color-go)" />
        <span className="tnum text-[11px] text-mist/70">
          {Math.round(clamp01(track.energy) * 100)}
        </span>
      </div>

      <div className="mt-3.5 h-1 w-full overflow-hidden rounded-full bg-white/[0.07]">
        <div
          className="h-full rounded-full bg-go/80 transition-[width] duration-1000 ease-linear"
          style={{ width: `${pct * 100}%` }}
        />
      </div>
      <div className="mt-1.5 flex justify-between text-[10px] text-mist/50">
        <span className="tnum">{fmtDuration(elapsed)}</span>
        <span className="tnum">{fmtDuration(track.duration_sec)}</span>
      </div>
    </div>
  );
}

function LaterQueue({ dj }: { dj: DJState }) {
  return (
    <div className="card p-4">
      <div className="flex items-center justify-between">
        <SectionLabel>Later Queue</SectionLabel>
        <span className="tnum text-[11px] text-mist/55">{dj.queue.length}</span>
      </div>
      {dj.queue.length === 0 ? (
        <p className="mt-3 text-[13px] text-mist/60">
          Nothing held back yet.
        </p>
      ) : (
        <ol className="mt-3 space-y-2.5">
          {dj.queue.slice(0, 5).map((t, i) => (
            <li key={`${t.id}-${i}`} className="flex items-center gap-3">
              <span
                className="tnum w-4 shrink-0 text-[11px] font-bold"
                style={{ color: tint("var(--color-hold)", 80) }}
              >
                {i + 1}
              </span>
              <span className="min-w-0 flex-1">
                <span className="block truncate text-[13px] font-medium text-chalk/90">
                  {t.title}
                </span>
                <span className="block truncate text-[11px] text-mist/70">
                  {t.artist}
                </span>
              </span>
              <span className="tnum shrink-0 text-[11px] text-mist/60">{t.bpm}</span>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}

/**
 * Chaos on the right, order on the left. Raw guest phrasing streams in here
 * exactly as typed, tagged with the wave the interpreter dropped it into.
 */
function Ticker({
  items,
  accentFor,
}: {
  items: TickerItem[];
  accentFor: (waveId: string | null) => string;
}) {
  return (
    <div className="card flex min-h-0 flex-1 flex-col p-4">
      <div className="flex shrink-0 items-center justify-between">
        <SectionLabel>Incoming Requests</SectionLabel>
        <span className="flex items-center gap-1.5">
          <span className="relative flex h-1.5 w-1.5">
            <span className="absolute inset-0 rounded-full bg-cue-1 animate-pulse-ring" />
            <span className="relative h-1.5 w-1.5 rounded-full bg-cue-1" />
          </span>
          <span className="text-[10px] font-semibold uppercase tracking-[0.14em] text-mist/60">
            raw feed
          </span>
        </span>
      </div>

      {items.length === 0 ? (
        <p className="mt-3 text-[13px] leading-relaxed text-mist/55">
          Guest requests appear here the instant they are sent — unedited, in
          their own words.
        </p>
      ) : (
        <ul
          className="mt-3 min-h-0 flex-1 space-y-2 overflow-y-auto pr-1"
          style={{
            maskImage:
              "linear-gradient(to bottom, black calc(100% - 34px), transparent)",
            WebkitMaskImage:
              "linear-gradient(to bottom, black calc(100% - 34px), transparent)",
          }}
          aria-live="polite"
          aria-label="Live incoming guest requests"
        >
          {items.map((item, i) => {
            const accent = accentFor(item.waveId);
            return (
              <li
                key={item.key}
                className="animate-slide-in rounded-lg border border-ink-line/70 bg-white/[0.02] px-3 py-2"
                style={{ opacity: Math.max(0.32, 1 - i * 0.06) }}
              >
                <p className="text-[13px] italic leading-snug text-chalk/85">
                  &ldquo;{item.text}&rdquo;
                </p>
                <p className="mt-1.5 flex items-center gap-1.5">
                  <span
                    className="h-1.5 w-1.5 shrink-0 rounded-full"
                    style={{ background: accent }}
                    aria-hidden="true"
                  />
                  <span
                    className="truncate text-[10px] font-semibold uppercase tracking-[0.12em]"
                    style={{ color: tint(accent, 85) }}
                  >
                    {item.waveLabel}
                  </span>
                </p>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

export function RightRail({
  dj,
  ticker,
  accentFor,
}: {
  dj: DJState;
  ticker: TickerItem[];
  accentFor: (waveId: string | null) => string;
}) {
  return (
    <aside className="flex min-h-0 flex-col gap-3.5 overflow-hidden">
      <NowPlaying dj={dj} />
      <LaterQueue dj={dj} />
      <Ticker items={ticker} accentFor={accentFor} />
    </aside>
  );
}
