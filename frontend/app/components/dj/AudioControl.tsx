"use client";

/**
 * The booth's audio control: one tap to arm, then a mute and a fade indicator.
 *
 * Kept deliberately quiet in the layout. It is scaffolding for the demo, not
 * part of the product's argument, so it must never compete with a wave card for
 * attention — but it does have to be honest about what the room is hearing.
 */

import type { AudioDeck } from "./useAudioDeck";

export function AudioControl({
  deck,
  trackTitle,
}: {
  deck: AudioDeck;
  trackTitle: string | null;
}) {
  if (!deck.armed) {
    return (
      <button
        type="button"
        onClick={deck.arm}
        className="flex h-9 items-center gap-2 rounded-lg border border-ink-line px-3 text-[11px] font-semibold uppercase tracking-[0.14em] text-mist transition-colors hover:border-mist/40 hover:text-chalk"
        title="Browsers need a tap before any page can play audio"
      >
        <SpeakerIcon muted />
        Enable audio
      </button>
    );
  }

  return (
    <div className="flex h-9 items-center gap-2.5 rounded-lg border border-ink-line px-3">
      <button
        type="button"
        onClick={deck.toggleMute}
        className="text-mist transition-colors hover:text-chalk"
        aria-pressed={deck.muted}
        aria-label={deck.muted ? "Unmute the room" : "Mute the room"}
        title={deck.muted ? "Unmute" : "Mute"}
      >
        <SpeakerIcon muted={deck.muted} />
      </button>

      <span className="h-4 w-px bg-ink-line" aria-hidden="true" />

      <span className="text-[11px] font-medium tracking-[0.04em] text-mist/80">
        {deck.muted
          ? "Muted"
          : deck.fading
            ? "Crossfading…"
            : trackTitle
              ? deck.usingFile
                ? "Playing file"
                : "Playing synth"
              : "Ready"}
      </span>

      {deck.fading && !deck.muted && (
        <span
          className="h-1.5 w-1.5 rounded-full animate-pulse-ring"
          style={{ background: "var(--color-go)" }}
          aria-hidden="true"
        />
      )}

      {deck.error && <span className="text-[11px] text-mist/70">{deck.error}</span>}
    </div>
  );
}

function SpeakerIcon({ muted }: { muted: boolean }) {
  return (
    <svg
      viewBox="0 0 24 24"
      className="h-4 w-4"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M4 9v6h3l5 4V5L7 9H4z" />
      {muted ? (
        <path d="M16 9l5 5m0-5l-5 5" />
      ) : (
        <>
          <path d="M16.5 8.5a5 5 0 0 1 0 7" />
          <path d="M19 6a8.5 8.5 0 0 1 0 12" />
        </>
      )}
    </svg>
  );
}
