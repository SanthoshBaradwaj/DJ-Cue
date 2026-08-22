"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import type { Song, SongRequest } from "@/lib/types";
import { haptic } from "./motion";
import { trendingFor } from "./trending";

const DEBOUNCE_MS = 180;

// How often to refresh the "already requested" list while this screen is
// open -- matches the DJ status poll cadence elsewhere in the guest app.
// It's a plain poll, not the dashboard's websocket feed: this screen is
// open for seconds, not the whole set, so a socket connection isn't worth
// it for a "live-ish" list.
const PUBLIC_QUEUE_POLL_MS = 4000;
const PUBLIC_QUEUE_LIMIT = 6;

function requestToSong(r: SongRequest): Song {
  return {
    id: r.id,
    title: r.song_title,
    artist: r.song_artist,
    genre: r.genre,
    artwork_url: r.artwork_url,
    album: r.album,
    release_date: r.release_date,
    popularity: r.popularity,
  };
}

/**
 * Screen 2 of the guest flow: type, see matches, tap one to send it.
 *
 * Tapping a suggestion *is* the submit — the fastest path from thumb to
 * queued request. A guest whose song isn't in the catalog can still send the
 * raw text they typed via the fallback button underneath.
 */
export default function SongSearch({
  genreKey,
  displayLabel,
  biasSearch,
  eventId,
  pending,
  error,
  actionLimited,
  showPublicQueue,
  onBack,
  onSubmit,
}: {
  genreKey: string;
  /** What the header/empty-state copy shows -- the DJ's bucket label
   * ("South Indian") when the opening screen is bucket-driven, otherwise the
   * same as the single genre's own label. Never a narrower key underneath. */
  displayLabel: string;
  /** Whether catalog search should be nudged toward `genreKey`. False for a
   * bucket spanning more than one language -- there's no single language to
   * bias toward, so search runs on the typed text alone. */
  biasSearch: boolean;
  eventId?: string | null;
  pending: boolean;
  error: string | null;
  /** This session has spent its configured request/upvote budget -- disable
   * further taps rather than let every one round-trip to a guaranteed
   * rejection. Always false for an event with no cap configured. */
  actionLimited?: boolean;
  /** Config-gated (settings.show_public_queue): render an "already
   * requested" list above trending so a guest can upvote instead of
   * re-typing a song someone already asked for. */
  showPublicQueue?: boolean;
  onBack: () => void;
  onSubmit: (song: {
    title: string;
    artist?: string;
    songId?: string | null;
    artworkUrl?: string | null;
    album?: string | null;
    popularity?: number | null;
  }) => void;
}) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<Song[]>([]);
  const [searching, setSearching] = useState(false);
  const [publicQueue, setPublicQueue] = useState<SongRequest[]>([]);
  const genreQueue = showPublicQueue
    ? publicQueue.filter((r) => r.genre === genreKey).slice(0, PUBLIC_QUEUE_LIMIT)
    : [];
  // A curated trending pick and a real live request can be the same song --
  // don't show it twice. The live one wins since it reflects what this
  // crowd actually asked for, not a generic suggestion.
  const trending = trendingFor(genreKey).filter(
    (t) =>
      !genreQueue.some(
        (r) =>
          r.song_title.toLowerCase() === t.title.toLowerCase() &&
          (r.song_artist || "").toLowerCase() === (t.artist || "").toLowerCase(),
      ),
  );
  const inputRef = useRef<HTMLInputElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const blocked = pending || Boolean(actionLimited);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  useEffect(() => {
    if (!showPublicQueue || !eventId) {
      setPublicQueue([]);
      return;
    }
    let alive = true;
    const refresh = () => {
      api
        .dashboard(eventId)
        .then((state) => {
          if (alive) setPublicQueue(state.requests);
        })
        .catch(() => undefined);
    };
    refresh();
    const timer = setInterval(refresh, PUBLIC_QUEUE_POLL_MS);
    return () => {
      alive = false;
      clearInterval(timer);
    };
  }, [showPublicQueue, eventId]);

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    const q = query.trim();
    if (!q) {
      setResults([]);
      setSearching(false);
      return;
    }
    setSearching(true);
    debounceRef.current = setTimeout(async () => {
      try {
        const res = await api.searchSongs(q, biasSearch ? genreKey : undefined, 8);
        setResults(res.songs);
      } catch {
        setResults([]);
      } finally {
        setSearching(false);
      }
    }, DEBOUNCE_MS);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [query, genreKey, biasSearch]);

  const pickSong = (song: Song) => {
    if (blocked) return;
    haptic(12);
    onSubmit({
      title: song.title,
      artist: song.artist,
      songId: song.id,
      artworkUrl: song.artwork_url,
      album: song.album,
      popularity: song.popularity,
    });
  };

  const requestTyped = () => {
    const value = query.trim();
    if (!value || blocked) return;
    haptic(12);
    onSubmit({ title: value, songId: null });
  };

  return (
    <div className="flex flex-col animate-rise">
      <header className="flex items-center gap-3">
        <button
          type="button"
          onClick={onBack}
          aria-label="Back to genres"
          className="tap flex h-11 w-11 shrink-0 items-center justify-center rounded-full border border-ink-line bg-ink-card/80 text-chalk transition-colors active:bg-ink-line/70 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cue-1/70"
        >
          <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M15 18l-6-6 6-6" />
          </svg>
        </button>
        <div className="min-w-0">
          <p className="truncate text-[13px] tracking-[0.1em] text-mist/80 uppercase">
            {displayLabel}
          </p>
          <h1 className="truncate text-[21px] font-semibold tracking-[-0.02em] text-chalk">
            What song?
          </h1>
        </div>
      </header>

      <div className="relative mt-5 card p-4 transition-shadow duration-200 focus-within:ring-2 focus-within:ring-cue-1/60">
        <input
          ref={inputRef}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.nativeEvent.isComposing) {
              e.preventDefault();
              if (results.length > 0) pickSong(results[0]);
              else requestTyped();
            }
          }}
          placeholder="Type a song or artist…"
          autoComplete="off"
          autoCapitalize="none"
          autoCorrect="on"
          spellCheck={false}
          enterKeyHint="search"
          maxLength={120}
          disabled={blocked}
          className="block w-full bg-transparent text-[20px] font-medium tracking-[-0.01em] text-chalk caret-cue-1 outline-none placeholder:text-mist/60 disabled:opacity-70"
        />
      </div>

      {actionLimited ? (
        <p role="alert" className="mt-3 rounded-xl bg-cue-1 px-4 py-3 text-[14px] font-semibold text-ink animate-rise">
          {error || "You've used up your requests for tonight -- thanks for playing along!"}
        </p>
      ) : error ? (
        <p role="alert" className="mt-3 rounded-xl border border-hold/40 bg-hold/10 px-4 py-3 text-[14px] text-chalk/90 animate-rise">
          {error}
        </p>
      ) : null}

      <div className="mt-4 flex min-h-[3rem] flex-col gap-5">
        {query.trim() ? (
          results.length > 0 ? (
            <SongList songs={results} pending={blocked} onPick={pickSong} />
          ) : !searching ? (
            <div className="animate-rise">
              <p className="px-1 text-[14px] text-mist">No match in the catalog yet.</p>
              <button
                type="button"
                disabled={blocked}
                onClick={requestTyped}
                className="tap mt-3 flex h-14 w-full items-center justify-center gap-2 rounded-2xl bg-gradient-to-r from-cue-1 to-cue-2 text-[17px] font-semibold text-white shadow-[0_10px_40px_-12px_rgba(255,45,120,0.75)] transition-all duration-150 active:scale-[0.985] disabled:cursor-not-allowed disabled:bg-none disabled:bg-ink-card disabled:text-mist disabled:shadow-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-chalk/80 focus-visible:ring-offset-2 focus-visible:ring-offset-ink"
              >
                {pending ? (
                  <>
                    <span aria-hidden="true" className="h-4 w-4 shrink-0 animate-spin rounded-full border-2 border-white/35 border-t-white" />
                    Sending
                  </>
                ) : (
                  <>Request &ldquo;{query.trim()}&rdquo; anyway</>
                )}
              </button>
            </div>
          ) : null
        ) : (
          <>
            {genreQueue.length > 0 && (
              <div className="animate-rise">
                <p className="px-1 text-[12px] font-medium uppercase tracking-[0.14em] text-mist/60">
                  Already requested — tap to upvote
                </p>
                <div className="mt-2">
                  <SongList songs={genreQueue.map(requestToSong)} pending={blocked} onPick={pickSong} />
                </div>
              </div>
            )}
            {trending.length > 0 ? (
              <div className="animate-rise">
                <p className="px-1 text-[12px] font-medium uppercase tracking-[0.14em] text-mist/60">
                  Popular right now
                </p>
                <div className="mt-2">
                  <SongList songs={trending} pending={blocked} onPick={pickSong} />
                </div>
              </div>
            ) : genreQueue.length === 0 ? (
              <p className="px-1 text-[14px] text-mist/70">
                Start typing — matches from the {displayLabel} catalog show up here.
              </p>
            ) : null}
          </>
        )}
      </div>
    </div>
  );
}

function SongList({
  songs,
  pending,
  onPick,
}: {
  songs: Song[];
  pending: boolean;
  onPick: (song: Song) => void;
}) {
  return (
    <ul className="flex flex-col gap-2 animate-rise">
      {songs.map((song) => (
        <li key={song.id}>
          <button
            type="button"
            disabled={pending}
            onClick={() => onPick(song)}
            className="tap flex w-full items-center gap-3 rounded-2xl border border-ink-line bg-ink-card/80 px-3 py-3 text-left transition-all duration-150 active:scale-[0.985] active:border-cue-1/60 active:bg-cue-1/10 disabled:opacity-60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cue-1/70"
          >
            {song.artwork_url ? (
              // eslint-disable-next-line @next/next/no-img-element -- arbitrary remote CDN host, not worth next/image config
              <img
                src={song.artwork_url}
                alt=""
                width={48}
                height={48}
                className="h-12 w-12 shrink-0 rounded-lg object-cover"
              />
            ) : (
              <span
                aria-hidden="true"
                className="flex h-12 w-12 shrink-0 items-center justify-center rounded-lg bg-ink-line text-mist"
              >
                <svg viewBox="0 0 24 24" className="h-5 w-5" fill="currentColor">
                  <path d="M9 18V5l12-2v13" stroke="currentColor" strokeWidth="1.6" fill="none" strokeLinecap="round" strokeLinejoin="round" />
                  <circle cx="6" cy="18" r="3" stroke="currentColor" strokeWidth="1.6" fill="none" />
                  <circle cx="18" cy="16" r="3" stroke="currentColor" strokeWidth="1.6" fill="none" />
                </svg>
              </span>
            )}
            <span className="min-w-0 flex-1">
              <span className="block truncate text-[16px] font-semibold text-chalk">
                {song.title}
              </span>
              {song.artist ? (
                <span className="block truncate text-[13px] text-mist">{song.artist}</span>
              ) : null}
            </span>
            <span className="shrink-0 text-cue-1" aria-hidden="true">
              <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="2.3" strokeLinecap="round" strokeLinejoin="round">
                <path d="M9 18l6-6-6-6" />
              </svg>
            </span>
          </button>
        </li>
      ))}
    </ul>
  );
}
