"use client";

import type { SongRequest } from "@/lib/types";
import { genreLabel } from "../guest/genres";

/**
 * One queued request. `request_count` is the whole ranking signal now — no
 * waves, no bridge scores, just how many phones asked for this exact song.
 * "Mark as played" and "Dismiss" are both soft deletes: the row disappears
 * from this list, but the backend keeps it (status flips, nothing is
 * deleted) so the full lifecycle survives for post-event analysis.
 */
export function RequestRow({
  request,
  rank,
  onPlayed,
  onDismiss,
}: {
  request: SongRequest;
  rank: number;
  onPlayed: () => void;
  onDismiss: () => void;
}) {
  const hot = request.request_count >= 3;

  return (
    <li
      data-flip-key={request.id}
      className="card flex items-center gap-2.5 px-3 py-3.5 sm:gap-4 sm:px-5"
    >
      <div className="relative h-11 w-11 shrink-0 sm:h-12 sm:w-12">
        {request.artwork_url ? (
          // eslint-disable-next-line @next/next/no-img-element -- arbitrary remote CDN host (iTunes/Deezer), not worth next/image config
          <img
            src={request.artwork_url}
            alt=""
            width={48}
            height={48}
            className="h-full w-full rounded-xl object-cover"
          />
        ) : (
          <span
            aria-hidden="true"
            className="flex h-full w-full items-center justify-center rounded-xl bg-ink-line text-mist"
          >
            <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
              <path d="M9 18V5l12-2v13" />
              <circle cx="6" cy="18" r="3" />
              <circle cx="18" cy="16" r="3" />
            </svg>
          </span>
        )}
        <span
          className="tnum absolute -bottom-1.5 -left-1.5 flex h-5 w-5 items-center justify-center rounded-full text-[10px] font-bold ring-2 ring-ink-card"
          style={{
            background:
              rank === 0
                ? "color-mix(in oklab, var(--color-cue-1) 85%, var(--color-ink-card))"
                : "var(--color-ink-line)",
            color: rank === 0 ? "white" : "var(--color-mist)",
          }}
          aria-hidden="true"
        >
          {rank + 1}
        </span>
      </div>

      <div className="min-w-0 flex-1">
        <p className="truncate text-[16px] font-semibold text-chalk">{request.song_title}</p>
        <p className="mt-0.5 flex min-w-0 items-center gap-2 truncate text-[13px] text-mist">
          {request.song_artist ? <span className="truncate">{request.song_artist}</span> : null}
          {request.genre ? (
            <span className="shrink-0 rounded-full border border-ink-line px-2 py-0.5 text-[11px] uppercase tracking-[0.08em] text-mist/80">
              {genreLabel(request.genre)}
            </span>
          ) : null}
        </p>
      </div>

      <div
        className="tnum flex shrink-0 items-center gap-1.5 rounded-full px-2.5 py-1.5 text-[14px] font-bold sm:px-3 sm:text-[15px]"
        style={{
          background: hot
            ? "color-mix(in oklab, var(--color-cue-1) 16%, transparent)"
            : "var(--color-ink-line)",
          color: hot ? "var(--color-cue-1)" : "var(--color-chalk)",
        }}
        title={`${request.request_count} request${request.request_count === 1 ? "" : "s"}`}
      >
        {request.request_count}×
      </div>

      <div className="flex shrink-0 items-center gap-1.5 sm:gap-2">
        <button
          type="button"
          onClick={onPlayed}
          aria-label="Mark as played"
          className="tap flex h-11 items-center gap-1.5 rounded-xl bg-go/15 px-2.5 text-[13px] font-bold text-go transition-colors active:bg-go/25 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-go/70 sm:px-3.5"
        >
          <svg viewBox="0 0 12 12" className="h-3 w-3 shrink-0" aria-hidden="true">
            <path d="M3 1.8v8.4L10 6z" fill="currentColor" />
          </svg>
          <span className="hidden sm:inline">Mark as played</span>
        </button>
        <button
          type="button"
          onClick={onDismiss}
          aria-label="Dismiss request"
          className="tap group flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-ink-line text-mist transition-all duration-150 hover:scale-105 hover:border-danger hover:bg-danger/10 hover:text-danger active:scale-95 active:bg-danger/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-danger/70"
        >
          <svg viewBox="0 0 12 12" className="h-3.5 w-3.5 transition-transform duration-150 group-hover:rotate-90" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" aria-hidden="true">
            <path d="M2.6 2.6l6.8 6.8M9.4 2.6L2.6 9.4" />
          </svg>
        </button>
      </div>
    </li>
  );
}
