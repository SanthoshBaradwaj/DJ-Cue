"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import type { Song } from "@/lib/types";
import { genreLabel } from "./genres";
import { haptic } from "./motion";
import { trendingFor } from "./trending";

const DEBOUNCE_MS = 180;

/**
 * Screen 2 of the guest flow: type, see matches, tap one to send it.
 *
 * Tapping a suggestion *is* the submit — the fastest path from thumb to
 * queued request. A guest whose song isn't in the catalog can still send the
 * raw text they typed via the fallback button underneath.
 */
export default function SongSearch({
  genreKey,
  pending,
  error,
  onBack,
  onSubmit,
}: {
  genreKey: string;
  pending: boolean;
  error: string | null;
  onBack: () => void;
  onSubmit: (song: {
    title: string;
    artist?: string;
    songId?: string | null;
    artworkUrl?: string | null;
  }) => void;
}) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<Song[]>([]);
  const [searching, setSearching] = useState(false);
  const trending = trendingFor(genreKey);
  const inputRef = useRef<HTMLInputElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

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
        const res = await api.searchSongs(q, genreKey, 8);
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
  }, [query, genreKey]);

  const pickSong = (song: Song) => {
    haptic(12);
    onSubmit({
      title: song.title,
      artist: song.artist,
      songId: song.id,
      artworkUrl: song.artwork_url,
    });
  };

  const requestTyped = () => {
    const value = query.trim();
    if (!value || pending) return;
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
            {genreLabel(genreKey)}
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
          disabled={pending}
          className="block w-full bg-transparent text-[20px] font-medium tracking-[-0.01em] text-chalk caret-cue-1 outline-none placeholder:text-mist/60 disabled:opacity-70"
        />
      </div>

      {error ? (
        <p role="alert" className="mt-3 rounded-xl border border-hold/40 bg-hold/10 px-4 py-3 text-[14px] text-chalk/90 animate-rise">
          {error}
        </p>
      ) : null}

      <div className="mt-4 min-h-[3rem]">
        {query.trim() ? (
          results.length > 0 ? (
            <SongList songs={results} pending={pending} onPick={pickSong} />
          ) : !searching ? (
            <div className="animate-rise">
              <p className="px-1 text-[14px] text-mist">No match in the catalog yet.</p>
              <button
                type="button"
                disabled={pending}
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
        ) : trending.length > 0 ? (
          <div className="animate-rise">
            <p className="px-1 text-[12px] font-medium uppercase tracking-[0.14em] text-mist/60">
              Popular right now
            </p>
            <div className="mt-2">
              <SongList songs={trending} pending={pending} onPick={pickSong} />
            </div>
          </div>
        ) : (
          <p className="px-1 text-[14px] text-mist/70">
            Start typing — matches from the {genreLabel(genreKey)} catalog show up here.
          </p>
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
