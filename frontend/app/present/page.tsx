"use client";

/**
 * Presenter screen — projected during the pitch.
 *
 * One job: get the room to scan, then make the compression visible in real
 * time. Raw chaos scrolls down the right; the wave count on the left refuses
 * to grow past five. That contrast is the entire argument.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { QRCodeSVG } from "qrcode.react";
import { api, connectDashboard } from "@/lib/api";
import type { DashboardState, WSMessage } from "@/lib/types";

const WAVE_COLORS = [
  "var(--color-cue-1)",
  "var(--color-cue-2)",
  "var(--color-cue-3)",
  "var(--color-cue-4)",
  "var(--color-cue-5)",
];

interface TickerItem {
  id: number;
  text: string;
  wave: string;
}

export default function PresentPage() {
  const [state, setState] = useState<DashboardState | null>(null);
  const [guestUrl, setGuestUrl] = useState<string>("");
  const [status, setStatus] = useState<"connecting" | "live" | "polling">(
    "connecting",
  );
  const [ticker, setTicker] = useState<TickerItem[]>([]);
  const tickerId = useRef(0);

  useEffect(() => {
    api
      .config()
      .then((c) => setGuestUrl(c.guest_url))
      .catch(() => {
        if (typeof window !== "undefined") {
          setGuestUrl(`${window.location.protocol}//${window.location.host}`);
        }
      });
  }, []);

  const onMessage = useCallback((msg: WSMessage) => {
    if (msg.type !== "request") return;
    const text = String(msg.payload.text ?? "");
    const wave = String(msg.payload.wave_label ?? "");
    if (!text) return;
    tickerId.current += 1;
    const item = { id: tickerId.current, text, wave };
    setTicker((prev) => [item, ...prev].slice(0, 14));
  }, []);

  useEffect(
    () =>
      connectDashboard("default", {
        onState: setState,
        onMessage,
        onStatus: setStatus,
      }),
    [onMessage],
  );

  const stats = state?.stats;
  const waves = useMemo(() => state?.waves ?? [], [state]);
  const compression = stats?.compression_ratio ?? 0;

  return (
    <main className="min-h-dvh p-8 lg:p-12 flex flex-col gap-8">
      <header className="flex items-center justify-between">
        <div className="flex items-baseline gap-4">
          <span className="text-3xl font-bold tracking-[-0.04em]">CUE</span>
          <span className="text-[var(--color-mist)] text-sm tracking-wide">
            AI song request aggregator
          </span>
        </div>
        <span
          className="flex items-center gap-2 text-xs font-medium tracking-widest uppercase text-[var(--color-mist)]"
          aria-live="polite"
        >
          <span
            className="h-2 w-2 rounded-full"
            style={{
              background:
                status === "live" ? "var(--color-go)" : "var(--color-hold)",
              boxShadow:
                status === "live" ? "0 0 12px var(--color-go)" : "none",
            }}
          />
          {status === "live" ? "Live" : status}
        </span>
      </header>

      <div className="grid gap-8 lg:grid-cols-[auto_1fr_22rem] flex-1 min-h-0">
        {/* Scan target */}
        <section className="flex flex-col items-center justify-center gap-6">
          <div className="rounded-3xl bg-white p-6 shadow-2xl">
            {guestUrl ? (
              <QRCodeSVG value={guestUrl} size={280} level="M" />
            ) : (
              <div className="h-[280px] w-[280px] animate-pulse rounded bg-neutral-200" />
            )}
          </div>
          <div className="text-center">
            <p className="text-2xl font-semibold">Scan. Ask for anything.</p>
            <p className="mt-1 text-sm text-[var(--color-mist)]">
              Plain English, slang, or a vibe. No app, no signup.
            </p>
            <p className="mt-3 font-mono text-xs text-[var(--color-mist)]">
              {guestUrl}
            </p>
          </div>
        </section>

        {/* The thesis */}
        <section className="flex flex-col justify-center gap-10">
          <div>
            <p className="text-sm uppercase tracking-[0.2em] text-[var(--color-mist)]">
              The floor is saying
            </p>
            <div className="mt-3 flex items-end gap-6">
              <span className="tnum text-[7rem] leading-none font-bold">
                {stats?.total_requests ?? 0}
              </span>
              <span className="mb-4 text-xl text-[var(--color-mist)]">
                requests from{" "}
                <span className="tnum text-[var(--color-chalk)]">
                  {stats?.unique_sessions ?? 0}
                </span>{" "}
                people
              </span>
            </div>
          </div>

          <div className="flex items-center gap-5 text-[var(--color-mist)]">
            <span className="h-px flex-1 bg-[var(--color-ink-line)]" />
            <span className="text-sm uppercase tracking-[0.2em]">
              CUE hears
            </span>
            <span className="h-px flex-1 bg-[var(--color-ink-line)]" />
          </div>

          <div>
            <div className="flex items-end gap-6">
              <span
                className="tnum text-[7rem] leading-none font-bold"
                style={{ color: "var(--color-cue-1)" }}
              >
                {stats?.wave_count ?? 0}
              </span>
              <span className="mb-4 text-xl text-[var(--color-mist)]">
                crowd waves
                {compression > 0 && (
                  <span className="ml-3 rounded-full border border-[var(--color-ink-line)] px-3 py-1 text-sm text-[var(--color-chalk)]">
                    {Math.round(compression * 100)}% compressed
                  </span>
                )}
              </span>
            </div>

            <ul className="mt-6 space-y-3">
              {waves.map((view, i) => (
                <li key={view.wave.id} className="flex items-center gap-4">
                  <span
                    className="h-3 w-3 shrink-0 rounded-full"
                    style={{ background: WAVE_COLORS[i % WAVE_COLORS.length] }}
                  />
                  <span className="w-64 shrink-0 text-lg font-medium">
                    {view.wave.label}
                  </span>
                  <div className="h-2 flex-1 overflow-hidden rounded-full bg-[var(--color-ink-line)]">
                    <div
                      className="h-full rounded-full transition-all duration-700 ease-out"
                      style={{
                        width: `${Math.max(4, view.wave.share * 100)}%`,
                        background: WAVE_COLORS[i % WAVE_COLORS.length],
                      }}
                    />
                  </div>
                  <span className="tnum w-24 shrink-0 text-right text-sm text-[var(--color-mist)]">
                    {view.wave.unique_sessions} people
                  </span>
                </li>
              ))}
              {waves.length === 0 && (
                <li className="text-[var(--color-mist)]">
                  Waiting for the first request…
                </li>
              )}
            </ul>
          </div>
        </section>

        {/* Raw chaos */}
        <section className="card flex min-h-0 flex-col p-5">
          <h2 className="mb-4 text-xs font-semibold uppercase tracking-[0.2em] text-[var(--color-mist)]">
            Raw requests
          </h2>
          <ul className="flex-1 space-y-3 overflow-hidden">
            {ticker.map((item) => (
              <li
                key={item.id}
                className="animate-[slide-in_0.35s_cubic-bezier(0.16,1,0.3,1)]"
              >
                <p className="text-sm leading-snug">“{item.text}”</p>
                <p className="mt-0.5 text-[11px] uppercase tracking-wider text-[var(--color-mist)]">
                  → {item.wave}
                </p>
              </li>
            ))}
            {ticker.length === 0 && (
              <li className="text-sm text-[var(--color-mist)]">
                Requests appear here the moment they land.
              </li>
            )}
          </ul>
        </section>
      </div>
    </main>
  );
}
