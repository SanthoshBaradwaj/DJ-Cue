"use client";

import type { Candidate, DJAction } from "@/lib/types";
import { Chip, EnergyBar, LaterIcon, PlayIcon, SkipIcon, SparkIcon } from "./Primitives";
import { clamp01, tint } from "./theme";

const ACTION_COLOR: Record<DJAction, string> = {
  play: "var(--color-go)",
  later: "var(--color-hold)",
  skip: "var(--color-drop)",
};

const ACTION_DONE: Record<DJAction, string> = {
  play: "Playing next",
  later: "Queued for later",
  skip: "Skipped",
};

function ActionButton({
  action,
  label,
  icon,
  wide,
  disabled,
  onClick,
}: {
  action: DJAction;
  label: string;
  icon: React.ReactNode;
  wide?: boolean;
  disabled: boolean;
  onClick: () => void;
}) {
  const color = ACTION_COLOR[action];
  const filled = action === "play";
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={`tap group/btn flex min-h-[52px] items-center justify-center gap-2 rounded-xl border text-[13px] font-bold uppercase tracking-[0.14em] transition-all duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-ink-card active:scale-[0.97] disabled:opacity-40 ${
        wide ? "flex-[1.5]" : "flex-1"
      } ${filled ? "text-ink" : ""}`}
      style={{
        background: filled ? color : tint(color, 10),
        borderColor: filled ? color : tint(color, 40),
        color: filled ? "var(--color-ink)" : color,
        // Tailwind can't see a runtime colour, so the focus ring is set here.
        ["--tw-ring-color" as string]: color,
      }}
    >
      <span className="opacity-90">{icon}</span>
      {label}
    </button>
  );
}

export function CandidateCard({
  candidate,
  accent,
  rank,
  decision,
  tipMinor,
  onDecide,
}: {
  candidate: Candidate;
  accent: string;
  rank: number;
  decision: DJAction | null;
  tipMinor: number;
  onDecide: (action: DJAction) => void;
}) {
  const { track, reasons, bpm_delta: delta, score } = candidate;
  const decided = decision !== null;
  const doneColor = decision ? ACTION_COLOR[decision] : accent;

  // A same-tempo or near-tempo pick is a clean blend; anything past 8 BPM is a
  // deliberate gear change and should look like one.
  const deltaTone =
    delta === null || delta === 0
      ? "var(--color-mist)"
      : Math.abs(delta) <= 8
        ? "var(--color-go)"
        : "var(--color-hold)";

  return (
    <article
      className="relative overflow-hidden rounded-2xl border p-4 transition-all duration-500 ease-out sm:p-5"
      style={{
        borderColor: decided ? tint(doneColor, 45) : "var(--color-ink-line)",
        background: decided
          ? tint(doneColor, 9)
          : "color-mix(in oklab, var(--color-ink-raised) 70%, transparent)",
        opacity: decided ? 0.85 : 1,
        transform: decided ? "scale(0.985)" : "none",
      }}
    >
      {/* Optimistic confirmation — the tap must land before the socket echoes. */}
      {decided && decision && (
        <div
          className="animate-rise absolute inset-0 z-10 flex items-center justify-center gap-3 backdrop-blur-[2px]"
          style={{ background: tint(doneColor, 14) }}
        >
          <span
            className="h-2.5 w-2.5 rounded-full"
            style={{ background: doneColor }}
            aria-hidden="true"
          />
          <span
            className="text-sm font-bold uppercase tracking-[0.2em]"
            style={{ color: doneColor }}
          >
            {ACTION_DONE[decision]}
          </span>
        </div>
      )}

      <div className="flex items-start justify-between gap-4">
        <div className="flex min-w-0 items-start gap-3">
          <span
            className="tnum mt-1 shrink-0 text-[11px] font-bold tabular-nums"
            style={{ color: tint(accent, 75) }}
          >
            {String(rank).padStart(2, "0")}
          </span>
          <div className="min-w-0">
            <h4 className="truncate text-[17px] font-semibold leading-snug text-chalk">
              {track.title}
            </h4>
            <p className="truncate text-[13px] text-mist">{track.artist}</p>
          </div>
        </div>

        <div className="shrink-0 text-right leading-none">
          <span
            className="tnum text-lg font-bold"
            style={{ color: tint(accent, 88) }}
          >
            {Math.round(clamp01(score) * 100)}
          </span>
          <span className="mt-1 block text-[9px] uppercase tracking-[0.14em] text-mist/60">
            match
          </span>
          {tipMinor > 0 && (
            <span
              className="tnum mt-1.5 inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-bold"
              style={{
                background: "color-mix(in oklab, var(--color-tip) 15%, transparent)",
                color: "var(--color-tip)",
                border: "1px solid color-mix(in oklab, var(--color-tip) 35%, transparent)",
              }}
            >
              <svg viewBox="0 0 16 16" className="h-3 w-3" fill="currentColor" aria-hidden="true">
                <path d="M8 1a1 1 0 0 1 .894.553l.448.894H12a1 1 0 0 1 .707 1.707L11.414 5.5l.293.293a1 1 0 0 1-1.414 1.414L10 6.914l-.293.293a1 1 0 0 1-1.414 0L8 6.914l-.293.293a1 1 0 0 1-1.414 0L6 6.914l-.293.293a1 1 0 0 1-1.414-1.414l.293-.293-1.293-1.346A1 1 0 0 1 4 2.447h2.658l.448-.894A1 1 0 0 1 8 1ZM5 9a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v4.5a1.5 1.5 0 0 1-1.5 1.5h-3A1.5 1.5 0 0 1 5 13.5V9Z" />
              </svg>
              ₹{(tipMinor / 100).toFixed(0)}
            </span>
          )}
        </div>
      </div>

      {/* Mix metadata: everything a DJ checks before committing. */}
      <div className="mt-3.5 flex flex-wrap items-center gap-x-3 gap-y-2 text-[12px]">
        <span className="tnum inline-flex items-center gap-1.5 font-semibold text-chalk/90">
          {track.bpm}
          <span className="text-[10px] font-medium uppercase tracking-[0.12em] text-mist/70">
            bpm
          </span>
          {delta !== null && (
            <span
              className="tnum ml-0.5 rounded-md px-1.5 py-0.5 text-[11px] font-bold"
              style={{ color: deltaTone, background: tint(deltaTone, 12) }}
            >
              {delta > 0 ? `+${delta}` : delta}
            </span>
          )}
        </span>

        <span className="h-3 w-px bg-ink-line" aria-hidden="true" />

        <span className="inline-flex items-center gap-2">
          <EnergyBar energy={track.energy} accent={accent} />
          <span className="tnum text-[11px] text-mist/80">
            {Math.round(clamp01(track.energy) * 100)}
          </span>
        </span>

        <span className="h-3 w-px bg-ink-line" aria-hidden="true" />

        <span className="flex flex-wrap gap-1.5">
          <Chip>{track.language}</Chip>
          <Chip>{track.era}</Chip>
          {track.genres.slice(0, 1).map((g) => (
            <Chip key={g}>{g}</Chip>
          ))}
        </span>
      </div>

      {/* The receipts for the recommendation. */}
      {reasons.length > 0 && (
        <ul className="mt-3.5 flex flex-wrap gap-2">
          {reasons.slice(0, 4).map((r) => (
            <li key={r}>
              <span
                className="inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-[12px] font-medium leading-snug text-chalk/85"
                style={{
                  borderColor: tint(accent, 26),
                  background: tint(accent, 8),
                }}
              >
                <span style={{ color: accent }} aria-hidden="true">
                  <SparkIcon className="h-3 w-3 shrink-0" />
                </span>
                {r}
              </span>
            </li>
          ))}
        </ul>
      )}

      <div className="mt-4 flex gap-2.5">
        <ActionButton
          action="play"
          label="Play"
          wide
          icon={<PlayIcon className="h-3 w-3" />}
          disabled={decided}
          onClick={() => onDecide("play")}
        />
        <ActionButton
          action="later"
          label="Later"
          icon={<LaterIcon className="h-3.5 w-3.5" />}
          disabled={decided}
          onClick={() => onDecide("later")}
        />
        <ActionButton
          action="skip"
          label="Skip"
          icon={<SkipIcon className="h-3 w-3" />}
          disabled={decided}
          onClick={() => onDecide("skip")}
        />
      </div>
    </article>
  );
}
