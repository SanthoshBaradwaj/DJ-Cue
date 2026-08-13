"use client";

import { useLayoutEffect, useRef, type RefObject } from "react";

/**
 * FLIP the direct children of `ref` whenever `signature` changes.
 *
 * Waves are re-ranked live while the DJ is looking at them, and a card that
 * teleports to a new position reads as a glitch on stage. Each child opts in
 * with `data-flip-key`; we remember its offset, then play the difference back
 * as a transform so the browser animates the move on the compositor.
 */
export function useFlipReorder(
  ref: RefObject<HTMLElement | null>,
  signature: string,
) {
  const previous = useRef<Map<string, number>>(new Map());

  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;

    const reduced =
      typeof window !== "undefined" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    const next = new Map<string, number>();
    const frames: number[] = [];

    for (const child of Array.from(el.children) as HTMLElement[]) {
      const key = child.dataset.flipKey;
      if (!key) continue;
      const top = child.offsetTop;
      next.set(key, top);
      if (reduced) continue;

      const before = previous.current.get(key);
      if (before === undefined || before === top) continue;

      child.style.transition = "none";
      child.style.transform = `translateY(${before - top}px)`;
      frames.push(
        requestAnimationFrame(() => {
          child.style.transition = "transform 520ms cubic-bezier(0.16, 1, 0.3, 1)";
          child.style.transform = "";
        }),
      );
    }

    previous.current = next;
    return () => frames.forEach(cancelAnimationFrame);
  }, [ref, signature]);
}
