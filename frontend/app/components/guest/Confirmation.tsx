"use client";

import { useEffect, useRef } from "react";
import type { RequestAck } from "@/lib/types";
import CountUp from "./CountUp";
import { intentChips } from "./intent";
import type { GuestHistoryEntry } from "./useGuestHistory";

function timeAgo(at: number): string {
  if (!at) return "";
  const secs = Math.max(0, Math.round((Date.now() - at) / 1000));
  if (secs < 60) return "just now";
  const mins = Math.round(secs / 60);
  if (mins < 60) return `${mins}m ago`;
  return `${Math.round(mins / 60)}h ago`;
}

/** Expanding rings — the request visibly leaving the phone and hitting the floor. */
function Ripple() {
  return (
    <div className="relative mx-auto flex h-20 w-20 items-center justify-center">
      {/* Scoped keyframes: globals.css is frozen, and `cue-ripple` is namespaced
          so it cannot collide with the DJ surface. The global
          prefers-reduced-motion rule still flattens it. */}
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
  submittedText,
  history,
  onAskAgain,
}: {
  ack: RequestAck;
  submittedText: string;
  history: GuestHistoryEntry[];
  onAskAgain: () => void;
}) {
  const headingRef = useRef<HTMLDivElement>(null);

  // Focus follows the state change: the textarea just unmounted, so without
  // this a screen reader (and keyboard tab order) would fall back to <body>.
  useEffect(() => {
    headingRef.current?.focus();
  }, []);

  const chips = intentChips(ack.intent_summary);
  // Assumption: wave_size counts this request too, so the crowd behind you is
  // one fewer. If the wave is somehow reported as a party of one, fall back to
  // copy that is still true rather than claiming "0 other people".
  const others = Math.max(0, (ack.wave_size || 0) - 1);
  const label = ack.wave_label?.trim();
  const mode: "crowd" | "watched" | "new" = !ack.joined_existing_wave
    ? "new"
    : others > 0
      ? "crowd"
      : "watched";
  const earlier = history.filter((e) => e.id !== ack.request_id);

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

        {submittedText ? (
          <p className="mt-6 max-w-[19rem] truncate text-[14px] text-mist/80">
            “{submittedText}”
          </p>
        ) : null}

        <h1 className="mt-2 text-[27px] leading-[1.2] font-semibold tracking-[-0.02em] text-balance text-chalk">
          {ack.message || "Got it. The DJ has your request."}
        </h1>

        <p
          className="mt-5 max-w-[21rem] text-[17px] leading-[1.45] text-mist animate-rise"
          style={{ animationDelay: "120ms", animationFillMode: "backwards" }}
        >
          {mode === "crowd" ? (
            <>
              Your request just joined a wave of{" "}
              <span className="font-semibold text-chalk">
                <CountUp value={others} />
              </span>{" "}
              {others === 1 ? "other person" : "other people"}
              {label ? (
                <>
                  {" "}
                  asking for{" "}
                  <span className="font-semibold text-cue-1">{label}</span>
                </>
              ) : null}
              .
            </>
          ) : mode === "watched" ? (
            <>
              Your request joined
              {label ? (
                <>
                  {" "}
                  <span className="font-semibold text-cue-1">{label}</span>
                </>
              ) : (
                <> a wave</>
              )}
              {" — the DJ is already watching it."}
            </>
          ) : (
            <>
              You just started a new wave
              {label ? (
                <>
                  {" — "}
                  <span className="font-semibold text-cue-1">{label}</span>
                </>
              ) : null}
              . The DJ sees it now.
            </>
          )}
        </p>

        {chips.length > 0 ? (
          <ul
            className="mt-6 flex flex-wrap justify-center gap-2 animate-rise"
            style={{ animationDelay: "220ms", animationFillMode: "backwards" }}
          >
            {chips.map((chip) => (
              <li
                key={chip}
                className="rounded-full border border-cue-2/35 bg-cue-2/10 px-3 py-1.5 text-[13px] font-medium text-chalk/90"
              >
                {chip}
              </li>
            ))}
          </ul>
        ) : null}
      </div>

      <button
        type="button"
        onClick={onAskAgain}
        className="tap mt-9 flex h-14 w-full items-center justify-center rounded-2xl border border-ink-line bg-ink-card/80 text-[17px] font-semibold text-chalk transition-colors duration-150 active:bg-ink-line/70 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cue-1/70"
      >
        Ask for something else
      </button>

      {earlier.length > 0 ? (
        <section className="mt-9">
          <h2 className="mb-3 text-[13px] tracking-[0.14em] text-mist/80 uppercase">
            Earlier tonight
          </h2>
          <ul className="flex flex-col gap-2">
            {earlier.map((entry) => (
              <li
                key={entry.id}
                className="card flex items-center justify-between gap-3 px-4 py-3"
              >
                <div className="min-w-0">
                  <p className="truncate text-[15px] text-chalk/90">{entry.text}</p>
                  <p className="mt-0.5 truncate text-[12px] text-mist">
                    {entry.waveLabel
                      ? `${entry.joined ? "joined" : "started"} ${entry.waveLabel}`
                      : entry.joined
                        ? "joined a wave"
                        : "started a wave"}
                  </p>
                </div>
                <span className="tnum shrink-0 text-[12px] text-mist/70">
                  {timeAgo(entry.at)}
                </span>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  );
}
