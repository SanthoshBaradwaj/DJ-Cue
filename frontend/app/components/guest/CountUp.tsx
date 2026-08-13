"use client";

import { useEffect, useState } from "react";
import { usePrefersReducedMotion } from "./motion";

/** Ticks a count up so "you joined 14 other people" lands as an event, not a fact. */
export default function CountUp({
  value,
  duration = 800,
}: {
  value: number;
  duration?: number;
}) {
  const reduced = usePrefersReducedMotion();
  const [shown, setShown] = useState(0);

  useEffect(() => {
    if (reduced || value <= 0) {
      setShown(value);
      return;
    }
    let frame = 0;
    const start = performance.now();
    const tick = (now: number) => {
      const p = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - p, 3);
      setShown(Math.round(value * eased));
      if (p < 1) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [value, duration, reduced]);

  return <span className="tnum">{shown}</span>;
}
