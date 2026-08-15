"use client";

import type { DJStatus } from "@/lib/types";

const ORDER: DJStatus[] = ["open", "closed"];

const COPY: Record<DJStatus, { label: string; color: string }> = {
  open: { label: "Taking requests", color: "var(--color-go)" },
  closed: { label: "Not taking requests", color: "var(--color-drop)" },
};

/**
 * One tap flips open <-> closed. Deliberately a single control with no
 * confirmation step or menu -- this gets tapped between songs, often
 * one-handed, and a DJ (or a very insistent guest who grabbed the tablet)
 * needs it to register on the first touch, not the second. Flipping to
 * "closed" is enforced server-side -- guests are blocked from submitting,
 * not just shown a different label.
 */
export function DJStatusToggle({
  status,
  onChange,
  busy,
}: {
  status: DJStatus;
  onChange: (next: DJStatus) => void;
  busy?: boolean;
}) {
  const copy = COPY[status];
  const advance = () => {
    const next = ORDER[(ORDER.indexOf(status) + 1) % ORDER.length];
    onChange(next);
  };

  return (
    <button
      type="button"
      onClick={advance}
      disabled={busy}
      title="Tap to change what guests see"
      aria-label={`Guest-facing status: ${copy.label}. Tap to change.`}
      className="tap flex shrink-0 items-center gap-2 rounded-full border px-3 py-1.5 text-[12px] font-bold transition-transform active:scale-95 disabled:opacity-60"
      style={{
        borderColor: `color-mix(in oklab, ${copy.color} 40%, transparent)`,
        background: `color-mix(in oklab, ${copy.color} 12%, transparent)`,
        color: copy.color,
      }}
    >
      <span className="h-1.5 w-1.5 shrink-0 rounded-full" style={{ background: copy.color }} aria-hidden="true" />
      {copy.label}
    </button>
  );
}
