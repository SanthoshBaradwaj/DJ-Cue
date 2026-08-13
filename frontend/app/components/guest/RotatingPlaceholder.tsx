"use client";

import { useEffect, useState } from "react";
import { usePrefersReducedMotion } from "./motion";

/**
 * The examples ARE the instructions. Rotating them teaches the input's range —
 * vibe, era, artist, half-remembered description — without a line of help text.
 */
export const PLACEHOLDER_EXAMPLES = [
  "punjabi wedding chaos",
  "2010s bollywood romance",
  "that hrithik song where everyone dances",
  "something romantic but we can still dance",
  "90s throwback bangers",
  "make the aunties get up",
];

const INTERVAL_MS = 3000;
const FADE_MS = 320;

/**
 * A real `placeholder` attribute can't crossfade, so this is an overlay that
 * mirrors the textarea's box exactly. It is aria-hidden and pointer-events-none:
 * the textarea keeps its own sr-only-labelled identity, and taps fall through.
 */
export default function RotatingPlaceholder({ paused }: { paused: boolean }) {
  const reduced = usePrefersReducedMotion();
  const [index, setIndex] = useState(0);
  const [visible, setVisible] = useState(true);

  useEffect(() => {
    if (paused) return;
    if (reduced) {
      // Still rotate (the examples are informational) but without the fade.
      const id = setInterval(
        () => setIndex((i) => (i + 1) % PLACEHOLDER_EXAMPLES.length),
        INTERVAL_MS,
      );
      return () => clearInterval(id);
    }

    let fadeIn: ReturnType<typeof setTimeout> | undefined;
    const id = setInterval(() => {
      setVisible(false);
      fadeIn = setTimeout(() => {
        setIndex((i) => (i + 1) % PLACEHOLDER_EXAMPLES.length);
        setVisible(true);
      }, FADE_MS);
    }, INTERVAL_MS);

    return () => {
      clearInterval(id);
      if (fadeIn) clearTimeout(fadeIn);
    };
  }, [paused, reduced]);

  if (paused) return null;

  return (
    <div
      aria-hidden="true"
      className="pointer-events-none absolute inset-0 select-none px-5 py-5 text-[22px] leading-[1.35] font-medium tracking-[-0.01em] text-mist/55 transition-opacity duration-300"
      style={{ opacity: visible ? 1 : 0 }}
    >
      {PLACEHOLDER_EXAMPLES[index]}
    </div>
  );
}
