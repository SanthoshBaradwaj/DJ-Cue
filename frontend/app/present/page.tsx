"use client";

/**
 * Presenter screen — projected on a venue TV/monitor so guests know how to
 * join. One job: get the room to scan, then make it visibly alive (live
 * request count, top requests climbing) so people believe it's working.
 */

import { useEffect, useState } from "react";
import { QRCodeSVG } from "qrcode.react";
import { api, connectDashboard } from "@/lib/api";
import type { DashboardState } from "@/lib/types";

const ACTIVE_EVENT_KEY = "cue_dj_active_event";

export default function PresentPage() {
  const [eventId, setEventId] = useState<string | null>(null);
  const [guestUrl, setGuestUrl] = useState<string>("");
  const [state, setState] = useState<DashboardState | null>(null);
  const [status, setStatus] = useState<"connecting" | "live" | "polling">("connecting");

  useEffect(() => {
    const fromUrl =
      typeof window !== "undefined"
        ? new URLSearchParams(window.location.search).get("event")
        : null;
    const stored =
      typeof window !== "undefined" ? window.localStorage.getItem(ACTIVE_EVENT_KEY) : null;
    const resolved = fromUrl || stored || undefined;
    api
      .config(resolved)
      .then((c) => {
        setEventId(c.event_id);
        setGuestUrl(c.guest_url);
      })
      .catch(() => {
        if (typeof window !== "undefined") {
          setGuestUrl(`${window.location.protocol}//${window.location.host}`);
        }
      });
  }, []);

  useEffect(() => {
    if (!eventId) return;
    return connectDashboard(eventId, { onState: setState, onStatus: setStatus });
  }, [eventId]);

  const stats = state?.stats;
  const top = (state?.requests ?? []).slice(0, 6);

  return (
    <main className="min-h-dvh p-8 lg:p-12 flex flex-col gap-8">
      <header className="flex items-center justify-between">
        <div className="flex items-baseline gap-4">
          <span className="text-3xl font-bold tracking-[-0.04em]">DJ-CUE</span>
          <span className="text-[var(--color-mist)] text-sm tracking-wide">
            Request the song you want to hear
          </span>
        </div>
        <span
          className="flex items-center gap-2 text-xs font-medium tracking-widest uppercase text-[var(--color-mist)]"
          aria-live="polite"
        >
          <span
            className="h-2 w-2 rounded-full"
            style={{
              background: status === "live" ? "var(--color-go)" : "var(--color-hold)",
              boxShadow: status === "live" ? "0 0 12px var(--color-go)" : "none",
            }}
          />
          {status === "live" ? "Live" : status}
        </span>
      </header>

      <div className="grid gap-10 lg:grid-cols-[auto_1fr] flex-1 min-h-0">
        <section className="flex flex-col items-center justify-center gap-6">
          <div className="rounded-3xl bg-white p-6 shadow-2xl">
            {guestUrl ? (
              <QRCodeSVG value={guestUrl} size={280} level="M" />
            ) : (
              <div className="h-[280px] w-[280px] animate-pulse rounded bg-neutral-200" />
            )}
          </div>
          <div className="text-center">
            <p className="text-2xl font-semibold">Scan. Pick a genre. Request a song.</p>
            <p className="mt-1 text-sm text-[var(--color-mist)]">Takes about five seconds.</p>
          </div>
        </section>

        <section className="flex flex-col justify-center gap-8">
          <div className="flex items-end gap-10">
            <div>
              <span className="tnum block text-[6rem] leading-none font-bold">
                {stats?.total_requests ?? 0}
              </span>
              <span className="mt-1 block text-sm uppercase tracking-[0.2em] text-[var(--color-mist)]">
                requests
              </span>
            </div>
            <div>
              <span
                className="tnum block text-[6rem] leading-none font-bold"
                style={{ color: "var(--color-cue-1)" }}
              >
                {stats?.unique_sessions ?? 0}
              </span>
              <span className="mt-1 block text-sm uppercase tracking-[0.2em] text-[var(--color-mist)]">
                phones in
              </span>
            </div>
          </div>

          <div>
            <div className="flex items-center gap-5 text-[var(--color-mist)]">
              <span className="h-px flex-1 bg-[var(--color-ink-line)]" />
              <span className="text-sm uppercase tracking-[0.2em]">Top requests right now</span>
              <span className="h-px flex-1 bg-[var(--color-ink-line)]" />
            </div>
            <ul className="mt-6 space-y-3">
              {top.map((r) => (
                <li key={r.id} className="flex items-center gap-4">
                  <span className="tnum w-10 shrink-0 text-right text-xl font-bold" style={{ color: "var(--color-cue-1)" }}>
                    {r.request_count}×
                  </span>
                  <span className="truncate text-lg font-medium">{r.song_title}</span>
                </li>
              ))}
              {top.length === 0 && (
                <li className="text-[var(--color-mist)]">Waiting for the first request…</li>
              )}
            </ul>
          </div>
        </section>
      </div>
    </main>
  );
}
