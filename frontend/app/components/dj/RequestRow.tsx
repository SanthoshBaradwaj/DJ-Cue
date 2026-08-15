"use client";

import type { SongRequest } from "@/lib/types";
import { genreLabel } from "../guest/genres";

/**
 * One queued request. `request_count` is the whole ranking signal now — no
 * waves, no bridge scores, just how many phones asked for this exact song.
 * "Played" and "Dismiss" are both soft deletes: the row disappears from this
 * list, but the backend keeps it (status flips, nothing is deleted) so the
 * full lifecycle survives for post-event analysis.
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
      className="card flex items-center gap-4 px-4 py-3.5 sm:px-5"
    >
      <span
        className="tnum flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-[13px] font-bold"
        style={{
          background:
            rank === 0
              ? "color-mix(in oklab, var(--color-cue-1) 20%, transparent)"
              : "var(--color-ink-line)",
          color: rank === 0 ? "var(--color-cue-1)" : "var(--color-mist)",
        }}
        aria-hidden="true"
      >
        {rank + 1}
      </span>

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
        className="tnum flex shrink-0 items-center gap-1.5 rounded-full px-3 py-1.5 text-[15px] font-bold"
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

      <div className="flex shrink-0 items-center gap-2">
        <button
          type="button"
          onClick={onPlayed}
          className="tap flex h-11 items-center gap-1.5 rounded-xl bg-go/15 px-3.5 text-[13px] font-bold text-go transition-colors active:bg-go/25 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-go/70"
        >
          <svg viewBox="0 0 12 12" className="h-3 w-3 shrink-0" aria-hidden="true">
            <path d="M3 1.8v8.4L10 6z" fill="currentColor" />
          </svg>
          Played
        </button>
        <button
          type="button"
          onClick={onDismiss}
          aria-label="Dismiss request"
          className="tap flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-ink-line text-mist transition-colors active:bg-ink-line/70 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-drop/70"
        >
          <svg viewBox="0 0 12 12" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" aria-hidden="true">
            <path d="M2.6 2.6l6.8 6.8M9.4 2.6L2.6 9.4" />
          </svg>
        </button>
      </div>
    </li>
  );
}
