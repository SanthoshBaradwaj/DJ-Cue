"use client";

import type { PulseStatus } from "@/lib/types";
import { haptic } from "./motion";

const OPTIONS: { key: PulseStatus; label: string; color: string }[] = [
  { key: "single", label: "Single & ready to talk", color: "var(--color-pulse-single)" },
  { key: "committed", label: "Committed", color: "var(--color-pulse-committed)" },
];

/**
 * Small, optional slider-style control for the crowd-pulse signal. No
 * default selection -- a guest who never touches it sends nothing, which is
 * the point ("keep it optional"). Built as a single track with a sliding
 * highlight rather than two independent buttons, so it reads as one control
 * with two positions, not a form field.
 */
export default function PulseToggle({
  value,
  onChange,
}: {
  value: PulseStatus | null;
  onChange: (status: PulseStatus) => void;
}) {
  const pick = (status: PulseStatus) => {
    haptic(8);
    onChange(status);
  };

  return (
    <div
      className="relative mt-4 flex w-full max-w-full rounded-full border border-ink-line bg-ink-card/60 p-1 text-[12px]"
      role="group"
      aria-label="Optional: let the DJ know if you're single or committed"
    >
      {value && (
        <span
          aria-hidden="true"
          className="absolute inset-y-1 w-[calc(50%-4px)] rounded-full transition-transform duration-200 ease-out"
          style={{
            background: `color-mix(in oklab, ${OPTIONS.find((o) => o.key === value)!.color} 22%, transparent)`,
            transform: value === "committed" ? "translateX(calc(100% + 8px))" : "translateX(0)",
          }}
        />
      )}
      {OPTIONS.map((opt) => (
        <button
          key={opt.key}
          type="button"
          onClick={() => pick(opt.key)}
          aria-pressed={value === opt.key}
          className="tap relative z-10 flex-1 rounded-full px-2 py-1.5 text-center font-medium transition-colors"
          style={{ color: value === opt.key ? opt.color : "var(--color-mist)" }}
        >
          {opt.label}
        </button>
      ))}
    </div>
  );
}
