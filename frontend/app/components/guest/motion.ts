"use client";

import { useEffect, useState } from "react";

/**
 * Reduced-motion preference, SSR-safe.
 *
 * globals.css already neuters durations globally, but a few effects here are
 * driven in JS (the count-up, the placeholder crossfade) and have to opt out
 * explicitly.
 */
export function usePrefersReducedMotion(): boolean {
  const [reduced, setReduced] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined" || !window.matchMedia) return;
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReduced(mq.matches);
    const onChange = (e: MediaQueryListEvent) => setReduced(e.matches);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);

  return reduced;
}

/** A single soft tick on submit. Silently absent on iOS — never gate on it. */
export function haptic(ms = 12): void {
  if (typeof navigator === "undefined") return;
  try {
    navigator.vibrate?.(ms);
  } catch {
    /* some browsers throw when the page is not visible */
  }
}
