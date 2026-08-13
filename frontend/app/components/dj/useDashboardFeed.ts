"use client";

// The single place the dashboard talks to the outside world.
//
// Live mode delegates entirely to connectDashboard()/api.decide() from
// lib/api.ts — the socket, the backoff and the polling fallback all live there.
// Mock mode never touches the network; it replays a local fixture so the screen
// can be designed and demoed before M4 lands.

import { useCallback, useEffect, useRef, useState } from "react";
import { api, connectDashboard } from "@/lib/api";
import type { DashboardState, DJAction, WaveView } from "@/lib/types";
import { mockEmptyState, mockState, MOCK_INCOMING } from "./mock";

export type FeedStatus = "connecting" | "live" | "polling";
export type FeedMode = "live" | "mock" | "mock-empty";

export interface TickerItem {
  key: string;
  text: string;
  waveId: string | null;
  waveLabel: string;
  at: number;
}

const TICKER_CAP = 12;

export function readModeFromLocation(): FeedMode {
  if (typeof window === "undefined") return "live";
  const mock = new URLSearchParams(window.location.search).get("mock");
  if (!mock) return "live";
  return mock === "empty" ? "mock-empty" : "mock";
}

/** Newest first, capped so the ticker never grows unbounded on a long night. */
function pushTicker(list: TickerItem[], item: TickerItem): TickerItem[] {
  return [item, ...list].slice(0, TICKER_CAP);
}

/** Re-derive share + ordering after a simulated request lands. */
function resortWaves(waves: WaveView[], total: number): WaveView[] {
  return waves
    .map((w) => ({
      ...w,
      wave: { ...w.wave, share: total > 0 ? w.wave.raw_count / total : 0 },
    }))
    .sort((a, b) => b.wave.unique_sessions - a.wave.unique_sessions);
}

export function useDashboardFeed(eventId: string, mode: FeedMode) {
  const [state, setState] = useState<DashboardState | null>(null);
  const [status, setStatus] = useState<FeedStatus>("connecting");
  const [ticker, setTicker] = useState<TickerItem[]>([]);
  const [notice, setNotice] = useState<string | null>(null);
  const keySeq = useRef(0);
  const nextKey = () => `tick_${(keySeq.current += 1)}`;

  // ---- mock ---------------------------------------------------------------
  useEffect(() => {
    if (mode === "live") return;
    if (mode === "mock-empty") {
      setState(mockEmptyState());
      setStatus("live");
      return;
    }

    setState(mockState());
    setStatus("live");

    let i = Math.floor(Math.random() * MOCK_INCOMING.length);
    const timer = setInterval(() => {
      const incoming = MOCK_INCOMING[i % MOCK_INCOMING.length];
      i += 1;
      const newDevice = Math.random() < 0.55;

      setTicker((prev) =>
        pushTicker(prev, {
          key: nextKey(),
          text: incoming.text,
          waveId: incoming.wave_id,
          waveLabel: incoming.wave_label,
          at: Date.now(),
        }),
      );

      setState((prev) => {
        if (!prev) return prev;
        const total = prev.stats.total_requests + 1;
        const waves = prev.waves.map((w) =>
          w.wave.id === incoming.wave_id
            ? {
                ...w,
                wave: {
                  ...w.wave,
                  raw_count: w.wave.raw_count + 1,
                  unique_sessions: w.wave.unique_sessions + (newDevice ? 1 : 0),
                  momentum: Math.min(1, w.wave.momentum + 0.09),
                  updated_at: Date.now() / 1000,
                },
              }
            : {
                ...w,
                wave: { ...w.wave, momentum: Math.max(-1, w.wave.momentum - 0.03) },
              },
        );
        return {
          ...prev,
          waves: resortWaves(waves, total),
          stats: {
            ...prev.stats,
            total_requests: total,
            unique_sessions: prev.stats.unique_sessions + (newDevice ? 1 : 0),
            compression_ratio: prev.stats.wave_count / total,
            avg_interpret_ms: Math.round(
              prev.stats.avg_interpret_ms * 0.85 + (260 + Math.random() * 180) * 0.15,
            ),
          },
        };
      });
    }, 2600);

    return () => clearInterval(timer);
  }, [mode]);

  // ---- live ---------------------------------------------------------------
  useEffect(() => {
    if (mode !== "live") return;
    const stop = connectDashboard(eventId, {
      onState: (s) => {
        setState(s);
        setNotice(null);
      },
      onStatus: setStatus,
      onMessage: (msg) => {
        if (msg.type !== "request") return;
        const p = msg.payload as {
          text?: unknown;
          wave_id?: unknown;
          wave_label?: unknown;
        };
        if (typeof p.text !== "string") return;
        setTicker((prev) =>
          pushTicker(prev, {
            key: nextKey(),
            text: p.text as string,
            waveId: typeof p.wave_id === "string" ? p.wave_id : null,
            waveLabel: typeof p.wave_label === "string" ? p.wave_label : "New wave",
            at: (msg.ts ?? Date.now() / 1000) * 1000,
          }),
        );
      },
    });
    return stop;
  }, [eventId, mode]);

  // A dead backend must read as a quiet inline notice, never a blank stage.
  useEffect(() => {
    if (mode !== "live" || state) return;
    const t = setTimeout(
      () =>
        setNotice(
          "No response from the CUE backend yet — retrying. The dashboard will fill in the moment it answers.",
        ),
      4000,
    );
    return () => clearTimeout(t);
  }, [mode, state]);

  /**
   * Optimism lives in the caller; this only performs the write. In mock mode
   * the write is applied to the local fixture so PLAY/LATER/SKIP still feel
   * real without a server.
   */
  const decide = useCallback(
    async (trackId: string, action: DJAction, waveId: string | null) => {
      if (mode !== "live") {
        setState((prev) => {
          if (!prev) return prev;
          const found = prev.waves
            .flatMap((w) => w.candidates)
            .find((c) => c.track.id === trackId);
          if (!found) return prev;
          const waves = prev.waves.map((w) => ({
            ...w,
            candidates: w.candidates.filter((c) => c.track.id !== trackId),
          }));
          const dj = { ...prev.dj };
          if (action === "play") {
            if (dj.current_track) dj.history = [dj.current_track, ...dj.history].slice(0, 12);
            dj.current_track = found.track;
            dj.started_at = Date.now() / 1000;
          } else if (action === "later") {
            dj.queue = [...dj.queue, found.track];
          }
          return {
            ...prev,
            waves,
            dj,
            stats: { ...prev.stats, decisions_made: prev.stats.decisions_made + 1 },
          };
        });
        return;
      }
      try {
        await api.decide(trackId, action, waveId);
      } catch {
        setNotice("That decision did not reach the backend. Tap again when the connection returns.");
      }
    },
    [mode],
  );

  return { state, status, ticker, notice, decide };
}
