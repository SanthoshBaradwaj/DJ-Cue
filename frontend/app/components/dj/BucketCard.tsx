"use client";

import type { SongRequest } from "@/lib/types";
import { genreColor } from "../guest/genres";

/**
 * One slot in a genre-quota column. `request` is null for an explicitly
 * empty slot (that genre's backlog ran dry) -- rendered as a dashed
 * placeholder rather than collapsed away, so the DJ can see at a glance that
 * a bucket is short, not just miscounted.
 */
export function BucketCard({
  request,
  onExpand,
  onPlayed,
  onDismiss,
}: {
  request: SongRequest | null;
  onExpand: () => void;
  onPlayed: () => void;
  onDismiss: () => void;
}) {
  if (!request) {
    return (
      <div className="flex h-[4.25rem] items-center justify-center rounded-xl border border-dashed border-ink-line/70 px-3 text-[14px] text-mist/50">
        Empty slot
      </div>
    );
  }

  const hot = request.request_count >= 3;
  const accent = genreColor(request.genre);

  const stop = (fn: () => void) => (e: React.MouseEvent) => {
    e.stopPropagation();
    fn();
  };

  return (
    <button
      type="button"
      onClick={onExpand}
      data-flip-key={request.id}
      className="tap group flex h-[4.25rem] w-full items-center gap-2 rounded-xl border border-ink-line bg-ink-card/80 px-2.5 text-left transition-all duration-150 hover:border-cue-1/50 hover:bg-ink-card active:scale-[0.98] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cue-1/70"
    >
      <span
        aria-hidden="true"
        className="h-full w-1 shrink-0 rounded-full"
        style={{ background: accent }}
      />

      <span className="min-w-0 flex-1">
        <span className="block truncate text-[16px] font-semibold text-chalk">
          {request.song_title}
        </span>
        {request.song_artist ? (
          <span className="block truncate text-[14px] text-mist">{request.song_artist}</span>
        ) : null}
      </span>

      <span
        className="tnum shrink-0 rounded-full px-2 py-1 text-[14px] font-bold"
        style={{
          background: hot
            ? "color-mix(in oklab, var(--color-cue-1) 16%, transparent)"
            : "var(--color-ink-line)",
          color: hot ? "var(--color-cue-1)" : "var(--color-chalk)",
        }}
        title={`${request.request_count} request${request.request_count === 1 ? "" : "s"}`}
      >
        {request.request_count}
      </span>

      <span className="flex shrink-0 items-center gap-1">
        <span
          role="button"
          tabIndex={0}
          onClick={stop(onPlayed)}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault();
              stop(onPlayed)(e as unknown as React.MouseEvent);
            }
          }}
          aria-label="Mark as played"
          className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-go transition-all duration-150 hover:scale-110 hover:bg-go/20 active:scale-95 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-go/70"
        >
          <svg viewBox="0 0 12 12" className="h-3 w-3 shrink-0" aria-hidden="true">
            <path d="M3 1.8v8.4L10 6z" fill="currentColor" />
          </svg>
        </span>
        <span
          role="button"
          tabIndex={0}
          onClick={stop(onDismiss)}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault();
              stop(onDismiss)(e as unknown as React.MouseEvent);
            }
          }}
          aria-label="Dismiss request"
          className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-mist transition-all duration-150 hover:scale-110 hover:bg-danger/15 hover:text-danger active:scale-95 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-danger/70"
        >
          <svg viewBox="0 0 12 12" className="h-3 w-3" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" aria-hidden="true">
            <path d="M2.6 2.6l6.8 6.8M9.4 2.6L2.6 9.4" />
          </svg>
        </span>
      </span>
    </button>
  );
}
