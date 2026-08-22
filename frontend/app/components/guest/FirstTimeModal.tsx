"use client";

import { useEffect, useRef } from "react";
import { haptic } from "./motion";

/**
 * Config-gated onboarding modal -- only rendered when the event's DJ has
 * turned settings.first_time_prompt_enabled on, and only once per event per
 * device (GuestApp tracks that in localStorage).
 *
 * "Already answered" is a pure client-side dismiss, not a third answer
 * value -- it exists for a guest who remembers answering earlier but landed
 * here again (a reload, a second QR scan), and it never calls the API.
 */
export default function FirstTimeModal({
  onAnswer,
  onDismiss,
}: {
  onAnswer: (answer: "yes" | "no") => void;
  onDismiss: () => void;
}) {
  const headingRef = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    headingRef.current?.focus();
  }, []);

  const choose = (fn: () => void) => {
    haptic(12);
    fn();
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="fta-heading"
      className="fixed inset-0 z-50 flex items-end justify-center bg-ink/80 backdrop-blur-sm animate-rise sm:items-center sm:p-4"
    >
      <div className="w-full max-w-[420px] rounded-t-3xl border border-ink-line bg-ink-card px-6 pt-6 shadow-2xl sm:rounded-3xl"
        style={{ paddingBottom: "calc(env(safe-area-inset-bottom) + 1.5rem)" }}
      >
        <h2
          id="fta-heading"
          ref={headingRef}
          tabIndex={-1}
          className="text-[21px] font-semibold tracking-[-0.02em] text-chalk outline-none"
        >
          Is this your first time?
        </h2>

        <div className="mt-5 flex flex-col gap-2.5">
          <button
            type="button"
            onClick={() => choose(() => onAnswer("yes"))}
            className="tap flex h-14 w-full items-center justify-center rounded-2xl bg-gradient-to-r from-cue-1 to-cue-2 text-[16px] font-semibold text-white shadow-[0_10px_40px_-12px_rgba(255,45,120,0.75)] transition-all duration-150 active:scale-[0.985] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-chalk/80 focus-visible:ring-offset-2 focus-visible:ring-offset-ink"
          >
            Yes
          </button>
          <button
            type="button"
            onClick={() => choose(() => onAnswer("no"))}
            className="tap flex h-14 w-full items-center justify-center rounded-2xl border border-ink-line bg-ink/60 text-[16px] font-semibold text-chalk transition-colors duration-150 active:bg-ink-line/70 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cue-1/70"
          >
            No
          </button>
          <button
            type="button"
            onClick={() => choose(onDismiss)}
            className="tap flex h-12 w-full items-center justify-center rounded-2xl text-[14px] font-medium text-mist transition-colors duration-150 active:text-chalk focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cue-1/70"
          >
            Already answered
          </button>
        </div>
      </div>
    </div>
  );
}
