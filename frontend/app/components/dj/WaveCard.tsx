"use client";

import { useState } from "react";
import type { DJAction, WaveView } from "@/lib/types";
import { CandidateCard } from "./CandidateCard";
import { Chip, SectionLabel, SurgeIcon } from "./Primitives";
import { tint, waveShare } from "./theme";

function Momentum({ momentum, accent }: { momentum: number; accent: string }) {
  if (momentum > 0.5) {
    return (
      <span
        className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[10px] font-bold uppercase tracking-[0.16em]"
        style={{ background: tint(accent, 18), color: accent }}
      >
        <SurgeIcon className="h-3 w-3" />
        Surging
      </span>
    );
  }
  if (momentum < -0.1) {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full bg-white/[0.04] px-2.5 py-1 text-[10px] font-bold uppercase tracking-[0.16em] text-mist/70">
        <SurgeIcon className="h-3 w-3 rotate-180" />
        Cooling
      </span>
    );
  }
  return (
    <span className="rounded-full bg-white/[0.04] px-2.5 py-1 text-[10px] font-bold uppercase tracking-[0.16em] text-mist/60">
      Steady
    </span>
  );
}

/** The words guests actually typed. These are what make the clustering land. */
function Overheard({
  samples,
  accent,
  limit,
}: {
  samples: string[];
  accent: string;
  limit: number;
}) {
  if (samples.length === 0) return null;
  return (
    <ul
      className="space-y-1.5 border-l-2 pl-3.5"
      style={{ borderColor: tint(accent, 32) }}
    >
      {samples.slice(0, limit).map((s, i) => (
        <li
          key={`${i}-${s}`}
          className="truncate text-[13px] italic leading-relaxed text-mist/85"
        >
          &ldquo;{s}&rdquo;
        </li>
      ))}
    </ul>
  );
}

export function WaveCard({
  view,
  rank,
  accent,
  totalRequests,
  dominant,
  decisions,
  retired,
  onDecide,
}: {
  view: WaveView;
  rank: number;
  accent: string;
  totalRequests: number;
  dominant: boolean;
  decisions: Record<string, DJAction>;
  retired: ReadonlySet<string>;
  onDecide: (trackId: string, action: DJAction, waveId: string) => void;
}) {
  const { wave, candidates } = view;
  const [open, setOpen] = useState(false);
  const expanded = dominant || open;
  const share = waveShare(wave, totalRequests);
  const sharePct = Math.round(share * 100);
  // A decided card lingers just long enough to read the confirmation, then the
  // list closes over it — well before the socket echoes the same removal.
  const live = candidates.filter((c) => !retired.has(c.track.id));

  return (
    <section
      className="relative rounded-[1.25rem] border backdrop-blur-xl transition-colors duration-500"
      style={{
        borderColor: dominant ? tint(accent, 34) : "var(--color-ink-line)",
        background: dominant
          ? `linear-gradient(160deg, ${tint(accent, 9)}, color-mix(in oklab, var(--color-ink-card) 88%, transparent) 46%)`
          : "color-mix(in oklab, var(--color-ink-card) 84%, transparent)",
        boxShadow: dominant
          ? `0 30px 80px -50px ${accent}, inset 0 1px 0 0 ${tint(accent, 12)}`
          : "none",
      }}
      aria-label={`Wave ${rank + 1}: ${wave.label}`}
    >
      {/* Momentum ring — faster breath on a hotter wave. */}
      {dominant && (
        <span
          className="pointer-events-none absolute -inset-px rounded-[1.25rem] border animate-pulse-ring"
          style={{
            borderColor: tint(accent, 40),
            animationDuration: `${Math.max(1.1, 2.6 - Math.max(0, wave.momentum) * 1.4)}s`,
          }}
          aria-hidden="true"
        />
      )}

      <div className={dominant ? "p-6 xl:p-7" : "p-5"}>
        <div className="flex items-start justify-between gap-5">
          <div className="min-w-0">
            <div className="flex items-center gap-2.5">
              <span
                className="tnum inline-flex h-5 min-w-5 items-center justify-center rounded-md px-1 text-[11px] font-black"
                style={{ background: tint(accent, 20), color: accent }}
              >
                {rank + 1}
              </span>
              <Momentum momentum={wave.momentum} accent={accent} />
            </div>

            <h3
              className={`mt-2.5 font-semibold leading-tight tracking-[-0.02em] text-chalk ${
                dominant ? "text-[2rem] xl:text-[2.35rem]" : "text-xl"
              }`}
            >
              {wave.label}
            </h3>

            {wave.summary && (
              <p
                className={`mt-1.5 text-mist/80 ${dominant ? "text-sm" : "text-[13px]"}`}
              >
                {wave.summary}
              </p>
            )}
          </div>

          {/* Unique devices is the honest number, so it is the hero. */}
          <div className="shrink-0 text-right leading-none">
            <span
              className={`tnum block font-bold tracking-[-0.03em] ${
                dominant ? "text-[3.25rem] xl:text-[3.75rem]" : "text-[2rem]"
              }`}
              style={{ color: accent }}
            >
              {wave.unique_sessions}
            </span>
            <span
              className={`mt-1 block uppercase tracking-[0.2em] text-mist/70 ${
                dominant ? "text-[11px]" : "text-[10px]"
              }`}
            >
              people
            </span>
            <span className="tnum mt-2 block text-[11px] text-mist/55">
              {wave.raw_count} requests
            </span>
          </div>
        </div>

        {/* Share of the floor */}
        <div className="mt-5">
          <div className="flex items-baseline justify-between">
            <span className="text-[10px] uppercase tracking-[0.18em] text-mist/55">
              share of floor
            </span>
            <span className="tnum text-[13px] font-semibold" style={{ color: accent }}>
              {sharePct}%
            </span>
          </div>
          <div className="mt-1.5 h-1.5 w-full overflow-hidden rounded-full bg-white/[0.06]">
            <div
              className="h-full rounded-full transition-[width] duration-700 ease-out"
              style={{
                width: `${Math.max(2, sharePct)}%`,
                background: `linear-gradient(90deg, ${tint(accent, 55)}, ${accent})`,
              }}
            />
          </div>
        </div>

        {wave.top_keywords.length > 0 && (
          <div className="mt-4 flex flex-wrap gap-1.5">
            {wave.top_keywords.slice(0, dominant ? 6 : 4).map((k) => (
              <Chip key={k} accent={accent}>
                {k}
              </Chip>
            ))}
          </div>
        )}

        <div className="mt-4">
          <Overheard
            samples={wave.sample_texts}
            accent={accent}
            limit={dominant ? 3 : 2}
          />
        </div>

        {/* Recommendations */}
        {live.length > 0 && (
          <div className="mt-5 border-t border-ink-line/70 pt-5">
            {dominant ? (
              <div className="mb-3.5 flex items-center justify-between">
                <SectionLabel>Recommended · one tap to act</SectionLabel>
                <span className="tnum text-[11px] text-mist/55">
                  {live.length} picks
                </span>
              </div>
            ) : (
              <button
                type="button"
                onClick={() => setOpen((v) => !v)}
                aria-expanded={open}
                className="tap flex w-full items-center justify-between rounded-xl border border-ink-line bg-white/[0.02] px-4 text-left transition-colors hover:bg-white/[0.05] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-mist/60"
              >
                <span className="text-[12px] font-semibold uppercase tracking-[0.16em] text-mist">
                  {live.length} picks ready
                </span>
                <svg
                  viewBox="0 0 12 12"
                  className={`h-3 w-3 text-mist transition-transform duration-300 ${
                    open ? "rotate-180" : ""
                  }`}
                  fill="none"
                  aria-hidden="true"
                >
                  <path
                    d="M2.5 4.5L6 8l3.5-3.5"
                    stroke="currentColor"
                    strokeWidth="1.5"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              </button>
            )}

            {expanded && (
              <div className={`space-y-2.5 ${dominant ? "" : "mt-3"}`}>
                {live.map((c, i) => (
                  <CandidateCard
                    key={c.track.id}
                    candidate={c}
                    accent={accent}
                    rank={i + 1}
                    decision={decisions[c.track.id] ?? null}
                    onDecide={(action) => onDecide(c.track.id, action, wave.id)}
                  />
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </section>
  );
}
