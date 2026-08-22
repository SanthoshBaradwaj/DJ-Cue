"use client";

import type { CSSProperties } from "react";
import type { PulseStatus } from "@/lib/types";
import { haptic } from "./motion";

const LABEL: Record<PulseStatus, string> = {
  single: "Single & ready to talk",
  committed: "Committed",
};
const COLOR: Record<PulseStatus, string> = {
  single: "var(--color-pulse-single)",
  committed: "var(--color-pulse-committed)",
};

/** One glyph per state -- a spark for "available", linked rings for
 * "committed" -- so the two read as distinct at a glance, not just two
 * differently-coloured blocks of text. Same thin-stroke, rounded-cap style
 * as every other icon in the guest UI. */
function PulseGlyph({ status }: { status: PulseStatus }) {
  if (status === "single") {
    return (
      <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <circle cx="12" cy="12" r="5.5" />
        <path d="M12 2.5v2.2M12 19.3v2.2M21.5 12h-2.2M4.7 12H2.5M18.5 5.5l-1.6 1.6M7.1 16.9l-1.6 1.6M18.5 18.5l-1.6-1.6M7.1 7.1L5.5 5.5" />
      </svg>
    );
  }
  return (
    <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <circle cx="9" cy="12" r="5" />
      <circle cx="15" cy="12" r="5" />
    </svg>
  );
}

/**
 * Full-width, fully-labelled crowd-pulse control -- a second entry point to
 * the exact same vote as the header's compact PulseToggle icon. Same
 * onChange, so it lands on the same endpoint and the same session-scoped
 * 5-toggle cap the backend already enforces; this component only renders
 * state, it never re-derives or duplicates that limit.
 *
 * Sized and weighted to match the genre grid below it (same 19px label,
 * same card treatment, same hover/press motion) rather than reading as a
 * lightweight footnote above the "real" buttons.
 */
export default function PulseChoice({
  value,
  limited,
  pending,
  onChange,
}: {
  value: PulseStatus | null;
  limited: boolean;
  pending: boolean;
  onChange: (status: PulseStatus) => void;
}) {
  const pick = (status: PulseStatus) => {
    if (pending) return;
    if (limited) {
      haptic(14);
      return;
    }
    haptic(10);
    onChange(status);
  };

  return (
    <div className="mt-6">
      <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-mist">Tap your vibe</p>
      <div
        role="group"
        aria-label="Crowd pulse: single or committed"
        className="mt-2 grid grid-cols-2 gap-3"
      >
        {(["single", "committed"] as PulseStatus[]).map((opt) => {
          const active = value === opt;
          const accent = COLOR[opt];
          return (
            <button
              key={opt}
              type="button"
              onClick={() => pick(opt)}
              disabled={pending}
              aria-pressed={active}
              style={
                {
                  "--accent": accent,
                  borderColor: `color-mix(in oklab, ${accent} ${active ? 65 : 42}%, var(--color-ink-line))`,
                  background: `color-mix(in oklab, ${accent} ${active ? 22 : 13}%, var(--color-ink-card))`,
                  color: active ? accent : "var(--color-chalk)",
                } as CSSProperties
              }
              className="tap group/pulse relative flex min-h-24 flex-col items-center justify-center gap-1 overflow-hidden rounded-2xl border px-2.5 py-3 text-center transition-all duration-200 ease-out hover:-translate-y-0.5 hover:shadow-[0_14px_32px_-16px_var(--accent)] hover:[border-color:color-mix(in_oklab,var(--accent)_65%,var(--color-ink-line))] hover:[background:color-mix(in_oklab,var(--accent)_20%,var(--color-ink-card))] active:translate-y-0 active:scale-[0.96] active:duration-100 active:[background:color-mix(in_oklab,var(--accent)_28%,var(--color-ink-card))] focus-visible:outline-none focus-visible:ring-2 focus-visible:[--tw-ring-color:var(--accent)] disabled:opacity-60"
            >
              <span
                aria-hidden="true"
                className="absolute top-0 left-0 h-[3px] w-full origin-left transition-transform duration-200 ease-out"
                style={{ background: accent, transform: active ? "scaleX(1)" : "scaleX(0)" }}
              />
              <PulseGlyph status={opt} />
              <span className="text-[19px] font-semibold leading-[1.15] tracking-[-0.01em]">
                {LABEL[opt]}
              </span>
            </button>
          );
        })}
      </div>
      {limited && (
        <p className="mt-2 text-center text-[12px] leading-snug text-mist">
          That&apos;s five changes — we hear you, tough crowd. Locking it in!
        </p>
      )}
    </div>
  );
}
