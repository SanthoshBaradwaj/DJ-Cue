// Small shared pieces. Kept deliberately plain so the wave and candidate cards
// stay readable — nothing here holds state.

import { clamp01, tint } from "./theme";

export function SectionLabel({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <h2
      className={`text-[11px] font-semibold uppercase tracking-[0.22em] text-mist/70 ${className}`}
    >
      {children}
    </h2>
  );
}

export function Chip({
  children,
  accent,
  strong = false,
  className = "",
}: {
  children: React.ReactNode;
  accent?: string;
  strong?: boolean;
  className?: string;
}) {
  const style = accent
    ? {
        background: tint(accent, strong ? 16 : 9),
        borderColor: tint(accent, strong ? 42 : 24),
        color: strong ? "var(--color-chalk)" : undefined,
      }
    : undefined;
  return (
    <span
      style={style}
      className={`inline-flex items-center gap-1.5 rounded-full border border-ink-line bg-white/[0.03] px-2.5 py-1 text-[11px] font-medium leading-none text-mist ${className}`}
    >
      {children}
    </span>
  );
}

/** Five segments read faster than a continuous bar at arm's length. */
export function EnergyBar({
  energy,
  accent = "var(--color-chalk)",
  segments = 5,
}: {
  energy: number;
  accent?: string;
  segments?: number;
}) {
  const filled = Math.round(clamp01(energy) * segments);
  return (
    <span
      className="inline-flex items-center gap-[3px]"
      role="img"
      aria-label={`Energy ${Math.round(clamp01(energy) * 100)} out of 100`}
    >
      {Array.from({ length: segments }, (_, i) => (
        <span
          key={i}
          className="h-3 w-[5px] rounded-[2px] transition-colors duration-300"
          style={{
            background: i < filled ? accent : "var(--color-ink-line)",
            opacity: i < filled ? 0.55 + (i / segments) * 0.45 : 1,
          }}
        />
      ))}
    </span>
  );
}

export function SurgeIcon({ className = "" }: { className?: string }) {
  return (
    <svg viewBox="0 0 12 12" className={className} fill="none" aria-hidden="true">
      <path
        d="M6 10V2m0 0L2.5 5.5M6 2l3.5 3.5"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function PlayIcon({ className = "" }: { className?: string }) {
  return (
    <svg viewBox="0 0 12 12" className={className} aria-hidden="true">
      <path d="M3 1.8v8.4L10 6z" fill="currentColor" />
    </svg>
  );
}

export function LaterIcon({ className = "" }: { className?: string }) {
  return (
    <svg viewBox="0 0 12 12" className={className} fill="none" aria-hidden="true">
      <circle cx="6" cy="6" r="4.6" stroke="currentColor" strokeWidth="1.4" />
      <path d="M6 3.4V6l1.9 1.2" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
    </svg>
  );
}

export function SkipIcon({ className = "" }: { className?: string }) {
  return (
    <svg viewBox="0 0 12 12" className={className} fill="none" aria-hidden="true">
      <path
        d="M2.6 2.6l6.8 6.8M9.4 2.6L2.6 9.4"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
    </svg>
  );
}

export function SparkIcon({ className = "" }: { className?: string }) {
  return (
    <svg viewBox="0 0 12 12" className={className} fill="none" aria-hidden="true">
      <path
        d="M6 1.2l1.15 3.05L10.2 5.4 7.15 6.55 6 9.6 4.85 6.55 1.8 5.4l3.05-1.15z"
        fill="currentColor"
        opacity="0.9"
      />
    </svg>
  );
}
