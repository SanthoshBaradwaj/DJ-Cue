"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import type { SongRequest } from "@/lib/types";
import { genreColor, genreLabel } from "../guest/genres";

function formatDuration(totalSeconds: number): string {
  const m = Math.floor(totalSeconds / 60);
  const s = totalSeconds % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

/** Which source a catalog_url points at, purely for the link's own label --
 * the DJ shouldn't have to guess what tapping it opens. */
function catalogSourceLabel(url: string): string {
  if (url.includes("apple.com")) return "Apple Music";
  if (url.includes("deezer.com")) return "Deezer";
  return "Listen";
}

/**
 * Click-to-expand metadata for one queued request -- Title, Artist, Album,
 * BPM, Release Date, Duration, Vote Count, and a direct link to the track
 * on its source catalog, all in one place instead of the compact grid
 * card's truncated title/artist/count. Duration and the catalog link are
 * near-universally available (straight off the search result, not
 * dependent on Deezer's own tempo analysis like BPM is) -- so even when
 * BPM/release date come up empty, there's still a fast, concrete way to
 * identify the exact recording. Play and Dismiss are repeated here so a DJ
 * who opened this to double-check a song can act without closing it first.
 *
 * Opening this also re-attempts catalog resolution for any of those four
 * fields still missing -- a request can predate whichever deploy first
 * captured a field, or its one submit-time lookup can simply have missed
 * (fail-soft on purpose, so a flaky external call never blocks a guest's
 * request). Refetching only at view time, only for gaps, means this never
 * spends an API call on a request nobody ever looks at twice.
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
  const [live, setLive] = useState(request);
  const [refreshing, setRefreshing] = useState(false);

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

  useEffect(() => {
    setLive(request);
    const missing =
      request.bpm == null ||
      request.release_date == null ||
      request.catalog_url == null ||
      request.duration_seconds == null;
    if (!missing) return;
    let alive = true;
    setRefreshing(true);
    api
      .refreshRequestMetadata(request.id, request.event_id)
      .then((updated) => {
        if (alive) setLive(updated);
      })
      .catch(() => undefined)
      .finally(() => {
        if (alive) setRefreshing(false);
      });
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- only re-run when a *different* request opens, not on every `live`/`refreshing` update this effect itself causes
  }, [request.id]);

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
          <Field label="Album" value={live.album} />
          <Field
            label="Duration"
            value={live.duration_seconds ? formatDuration(live.duration_seconds) : null}
            pending={refreshing && live.duration_seconds == null}
          />
          <Field
            label="BPM"
            value={live.bpm ? String(live.bpm) : null}
            pending={refreshing && live.bpm == null}
          />
          <Field
            label="Release date"
            value={live.release_date}
            pending={refreshing && live.release_date == null}
          />
          <Field
            label="Vote count"
            value={`${live.request_count} request${live.request_count === 1 ? "" : "s"}`}
          />
          <LinkField
            label="Listen"
            href={live.catalog_url}
            pending={refreshing && live.catalog_url == null}
          />
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

function Field({
  label,
  value,
  pending,
}: {
  label: string;
  value: string | null;
  pending?: boolean;
}) {
  // A bare dash next to real data reads as broken, not "we don't have
  // this" -- a source (usually Deezer, for a track too new or too niche to
  // be in its catalog) genuinely not having a field is expected often
  // enough that it needs to look deliberate, not like a rendering bug.
  const known = value != null && value !== "";
  return (
    <div>
      <dt className="text-[11px] font-medium uppercase tracking-[0.1em] text-mist/60">{label}</dt>
      <dd
        className={
          known
            ? "mt-0.5 truncate text-[15px] font-medium text-chalk"
            : "mt-0.5 truncate text-[15px] font-medium text-mist/50 italic"
        }
      >
        {known ? value : pending ? "Checking…" : "Not available"}
      </dd>
    </div>
  );
}

function LinkField({
  label,
  href,
  pending,
}: {
  label: string;
  href: string | null;
  pending?: boolean;
}) {
  return (
    <div>
      <dt className="text-[11px] font-medium uppercase tracking-[0.1em] text-mist/60">{label}</dt>
      {href ? (
        <a
          href={href}
          target="_blank"
          rel="noopener noreferrer"
          onClick={(e) => e.stopPropagation()}
          className="tap mt-0.5 inline-flex items-center gap-1 truncate text-[15px] font-medium text-cue-1 underline decoration-cue-1/40 underline-offset-2 transition-colors active:text-cue-2"
        >
          {catalogSourceLabel(href)}
          <svg viewBox="0 0 12 12" className="h-3 w-3 shrink-0" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M4 2h6v6M10 2 4.5 7.5" />
          </svg>
        </a>
      ) : (
        <dd className="mt-0.5 truncate text-[15px] font-medium text-mist/50 italic">
          {pending ? "Checking…" : "Not available"}
        </dd>
      )}
    </div>
  );
}
