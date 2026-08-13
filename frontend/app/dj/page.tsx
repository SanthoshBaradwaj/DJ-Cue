"use client";

/**
 * DJ dashboard (M6) — the screen the DJ actually reads mid-set.
 *
 * This page is deliberately thin: every pixel lives in
 * `app/components/dj/*` and every byte of network lives in `useDashboardFeed`.
 * What remains here is the composition and the one piece of state neither of
 * those can own — the DJ's *just-tapped* intent.
 *
 * That last part matters more than it looks. A tap has to feel resolved
 * instantly, but the authoritative removal of a candidate only arrives on the
 * next `"state"` push. So a decision is recorded locally the moment it happens
 * (the card shows its confirmation), and the card is retired a beat later,
 * before the socket echoes the same removal. The DJ never sees a button that
 * appears to do nothing, and never sees a card flicker back.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "@/lib/api";
import type { DJAction, SlotProposal } from "@/lib/types";
import { AudioControl } from "../components/dj/AudioControl";
import { SetPanel } from "../components/dj/SetPanel";
import { RightRail } from "../components/dj/RightRail";
import { TopBar } from "../components/dj/TopBar";
import { WaveCard } from "../components/dj/WaveCard";
import { useAudioDeck } from "../components/dj/useAudioDeck";
import { waveAccent } from "../components/dj/theme";
import {
  readModeFromLocation,
  useDashboardFeed,
  type FeedMode,
} from "../components/dj/useDashboardFeed";
import { useFlipReorder } from "../components/dj/useFlipReorder";

const EVENT_ID = "default";

/** How long a decided card lingers on its confirmation before it folds away. */
const RETIRE_DELAY_MS = 1100;

const FALLBACK_ACCENT = "var(--color-cue-5)";

export default function DJDashboardPage() {
  // Resolved after mount, never during render: `?mock=1` exists on the client
  // only, and reading it in a state initialiser would desync hydration.
  const [mode, setMode] = useState<FeedMode>("live");
  useEffect(() => setMode(readModeFromLocation()), []);

  const { state, status, ticker, notice, decide } = useDashboardFeed(
    EVENT_ID,
    mode,
  );

  // trackId -> the action the DJ chose, shown as confirmation on the card.
  const [decisions, setDecisions] = useState<Record<string, DJAction>>({});
  // trackId -> folded away; the set the WaveCard subtracts from its candidates.
  const [retired, setRetired] = useState<ReadonlySet<string>>(
    () => new Set<string>(),
  );
  const timers = useRef<number[]>([]);

  useEffect(
    () => () => {
      timers.current.forEach(clearTimeout);
      timers.current = [];
    },
    [],
  );

  const onDecide = useCallback(
    (trackId: string, action: DJAction, waveId: string) => {
      // A double-tap on a 48px button under booth lighting is a near-certainty.
      // First tap wins; the rest are swallowed rather than queued.
      let first = false;
      setDecisions((prev) => {
        if (prev[trackId]) return prev;
        first = true;
        return { ...prev, [trackId]: action };
      });
      if (!first) return;

      void decide(trackId, action, waveId);
      timers.current.push(
        window.setTimeout(() => {
          setRetired((prev) => {
            const next = new Set(prev);
            next.add(trackId);
            return next;
          });
        }, RETIRE_DELAY_MS),
      );
    },
    [decide],
  );

  const waves = state?.waves ?? [];
  const nowPlaying = state?.dj.current_track ?? null;

  // Audio follows now-playing rather than the tap, so a decision made on
  // another device (or replayed from the store on reconnect) still fades the
  // room correctly.
  const deck = useAudioDeck(nowPlaying);

  // Insertion proposals are a separate read: they depend on the DJ's plan as
  // well as the waves, and they are cheap enough to refetch whenever the
  // dashboard changes rather than pushing a second thing down the socket.
  const [proposals, setProposals] = useState<SlotProposal[]>([]);
  const [tipTotals, setTipTotals] = useState<Record<string, number>>({});
  const [slotting, setSlotting] = useState<string | null>(null);
  const setlistSignature = (state?.dj.setlist ?? [])
    .map((e) => `${e.id}:${e.played_at ? 1 : 0}`)
    .join(",");
  const waveSignature = waves.map((v) => v.wave.id).join(",");

  const refreshProposals = useCallback(() => {
    if (mode !== "live") return;
    api
      .insertions(EVENT_ID)
      .then((r) => {
        setProposals(r.proposals);
        setTipTotals(r.tip_totals ?? {});
      })
      .catch(() => {
        // A failed proposal fetch must not disturb the board the DJ is reading.
      });
  }, [mode]);

  useEffect(refreshProposals, [refreshProposals, setlistSignature, waveSignature]);

  const onAcceptProposal = useCallback(
    (p: SlotProposal) => {
      setSlotting(p.track.id);
      api
        .acceptInsertion(p.track.id, p.position, p.wave_id, EVENT_ID)
        .catch(() => undefined)
        .finally(() => {
          setSlotting(null);
          refreshProposals();
        });
    },
    [refreshProposals],
  );

  const onAdvance = useCallback(() => {
    api
      .advanceSetlist(EVENT_ID)
      .catch(() => undefined)
      .finally(refreshProposals);
  }, [refreshProposals]);

  // Once the backend stops offering a track, our local memory of it is dead
  // weight. Pruning keeps both maps bounded across a long night.
  const liveTrackIds = useMemo(
    () => new Set(waves.flatMap((v) => v.candidates.map((c) => c.track.id))),
    [waves],
  );
  useEffect(() => {
    setDecisions((prev) => {
      const kept = Object.keys(prev).filter((id) => liveTrackIds.has(id));
      if (kept.length === Object.keys(prev).length) return prev;
      return Object.fromEntries(kept.map((id) => [id, prev[id]]));
    });
    setRetired((prev) => {
      const kept = [...prev].filter((id) => liveTrackIds.has(id));
      if (kept.length === prev.size) return prev;
      return new Set(kept);
    });
  }, [liveTrackIds]);

  // Rank decides colour, so a wave's accent follows it as it climbs — and the
  // ticker on the right can tint each raw request to match its wave card.
  const accents = useMemo(() => {
    const map = new Map<string, string>();
    waves.forEach((view, i) => map.set(view.wave.id, waveAccent(i)));
    return map;
  }, [waves]);

  const accentFor = useCallback(
    (waveId: string | null) =>
      (waveId ? accents.get(waveId) : undefined) ?? FALLBACK_ACCENT,
    [accents],
  );

  // Animate re-ranking only when the order actually changes, not on every push.
  const listRef = useRef<HTMLDivElement>(null);
  useFlipReorder(listRef, waves.map((v) => v.wave.id).join("|"));

  return (
    <main className="flex h-dvh flex-col overflow-hidden bg-ink text-chalk">
      {state && (
        <TopBar
          eventName={mode === "live" ? "Live event" : "Mock event"}
          stats={state.stats}
          status={status}
        />
      )}

      {notice && (
        <p
          role="status"
          className="shrink-0 border-b border-ink-line/80 bg-ink-raised/80 px-5 py-2.5 text-[13px] text-mist xl:px-8"
        >
          {notice}
        </p>
      )}

      <div className="flex min-h-0 flex-1 gap-5 overflow-hidden p-5 xl:gap-7 xl:p-7">
        {/* Waves — the column the DJ reads top-down. */}
        <div className="min-w-0 flex-1 overflow-y-auto">
          {waves.length > 0 ? (
            <div ref={listRef} className="flex flex-col gap-4 xl:gap-5">
              {waves.map((view, i) => (
                <div key={view.wave.id} data-flip-key={view.wave.id}>
                  <WaveCard
                    view={view}
                    rank={i}
                    accent={accentFor(view.wave.id)}
                    totalRequests={state?.stats.total_requests ?? 0}
                    dominant={i === 0}
                    decisions={decisions}
                    retired={retired}
                    onDecide={onDecide}
                  />
                </div>
              ))}
            </div>
          ) : (
            <WaitingForTheRoom connected={Boolean(state)} />
          )}
        </div>

        {/* Now playing, queue, and the raw requests as receipts. */}
        {state && (
          <aside className="hidden w-[21rem] shrink-0 flex-col gap-4 overflow-y-auto lg:flex xl:w-[23rem]">
            <div className="flex justify-end">
              <AudioControl deck={deck} trackTitle={nowPlaying?.title ?? null} />
            </div>
            {state.dj.setlist.length > 0 && (
              <SetPanel
                upcoming={state.dj.setlist.filter((e) => e.played_at === null)}
                proposals={proposals}
                tipTotals={tipTotals}
                onAccept={onAcceptProposal}
                onAdvance={onAdvance}
                busyTrackId={slotting}
              />
            )}
            <RightRail dj={state.dj} ticker={ticker} accentFor={accentFor} />
          </aside>
        )}
      </div>
    </main>
  );
}

/**
 * The pre-show state. It is on a projector-adjacent screen in a room that is
 * already filling up, so it reads as "ready and listening" rather than "empty".
 */
function WaitingForTheRoom({ connected }: { connected: boolean }) {
  return (
    <div className="flex h-full min-h-[24rem] items-center justify-center px-6">
      <div className="max-w-sm text-center">
        <span
          className="mx-auto mb-6 block h-2.5 w-2.5 rounded-full animate-pulse-ring"
          style={{ background: "var(--color-cue-1)" }}
          aria-hidden="true"
        />
        <h2 className="text-xl font-semibold tracking-[-0.02em] text-chalk">
          {connected ? "Listening for the room" : "Connecting to the floor"}
        </h2>
        <p className="mt-2.5 text-sm leading-relaxed text-mist/80">
          {connected
            ? "Crowd waves appear here the moment requests start landing. The first one to form becomes your headline card."
            : "Reaching the CUE backend. The dashboard fills in as soon as it answers."}
        </p>
      </div>
    </div>
  );
}
