"use client";

import type { DJStatus, PulseStatus } from "@/lib/types";
import { GENRES } from "./genres";
import { haptic } from "./motion";
import PulseToggle from "./PulseToggle";

const STATUS_COPY: Record<DJStatus, { label: string; dot: string }> = {
  open: { label: "Taking requests", dot: "bg-go" },
  closed: { label: "Not taking requests", dot: "bg-drop" },
};

/**
 * Screen 1 of the guest flow: one tap, no typing.
 *
 * One flowing grid, not two labeled sections. `GENRES` is already ordered so
 * north/south genres interleave rather than cluster -- there's no "north
 * block, then south block" to read past, no side that visually leads, and
 * moving from a Punjabi tap to a Tamil one is just eye movement across the
 * same grid, not a jump between zones.
 */
export default function GenreGrid({
  eventLine,
  djStatus,
  pulse,
  pulseLimited,
  pulsePending,
  onPick,
  onPulseChange,
}: {
  eventLine: string;
  djStatus?: DJStatus;
  pulse?: PulseStatus | null;
  pulseLimited?: boolean;
  pulsePending?: boolean;
  onPick: (genreKey: string) => void;
  onPulseChange?: (status: PulseStatus) => void;
}) {
  const pick = (key: string) => {
    haptic(12);
    onPick(key);
  };

  const status = djStatus ? STATUS_COPY[djStatus] : null;
  const closed = djStatus === "closed";

  return (
    <div className="flex flex-col animate-rise">
      <header className="flex items-center justify-between gap-3">
        <span className="shrink-0 bg-gradient-to-r from-cue-1 via-cue-2 to-cue-3 bg-clip-text text-[15px] font-bold tracking-[0.42em] text-transparent">
          DJ-CUE
        </span>
        <div className="flex min-w-0 items-center gap-2.5">
          <span className="flex min-w-0 items-center gap-2 text-[13px] text-mist">
            <span
              aria-hidden="true"
              className={`relative flex h-1.5 w-1.5 shrink-0 rounded-full ${status?.dot ?? "bg-go"}`}
            >
              {(!status || status === STATUS_COPY.open) && (
                <span className="absolute -inset-1 rounded-full bg-go/40 animate-pulse-ring" />
              )}
            </span>
            <span className="truncate">{status ? status.label : eventLine}</span>
          </span>
          {onPulseChange && (
            <PulseToggle
              value={pulse ?? null}
              limited={Boolean(pulseLimited)}
              pending={Boolean(pulsePending)}
              onChange={onPulseChange}
            />
          )}
        </div>
      </header>

      {closed ? (
        <div className="mt-10 flex flex-col items-center gap-2 rounded-2xl border border-ink-line bg-ink-card/60 px-6 py-10 text-center">
          <span className="h-2 w-2 rounded-full bg-drop" aria-hidden="true" />
          <h1 className="mt-2 text-[22px] font-semibold tracking-[-0.02em] text-chalk">
            Not taking requests right now
          </h1>
          <p className="mt-1 max-w-xs text-[14px] leading-relaxed text-mist">
            The DJ has paused new requests for a bit. Check back shortly --
            the queue will reopen.
          </p>
        </div>
      ) : (
        <>
          <h1 className="mt-7 text-[28px] leading-[1.15] font-semibold tracking-[-0.02em] text-chalk">
            Request your favourites
          </h1>
          <p className="mt-2 text-[15px] text-mist">Pick a genre to get started.</p>

          <div className="mt-7 grid grid-cols-2 gap-3">
            {GENRES.map((g, i) => (
              <button
                key={g.key}
                type="button"
                onClick={() => pick(g.key)}
                style={{ animationDelay: `${60 + i * 45}ms`, animationFillMode: "backwards" }}
                className={`tap flex h-24 flex-col items-center justify-center gap-1 rounded-2xl border border-ink-line bg-ink-card/80 px-3 text-center transition-all duration-150 active:scale-[0.96] active:border-cue-1/60 active:bg-cue-1/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cue-1/70 animate-rise ${
                  // An odd genre count in a 2-column grid leaves one item
                  // without a partner; give it the full row rather than a
                  // lopsided gap.
                  GENRES.length % 2 === 1 && i === GENRES.length - 1 ? "col-span-2" : ""
                }`}
              >
                <span className="text-[19px] font-semibold tracking-[-0.01em] text-chalk">
                  {g.label}
                </span>
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
