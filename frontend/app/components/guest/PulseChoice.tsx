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
    <div className="mt-6">
      <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-mist">Tap your vibe</p>
      <div
        role="group"
        aria-label="Crowd pulse: single or committed"
        className="mt-2 flex gap-2"
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
              className="tap flex flex-1 items-center justify-center gap-2 rounded-2xl border px-3 py-3.5 text-[13.5px] font-semibold leading-snug transition-all duration-150 ease-out active:scale-[0.97] disabled:opacity-60"
              style={{
                borderColor: `color-mix(in oklab, ${COLOR[opt]} ${active ? 55 : 32}%, var(--color-ink-line))`,
                background: `color-mix(in oklab, ${COLOR[opt]} ${active ? 20 : 9}%, var(--color-ink-card))`,
                color: active ? COLOR[opt] : "var(--color-chalk)",
              }}
            >
              <span
                aria-hidden="true"
                className="h-1.5 w-1.5 shrink-0 rounded-full"
                style={{ background: COLOR[opt] }}
              />
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
