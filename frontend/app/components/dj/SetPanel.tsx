"use client";

/**
 * The DJ's planned set, with the crowd's requests slotted into it.
 *
 * This is the surface that makes CUE setlist-aware rather than a recommender.
 * Two rules shape it:
 *
 * 1. **His plan is the spine.** The set reads top-to-bottom exactly as he
 *    wrote it. Crowd inserts appear *between* his tracks, marked, never
 *    reordering or replacing what he chose.
 * 2. **We place, he mixes.** The two-sided fit is shown as a small BPM delta on
 *    each edge and nothing more. CUE is not going to tell a working DJ how to
 *    blend two records — he is the one orchestrating it, and a confident-looking
 *    "transition score" would be both patronising and often wrong.
 */

import { useState } from "react";
import type { SetlistEntry, SlotProposal } from "@/lib/types";

/** Paise -> "₹200". Money never renders as a float. */
function rupees(minor: number): string {
  const whole = minor / 100;
  return `₹${whole % 1 === 0 ? whole.toFixed(0) : whole.toFixed(2)}`;
}

/** "00:57:10" -> "0:57" — the DJ reads set position, not seconds. */
function shortCue(cue: string | null): string | null {
  if (!cue) return null;
  const parts = cue.split(":");
  if (parts.length < 2) return cue;
  const [h, m] = parts;
  return `${parseInt(h, 10)}:${m}`;
}

function BpmEdge({ delta, label }: { delta: number | null; label: string }) {
  if (delta === null) return null;
  const sign = delta > 0 ? "+" : "";
  // Colour only past the point where a DJ would have to actually work for it.
  const strain = Math.abs(delta) >= 12;
  return (
    <span
      className="tnum text-[11px]"
      style={{ color: strain ? "var(--color-cue-1)" : "var(--color-mist)" }}
      title={`${sign}${delta} BPM ${label}`}
    >
      {sign}
      {delta}
    </span>
  );
}

export function SetPanel({
  upcoming,
  proposals,
  tipTotals,
  onAccept,
  onAdvance,
  busyTrackId,
}: {
  upcoming: SetlistEntry[];
  proposals: SlotProposal[];
  tipTotals: Record<string, number>;
  onAccept: (p: SlotProposal) => void;
  onAdvance: () => void;
  busyTrackId: string | null;
}) {
  const [open, setOpen] = useState(true);

  if (upcoming.length === 0) {
    return (
      <section className="rounded-xl border border-ink-line bg-ink-card/60 p-5">
        <h3 className="text-sm font-semibold tracking-[-0.01em] text-chalk">
          No set loaded
        </h3>
        <p className="mt-1.5 text-[13px] leading-relaxed text-mist/80">
          Import the DJ&apos;s planned set and crowd requests get slotted into it
          instead of listed loose. Without a plan, CUE falls back to plain
          recommendations.
        </p>
      </section>
    );
  }

  // Group proposals by the slot they want, so each gap shows its contenders.
  const byPosition = new Map<number, SlotProposal[]>();
  for (const p of proposals) {
    const list = byPosition.get(p.position) ?? [];
    list.push(p);
    byPosition.set(p.position, list);
  }

  const pending = tipTotals.pending ?? 0;
  const captured = tipTotals.captured ?? 0;

  return (
    <section className="rounded-xl border border-ink-line bg-ink-card/60">
      <header className="flex items-center justify-between gap-3 border-b border-ink-line/70 px-4 py-3">
        <div className="flex items-baseline gap-2.5">
          <h3 className="text-sm font-semibold tracking-[-0.01em] text-chalk">
            The Set
          </h3>
          <span className="tnum text-[11px] text-mist/70">
            {upcoming.length} ahead
          </span>
        </div>

        <div className="flex items-center gap-3">
          {(pending > 0 || captured > 0) && (
            <span
              className="tnum text-[11px]"
              style={{ color: "var(--color-tip)" }}
              title="Pending tips are only charged if the song plays"
            >
              {rupees(pending)} pending
              {captured > 0 && ` · ${rupees(captured)} earned`}
            </span>
          )}
          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            className="text-[11px] uppercase tracking-[0.14em] text-mist transition-colors hover:text-chalk"
          >
            {open ? "Hide" : "Show"}
          </button>
        </div>
      </header>

      {open && (
        <ol className="divide-y divide-ink-line/50">
          {upcoming.map((entry, index) => {
            const contenders = byPosition.get(index) ?? [];
            return (
              <li key={entry.id}>
                {/* Any crowd request wanting this gap sits above the track it
                    would precede — the reading order matches the play order. */}
                {contenders.map((p) => (
                  <ProposalRow
                    key={`${p.track.id}-${p.position}`}
                    proposal={p}
                    onAccept={onAccept}
                    busy={busyTrackId === p.track.id}
                  />
                ))}

                <div className="flex items-center gap-3 px-4 py-2.5">
                  <span className="tnum w-10 shrink-0 text-[11px] text-mist/50">
                    {shortCue(entry.cue_time) ?? index + 1}
                  </span>
                  <span
                    className="h-1 w-1 shrink-0 rounded-full"
                    style={{
                      background: entry.inserted_from_wave_id
                        ? "var(--color-go)"
                        : "var(--color-ink-line)",
                    }}
                    aria-hidden="true"
                  />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-[13px] text-chalk/90">
                      {entry.track.title}
                    </p>
                    <p className="truncate text-[11px] text-mist/60">
                      {entry.track.artist}
                    </p>
                  </div>
                  {entry.inserted_from_wave_id && (
                    <span
                      className="shrink-0 text-[10px] uppercase tracking-[0.12em]"
                      style={{ color: "var(--color-go)" }}
                    >
                      crowd
                    </span>
                  )}
                  <span className="tnum shrink-0 text-[11px] text-mist/60">
                    {entry.track.bpm}
                  </span>
                </div>

                {index === 0 && (
                  <div className="px-4 pb-3">
                    <button
                      type="button"
                      onClick={onAdvance}
                      className="h-9 w-full rounded-lg border border-ink-line text-[11px] font-semibold uppercase tracking-[0.14em] text-mist transition-colors hover:border-mist/40 hover:text-chalk"
                    >
                      Mark played · move on
                    </button>
                  </div>
                )}
              </li>
            );
          })}

          {/* Requests that want the tail of the set. */}
          {(byPosition.get(upcoming.length) ?? []).map((p) => (
            <li key={`tail-${p.track.id}`}>
              <ProposalRow
                proposal={p}
                onAccept={onAccept}
                busy={busyTrackId === p.track.id}
              />
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}

function ProposalRow({
  proposal,
  onAccept,
  busy,
}: {
  proposal: SlotProposal;
  onAccept: (p: SlotProposal) => void;
  busy: boolean;
}) {
  const tipped = proposal.tip_minor > 0;

  return (
    <div
      className="flex items-start gap-3 px-4 py-2.5"
      style={{
        // A dotted left edge reads as "proposed", not "scheduled" — the DJ can
        // tell at a glance what he has actually committed to.
        borderLeft: "2px dotted var(--color-cue-2)",
        background: "color-mix(in oklab, var(--color-cue-2) 5%, transparent)",
      }}
    >
      <span className="w-10 shrink-0 pt-0.5 text-[10px] uppercase tracking-[0.1em] text-mist/50">
        here
      </span>

      <div className="min-w-0 flex-1">
        <div className="flex items-baseline gap-2">
          <p className="truncate text-[13px] font-medium text-chalk">
            {proposal.track.title}
          </p>
          <BpmEdge delta={proposal.bpm_delta_out} label="out" />
          <span className="text-[10px] text-mist/40">/</span>
          <BpmEdge delta={proposal.bpm_delta_in} label="in" />
        </div>

        <p className="mt-0.5 truncate text-[11px] text-mist/70">
          {proposal.wave_label} · {proposal.track.artist}
        </p>

        {proposal.reasons.length > 0 && (
          <p className="mt-1 text-[11px] leading-snug text-mist/60">
            {proposal.reasons.slice(0, 2).join(" · ")}
          </p>
        )}

        {tipped && (
          <p className="mt-1 text-[11px]" style={{ color: "var(--color-tip)" }}>
            {rupees(proposal.tip_minor)} riding on it
            {proposal.tip_broke_tie && " — broke a tie"}
            <span className="text-mist/50"> · only charged if you play it</span>
          </p>
        )}
      </div>

      <button
        type="button"
        onClick={() => onAccept(proposal)}
        disabled={busy}
        className="h-11 shrink-0 rounded-lg px-3.5 text-[11px] font-semibold uppercase tracking-[0.12em] transition-opacity disabled:opacity-40"
        style={{ background: "var(--color-go)", color: "var(--color-ink)" }}
      >
        {busy ? "…" : "Slot in"}
      </button>
    </div>
  );
}
