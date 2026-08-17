"use client";

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

/**
 * Full-width, fully-labelled crowd-pulse control -- a second entry point to
 * the exact same vote as the header's compact PulseToggle icon. Same
 * onChange, so it lands on the same endpoint and the same session-scoped
 * 5-toggle cap the backend already enforces; this component only renders
 * state, it never re-derives or duplicates that limit.
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
    <div className="mt-5">
      <div
        role="group"
        aria-label="Crowd pulse: single or committed"
        className="flex overflow-hidden rounded-full border border-ink-line bg-ink-card/60 p-1"
      >
        {(["single", "committed"] as PulseStatus[]).map((opt) => {
          const active = value === opt;
          return (
            <button
              key={opt}
              type="button"
              onClick={() => pick(opt)}
              disabled={pending}
              aria-pressed={active}
              className="tap flex-1 rounded-full px-3 py-3 text-[14px] font-semibold transition-all duration-150 ease-out disabled:opacity-60"
              style={{
                color: active ? COLOR[opt] : "var(--color-mist)",
                background: active
                  ? `color-mix(in oklab, ${COLOR[opt]} 16%, transparent)`
                  : "transparent",
              }}
            >
              {LABEL[opt]}
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
