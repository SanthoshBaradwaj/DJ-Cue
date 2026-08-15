"use client";

import { useEffect, useRef, useState } from "react";
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
const OTHER: Record<PulseStatus, PulseStatus> = { single: "committed", committed: "single" };

const BANNER_MS = 2600;
const PICKER_MS = 4000;

/**
 * Crowd-pulse control, deliberately tiny: a single unlabeled square that
 * sits inline in the header, next to the DJ status pill -- not pinned to
 * the viewport. (An earlier version used `position: fixed` to the screen
 * corner; on any viewport wider than the guest card's own max-width that
 * left it floating alone in the empty margin, disconnected from the rest
 * of the UI. Living in the header's normal flow means it always sits at
 * the corner of the actual card, at any width.) First tap (no value yet)
 * opens a two-option picker to set a baseline; every tap after that is a
 * direct toggle between the two states, matching how the DJ-facing limit
 * is actually framed ("5 toggles"). Wording never sits on screen -- it
 * only appears as a hover peek (desktop) or a brief banner right after an
 * interaction, then gets out of the way again.
 */
export default function PulseToggle({
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
  const [picking, setPicking] = useState(false);
  const [banner, setBanner] = useState<string | null>(null);
  const pickerTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const bannerTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    return () => {
      if (pickerTimer.current) clearTimeout(pickerTimer.current);
      if (bannerTimer.current) clearTimeout(bannerTimer.current);
    };
  }, []);

  const showBanner = (text: string) => {
    setBanner(text);
    if (bannerTimer.current) clearTimeout(bannerTimer.current);
    bannerTimer.current = setTimeout(() => setBanner(null), BANNER_MS);
  };

  const openPicker = () => {
    haptic(8);
    setPicking(true);
    if (pickerTimer.current) clearTimeout(pickerTimer.current);
    pickerTimer.current = setTimeout(() => setPicking(false), PICKER_MS);
  };

  const pick = (status: PulseStatus) => {
    haptic(10);
    setPicking(false);
    if (pickerTimer.current) clearTimeout(pickerTimer.current);
    onChange(status);
    showBanner(LABEL[status]);
  };

  const tapSquare = () => {
    if (pending) return;
    if (limited) {
      haptic(14);
      showBanner("That's five changes -- we hear you, tough crowd. Locking it in!");
      return;
    }
    if (value === null) {
      openPicker();
      return;
    }
    pick(OTHER[value]);
  };

  const glyphColor = value ? COLOR[value] : "var(--color-mist)";

  return (
    <div className="group relative shrink-0">
      <button
        type="button"
        onClick={tapSquare}
        disabled={pending}
        aria-label={
          value
            ? `Crowd pulse: ${LABEL[value]}. Tap to change.`
            : "Optional: share whether you're single or committed"
        }
        className="tap flex h-7 w-7 shrink-0 items-center justify-center rounded-md border transition-transform active:scale-90 disabled:opacity-60"
        style={{
          borderColor: value
            ? `color-mix(in oklab, ${glyphColor} 45%, transparent)`
            : "var(--color-ink-line)",
          background: value
            ? `color-mix(in oklab, ${glyphColor} 16%, transparent)`
            : "color-mix(in oklab, var(--color-ink-card) 70%, transparent)",
        }}
      >
        <span
          aria-hidden="true"
          className="h-1.5 w-1.5 rounded-full transition-colors"
          style={{ background: glyphColor, opacity: value ? 1 : 0.5 }}
        />
      </button>

      {/* Hover peek (desktop only, in effect -- touch has no hover) */}
      {!picking && !banner && (
        <span
          aria-hidden="true"
          className="pointer-events-none absolute right-0 top-full z-20 mt-1.5 whitespace-nowrap rounded-md border border-ink-line bg-ink-card/95 px-2 py-1 text-[11px] text-mist opacity-0 shadow-lg transition-opacity duration-150 group-hover:opacity-100"
        >
          {value ? LABEL[value] : "Optional: single or committed?"}
        </span>
      )}

      {picking && (
        <div className="absolute right-0 top-full z-20 mt-1.5 flex flex-col gap-1 rounded-lg border border-ink-line bg-ink-card/95 p-1 shadow-lg animate-rise">
          {(["single", "committed"] as PulseStatus[]).map((opt) => (
            <button
              key={opt}
              type="button"
              onClick={() => pick(opt)}
              className="tap whitespace-nowrap rounded-md px-2.5 py-1.5 text-left text-[12px] font-medium transition-colors hover:bg-ink-line/60"
              style={{ color: COLOR[opt] }}
            >
              {LABEL[opt]}
            </button>
          ))}
        </div>
      )}

      {banner && (
        <p
          role="status"
          className="pointer-events-none absolute right-0 top-full z-20 mt-1.5 max-w-[13rem] whitespace-normal rounded-md border border-ink-line bg-ink-card/95 px-2.5 py-1.5 text-right text-[11px] leading-snug text-chalk shadow-lg animate-rise"
        >
          {banner}
        </p>
      )}
    </div>
  );
}
