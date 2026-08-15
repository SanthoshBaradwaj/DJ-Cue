"use client";

import { GENRES } from "./genres";
import { haptic } from "./motion";

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
  onPick,
}: {
  eventLine: string;
  onPick: (genreKey: string) => void;
}) {
  const pick = (key: string) => {
    haptic(12);
    onPick(key);
  };

  return (
    <div className="flex flex-col animate-rise">
      <header className="flex items-baseline justify-between gap-3">
        <span className="bg-gradient-to-r from-cue-1 via-cue-2 to-cue-3 bg-clip-text text-[15px] font-bold tracking-[0.42em] text-transparent">
          DJ-CUE
        </span>
        <span className="flex items-center gap-2 text-[13px] text-mist">
          <span
            aria-hidden="true"
            className="relative flex h-1.5 w-1.5 shrink-0 rounded-full bg-go"
          >
            <span className="absolute -inset-1 rounded-full bg-go/40 animate-pulse-ring" />
          </span>
          <span className="truncate">{eventLine}</span>
        </span>
      </header>

      <h1 className="mt-7 text-[28px] leading-[1.15] font-semibold tracking-[-0.02em] text-chalk">
        What&apos;s your sound tonight?
      </h1>
      <p className="mt-2 text-[15px] text-mist">Pick a genre to request a song.</p>

      <div className="mt-7 grid grid-cols-2 gap-3">
        {GENRES.map((g, i) => (
          <button
            key={g.key}
            type="button"
            onClick={() => pick(g.key)}
            style={{ animationDelay: `${60 + i * 45}ms`, animationFillMode: "backwards" }}
            className={`tap flex h-24 flex-col items-center justify-center gap-1 rounded-2xl border border-ink-line bg-ink-card/80 px-3 text-center transition-all duration-150 active:scale-[0.96] active:border-cue-1/60 active:bg-cue-1/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cue-1/70 animate-rise ${
              // 5 genres in a 2-column grid leaves one odd item; give it the
              // full row rather than letting it sit lopsided next to a gap.
              GENRES.length % 2 === 1 && i === GENRES.length - 1 ? "col-span-2" : ""
            }`}
          >
            <span className="text-[19px] font-semibold tracking-[-0.01em] text-chalk">
              {g.label}
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}
