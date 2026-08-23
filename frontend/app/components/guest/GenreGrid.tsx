"use client";

import type { CSSProperties } from "react";
import type { DJStatus, EventSettings, PulseStatus } from "@/lib/types";
import { GENRES, type GenrePick, genreColor } from "./genres";
import { haptic } from "./motion";
import PulseChoice from "./PulseChoice";
import PulseToggle from "./PulseToggle";

const STATUS_COPY: Record<DJStatus, { label: string; dot: string }> = {
  open: { label: "Taking requests", dot: "bg-go" },
  closed: { label: "Not taking requests", dot: "bg-drop" },
};

interface Tile {
  key: string;
  label: string;
  accent: string;
  pick: GenrePick;
}

/**
 * Screen 1 of the guest flow: one tap, no typing.
 *
 * The tiles themselves are config-driven: when the DJ has genre_buckets
 * configured, the guest sees those exact same buckets as buttons -- one
 * genre picker, not two different taxonomies on two screens. Every event
 * without bucket config (today's default, and any future DJ who doesn't
 * want this) falls back to the static 9-genre grid unchanged. `GENRES` is
 * already ordered so north/south genres interleave rather than cluster in
 * that fallback -- there's no "north block, then south block" to read past.
 */
export default function GenreGrid({
  eventLine,
  djStatus,
  pulse,
  pulseLimited,
  pulsePending,
  instagramHandle,
  genreBuckets,
  onPick,
  onPulseChange,
}: {
  eventLine: string;
  djStatus?: DJStatus;
  pulse?: PulseStatus | null;
  pulseLimited?: boolean;
  pulsePending?: boolean;
  /** Config-gated -- only rendered when the DJ has set one. */
  instagramHandle?: string | null;
  /** Config-gated (settings.genre_buckets) -- when present, these render as
   * the opening tiles instead of the static 9-genre grid. */
  genreBuckets?: EventSettings["genre_buckets"];
  onPick: (pick: GenrePick) => void;
  onPulseChange?: (status: PulseStatus) => void;
}) {
  const pick = (tile: GenrePick) => {
    haptic(12);
    onPick(tile);
  };

  const tiles: Tile[] =
    genreBuckets && genreBuckets.length > 0
      ? genreBuckets.map((b) => {
          const representative = b.genres[0] ?? "other";
          return {
            key: b.label,
            label: b.label,
            accent: genreColor(representative),
            pick: { genre: representative, label: b.label, biasSearch: b.genres.length === 1 },
          };
        })
      : GENRES.map((g) => ({
          key: g.key,
          label: g.label,
          accent: genreColor(g.key),
          pick: { genre: g.key, label: g.label, biasSearch: true },
        }));

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

      {onPulseChange && (
        <PulseChoice
          value={pulse ?? null}
          limited={Boolean(pulseLimited)}
          pending={Boolean(pulsePending)}
          onChange={onPulseChange}
        />
      )}

      {instagramHandle && (
        <a
          href={`https://www.instagram.com/${instagramHandle}/`}
          target="_blank"
          rel="noopener noreferrer"
          // A translucent Instagram-brand gradient at low opacity blended
          // into the dark background instead of separating from it -- with
          // nothing here reading as a clear, distinct block, the pulse
          // buttons above and "Request your favourites" below lost their
          // own visual weight too, since everything read as one undifferentiated
          // stack of similar-contrast cards. Solid cue-1-on-ink (this app's
          // own accent, not Instagram's) gives this its own clear identity,
          // which is what actually restores separation to the sections
          // around it.
          className="tap mt-4 flex h-12 w-full shrink-0 items-center justify-center gap-2 rounded-2xl bg-cue-1 text-[14px] font-bold text-ink transition-all duration-150 active:scale-[0.985] active:brightness-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cue-1/70"
        >
          <svg viewBox="0 0 24 24" className="h-[18px] w-[18px] shrink-0" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
            <rect x="3" y="3" width="18" height="18" rx="5" />
            <circle cx="12" cy="12" r="4" />
            <circle cx="17.2" cy="6.8" r="1" fill="currentColor" stroke="none" />
          </svg>
          Follow the DJ on Instagram
        </a>
      )}

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
            {tiles.map((tile, i) => (
              <button
                key={tile.key}
                type="button"
                onClick={() => pick(tile.pick)}
                style={
                  {
                    animationDelay: `${60 + i * 45}ms`,
                    animationFillMode: "backwards",
                    "--accent": tile.accent,
                    borderColor: `color-mix(in oklab, ${tile.accent} 42%, var(--color-ink-line))`,
                    background: `color-mix(in oklab, ${tile.accent} 13%, var(--color-ink-card))`,
                  } as CSSProperties
                }
                className={`tap group/genre relative flex h-24 flex-col items-center justify-center gap-1 overflow-hidden rounded-2xl border px-3 text-center transition-all duration-200 ease-out hover:-translate-y-0.5 hover:shadow-[0_14px_32px_-16px_var(--accent)] hover:[border-color:color-mix(in_oklab,var(--accent)_65%,var(--color-ink-line))] hover:[background:color-mix(in_oklab,var(--accent)_20%,var(--color-ink-card))] active:translate-y-0 active:scale-[0.96] active:duration-100 active:[background:color-mix(in_oklab,var(--accent)_28%,var(--color-ink-card))] focus-visible:outline-none focus-visible:ring-2 focus-visible:[--tw-ring-color:var(--accent)] animate-rise ${
                  // An odd tile count in a 2-column grid leaves one item
                  // without a partner; give it the full row rather than a
                  // lopsided gap.
                  tiles.length % 2 === 1 && i === tiles.length - 1 ? "col-span-2" : ""
                }`}
              >
                <span
                  aria-hidden="true"
                  className="absolute top-0 left-0 h-[3px] w-full origin-left scale-x-0 transition-transform duration-200 ease-out group-hover/genre:scale-x-100"
                  style={{ background: tile.accent }}
                />
                <span className="text-[19px] font-semibold tracking-[-0.01em] text-chalk">
                  {tile.label}
                </span>
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
