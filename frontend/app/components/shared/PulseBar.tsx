"use client";

/**
 * Minimal aggregate display for the guest-set crowd-pulse slider. Shown on
 * /dj and /present as a placeholder for "what the slider does" -- a
 * two-colour split bar plus a count, nothing more. Renders nothing until at
 * least one guest has voted, so it never occupies space as an empty stat.
 */
export function PulseBar({
  single,
  committed,
  size = "sm",
}: {
  single: number;
  committed: number;
  size?: "sm" | "lg";
}) {
  const total = single + committed;
  if (total === 0) return null;
  const singlePct = Math.round((single / total) * 100);
  const lg = size === "lg";

  return (
    <div className={`flex flex-col ${lg ? "gap-1.5" : "gap-1"}`}>
      <div
        className={`flex overflow-hidden rounded-full ${lg ? "h-2 w-40" : "h-1.5 w-16"}`}
        role="img"
        aria-label={`Crowd pulse: ${singlePct}% single, ${100 - singlePct}% committed, ${total} responded`}
      >
        <div style={{ width: `${singlePct}%`, background: "var(--color-pulse-single)" }} />
        <div style={{ width: `${100 - singlePct}%`, background: "var(--color-pulse-committed)" }} />
      </div>
      <span
        className={`tnum ${lg ? "text-xs" : "text-[10px]"} uppercase tracking-[0.14em] text-mist/60`}
      >
        {singlePct}% single · {total} responded
      </span>
    </div>
  );
}
