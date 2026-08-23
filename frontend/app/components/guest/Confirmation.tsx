"use client";

import { useEffect, useRef } from "react";
import type { RequestAck } from "@/lib/types";
import CountUp from "./CountUp";

/** Expanding rings — the request visibly leaving the phone and hitting the floor. */
function Ripple() {
  return (
    <div className="relative mx-auto flex h-20 w-20 items-center justify-center">
      <style>{`
        @keyframes cue-ripple {
          0% { opacity: 0.75; transform: scale(0.55); }
          80% { opacity: 0; transform: scale(2.1); }
          100% { opacity: 0; transform: scale(2.1); }
        }
      `}</style>
      {[0, 0.6, 1.2].map((delay) => (
        <span
          key={delay}
          aria-hidden="true"
          className="absolute inset-0 rounded-full border border-cue-1/50"
          style={{
            animation: "cue-ripple 2.4s cubic-bezier(0.16, 1, 0.3, 1) infinite",
            animationDelay: `${delay}s`,
          }}
        />
      ))}
      <span className="relative flex h-12 w-12 items-center justify-center rounded-full bg-gradient-to-br from-cue-1 to-cue-2 shadow-[0_0_44px_-6px_rgba(255,45,120,0.85)]">
        <svg
          viewBox="0 0 24 24"
          className="h-6 w-6"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <path d="M20 6 9 17l-5-5" />
        </svg>
      </span>
    </div>
  );
}

export default function Confirmation({
  ack,
  toastCopy,
  instagramHandle,
  onRequestAnother,
  onChangeGenre,
}: {
  ack: RequestAck;
  /** DJ-configured copy (settings.confirmation_toast_copy) that replaces the
   * default per-submission message when set. Null for every event that
   * hasn't configured one -- unchanged behaviour. */
  toastCopy?: string | null;
  /** Config-gated (settings.instagram_handle), same as GenreGrid's Follow
   * button. When set, this screen's two actions become "DM Your DJ" (an
   * IG link) and "Home" instead of "Request another song" / "Different
   * genre" -- an event that hasn't configured a handle keeps today's
   * behaviour unchanged rather than ever showing a dead link. */
  instagramHandle?: string | null;
  onRequestAnother: () => void;
  onChangeGenre: () => void;
}) {
  const headingRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    headingRef.current?.focus();
  }, []);

  // The configured copy is a complete, self-contained message (DJ
  // Prashant's own wording doesn't reference a vote count) -- showing it
  // alongside the crowd-count line would read like two different messages
  // bolted together, so it takes over the whole block instead of just the
  // heading.
  const crowd = !toastCopy && ack.request_count > 1;

  return (
    <div className="flex flex-col">
      <div
        ref={headingRef}
        tabIndex={-1}
        role="status"
        aria-live="polite"
        className="flex flex-col items-center text-center outline-none animate-rise"
      >
        <Ripple />

        <p className="mt-6 max-w-[19rem] truncate text-[14px] text-mist/80">
          &ldquo;{ack.song_title}&rdquo;
        </p>

        <h1
          className={
            toastCopy
              ? "mt-2 max-w-[22rem] text-[19px] leading-[1.5] font-medium text-balance text-chalk"
              : "mt-2 text-[27px] leading-[1.2] font-semibold tracking-[-0.02em] text-balance text-chalk"
          }
        >
          {toastCopy || ack.message || "Got it. The DJ has your request."}
        </h1>

        {crowd ? (
          <p
            className="mt-5 max-w-[21rem] text-[17px] leading-[1.45] text-mist animate-rise"
            style={{ animationDelay: "120ms", animationFillMode: "backwards" }}
          >
            <span className="font-semibold text-chalk">
              <CountUp value={ack.request_count} />
            </span>{" "}
            people want this one.
          </p>
        ) : !toastCopy ? (
          <p
            className="mt-5 max-w-[21rem] text-[17px] leading-[1.45] text-mist animate-rise"
            style={{ animationDelay: "120ms", animationFillMode: "backwards" }}
          >
            The DJ sees it on the dashboard now.
          </p>
        ) : null}
      </div>

      {instagramHandle ? (
        <>
          <a
            href={`https://www.instagram.com/${instagramHandle}/`}
            target="_blank"
            rel="noopener noreferrer"
            className="tap mt-9 flex h-14 w-full items-center justify-center gap-2 rounded-2xl bg-gradient-to-r from-cue-1 to-cue-2 text-[17px] font-semibold text-white shadow-[0_10px_40px_-12px_rgba(255,45,120,0.75)] transition-all duration-150 active:scale-[0.985] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-chalk/80 focus-visible:ring-offset-2 focus-visible:ring-offset-ink"
          >
            <svg viewBox="0 0 24 24" className="h-[18px] w-[18px] shrink-0" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
              <rect x="3" y="3" width="18" height="18" rx="5" />
              <circle cx="12" cy="12" r="4" />
              <circle cx="17.2" cy="6.8" r="1" fill="currentColor" stroke="none" />
            </svg>
            DM Your DJ
          </a>

          <button
            type="button"
            onClick={onChangeGenre}
            className="tap mt-3 flex h-14 w-full items-center justify-center gap-2 rounded-2xl border border-ink-line bg-ink-card/80 text-[16px] font-semibold text-chalk transition-colors duration-150 active:bg-ink-line/70 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cue-1/70"
          >
            <svg viewBox="0 0 24 24" className="h-[18px] w-[18px] shrink-0" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M4 11.5 12 4l8 7.5" />
              <path d="M6 10v9a1 1 0 0 0 1 1h3v-6h4v6h3a1 1 0 0 0 1-1v-9" />
            </svg>
            Home
          </button>
        </>
      ) : (
        <>
          <button
            type="button"
            onClick={onRequestAnother}
            className="tap mt-9 flex h-14 w-full items-center justify-center rounded-2xl bg-gradient-to-r from-cue-1 to-cue-2 text-[17px] font-semibold text-white shadow-[0_10px_40px_-12px_rgba(255,45,120,0.75)] transition-all duration-150 active:scale-[0.985] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-chalk/80 focus-visible:ring-offset-2 focus-visible:ring-offset-ink"
          >
            Request another song
          </button>

          <button
            type="button"
            onClick={onChangeGenre}
            className="tap mt-3 flex h-14 w-full items-center justify-center rounded-2xl border border-ink-line bg-ink-card/80 text-[16px] font-semibold text-chalk transition-colors duration-150 active:bg-ink-line/70 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cue-1/70"
          >
            Different genre
          </button>
        </>
      )}
    </div>
  );
}
