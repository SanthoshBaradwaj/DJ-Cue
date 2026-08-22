"use client";

import { useEffect, useRef } from "react";
import type { SongRequest } from "@/lib/types";
import { genreColor, genreLabel } from "../guest/genres";

/**
 * Click-to-expand metadata for one queued request -- Title, Artist, Album,
 * BPM, Vote Count, all in one place instead of the compact grid card's
 * truncated title/artist/count. Play and Dismiss are repeated here so a DJ
 * who opened this to double-check a song can act without closing it first.
 */
export function BucketDetailModal({
  request,
  onClose,
  onPlayed,
  onDismiss,
}: {
  request: SongRequest;
  onClose: () => void;
  onPlayed: () => void;
  onDismiss: () => void;
}) {
  const headingRef = useRef<HTMLHeadingElement>(null);
  const accent = genreColor(request.genre);

  useEffect(() => {
    headingRef.current?.focus();
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="bucket-detail-heading"
      onClick={onClose}
      className="fixed inset-0 z-50 flex items-end justify-center bg-ink/80 backdrop-blur-sm animate-rise sm:items-center sm:p-4"
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-[440px] rounded-t-3xl border border-ink-line bg-ink-card px-6 pt-6 shadow-2xl sm:rounded-3xl"
        style={{ paddingBottom: "calc(env(safe-area-inset-bottom) + 1.5rem)" }}
      >
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            {request.genre && (
              <span
                className="mb-1.5 inline-block rounded-full px-2.5 py-0.5 text-[11px] font-semibold uppercase tracking-[0.08em]"
                style={{
                  background: `color-mix(in oklab, ${accent} 18%, transparent)`,
                  color: accent,
                }}
              >
                {genreLabel(request.genre)}
              </span>
            )}
            <h2
              id="bucket-detail-heading"
              ref={headingRef}
              tabIndex={-1}
              className="text-[22px] leading-[1.25] font-semibold tracking-[-0.02em] text-chalk outline-none"
            >
              {request.song_title}
            </h2>
            {request.song_artist ? (
              <p className="mt-0.5 text-[15px] text-mist">{request.song_artist}</p>
            ) : null}
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="tap flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-ink-line text-mist transition-colors active:bg-ink-line/70 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cue-1/70"
          >
            <svg viewBox="0 0 12 12" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" aria-hidden="true">
              <path d="M2.6 2.6l6.8 6.8M9.4 2.6L2.6 9.4" />
            </svg>
          </button>
        </div>

        <dl className="mt-5 grid grid-cols-2 gap-3">
          <Field label="Album" value={request.album ?? "—"} />
          <Field label="BPM" value={request.bpm ? String(request.bpm) : "—"} />
          <Field
            label="Vote count"
            value={`${request.request_count} request${request.request_count === 1 ? "" : "s"}`}
          />
          <Field label="Release date" value={request.release_date ?? "—"} />
        </dl>

        <div className="mt-6 flex gap-2.5">
          <button
            type="button"
            onClick={onPlayed}
            className="tap flex h-14 flex-1 items-center justify-center gap-2 rounded-2xl bg-go/15 text-[15px] font-bold text-go transition-all duration-150 active:scale-[0.985] active:bg-go/25 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-go/70"
          >
            <svg viewBox="0 0 12 12" className="h-3.5 w-3.5 shrink-0" aria-hidden="true">
              <path d="M3 1.8v8.4L10 6z" fill="currentColor" />
            </svg>
            Mark as played
          </button>
          <button
            type="button"
            onClick={onDismiss}
            aria-label="Dismiss request"
            className="tap flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl border border-ink-line text-mist transition-all duration-150 active:scale-[0.985] active:border-danger active:bg-danger/10 active:text-danger focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-danger/70"
          >
            <svg viewBox="0 0 12 12" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" aria-hidden="true">
              <path d="M2.6 2.6l6.8 6.8M9.4 2.6L2.6 9.4" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-[11px] font-medium uppercase tracking-[0.1em] text-mist/60">{label}</dt>
      <dd className="mt-0.5 truncate text-[15px] font-medium text-chalk">{value}</dd>
    </div>
  );
}
