"use client";

/**
 * Drives the AudioEngine from whatever the backend says is now playing.
 *
 * The DJ arms this once with a tap (browsers require a gesture before any
 * sound), and from then on every PLAY decision crossfades the room without
 * anyone touching the audio controls again.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import type { Track } from "@/lib/types";
import { AudioEngine, CROSSFADE_S } from "./audioEngine";

export interface AudioDeck {
  /** Armed by a user gesture and currently allowed to make sound. */
  armed: boolean;
  muted: boolean;
  /** True while a crossfade is in flight, for the booth indicator. */
  fading: boolean;
  /** Set when the browser refused to start audio at all. */
  error: string | null;
  arm: () => void;
  toggleMute: () => void;
  /** Whether the current track is a real file rather than the synth. */
  usingFile: boolean;
}

export function useAudioDeck(current: Track | null): AudioDeck {
  const engineRef = useRef<AudioEngine | null>(null);
  const [armed, setArmed] = useState(false);
  const [muted, setMuted] = useState(false);
  const [fading, setFading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fadeTimer = useRef<number | null>(null);

  useEffect(
    () => () => {
      if (fadeTimer.current !== null) clearTimeout(fadeTimer.current);
      engineRef.current?.dispose();
      engineRef.current = null;
    },
    [],
  );

  const arm = useCallback(() => {
    if (!engineRef.current) engineRef.current = new AudioEngine();
    void engineRef.current.unlock().then((ok) => {
      setArmed(ok);
      setError(ok ? null : "This browser blocked audio playback.");
    });
  }, []);

  const toggleMute = useCallback(() => {
    setMuted((prev) => {
      const next = !prev;
      engineRef.current?.setMuted(next);
      return next;
    });
  }, []);

  // The only thing that starts music: now-playing changed and we're armed.
  const trackId = current?.id ?? null;
  useEffect(() => {
    if (!armed) return;
    const engine = engineRef.current;
    if (!engine) return;

    void engine.playTrack(current ?? null);

    if (!trackId) return;
    setFading(true);
    if (fadeTimer.current !== null) clearTimeout(fadeTimer.current);
    fadeTimer.current = window.setTimeout(
      () => setFading(false),
      CROSSFADE_S * 1000,
    );
    // `current` is intentionally excluded: a fresh object with the same id is
    // the same song, and re-running would restart the crossfade on every push.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [armed, trackId]);

  return {
    armed,
    muted,
    fading,
    error,
    arm,
    toggleMute,
    usingFile: Boolean(current?.audio_file),
  };
}
