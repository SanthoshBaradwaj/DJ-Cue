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
import { PulseBar } from "../components/shared/PulseBar";

const ACTIVE_EVENT_KEY = "cue_dj_active_event";

export default function PresentPage() {
  const [eventId, setEventId] = useState<string | null>(null);
  const [guestUrl, setGuestUrl] = useState<string>("");
  const [state, setState] = useState<DashboardState | null>(null);
  const [status, setStatus] = useState<"connecting" | "live" | "polling">("connecting");
  // This screen is meant for a projected TV/monitor, but it's reachable on
  // a phone too (someone previewing it, or sharing the link) -- a fixed
  // 280px QR plus its own padding doesn't fit a narrow phone width at all.
  const [qrSize, setQrSize] = useState(280);

  useEffect(() => {
    const update = () => setQrSize(window.innerWidth < 640 ? 200 : 280);
    update();
    window.addEventListener("resize", update);
    return () => window.removeEventListener("resize", update);
  }, []);

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
  // Full ranked queue, not a top-N slice -- the stat above already tells
  // guests how many requests exist, so a list that quietly drops the rest
  // reads as a bug, not curation. The page already scrolls (min-h-dvh, no
  // overflow trap), so there's nothing else to change to make this reachable.
  const top = state?.requests ?? [];

  return (
    <main className="min-h-dvh p-5 sm:p-8 lg:p-12 flex flex-col gap-6 sm:gap-8 overflow-x-hidden">
      <header className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-baseline gap-4">
          <span className="text-2xl sm:text-3xl font-bold tracking-[-0.04em]">DJ-CUE</span>
          <span className="hidden sm:inline text-[var(--color-mist)] text-sm tracking-wide">
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

      <div className="grid gap-8 sm:gap-10 lg:grid-cols-[auto_1fr] flex-1 min-h-0">
        <section className="flex flex-col items-center justify-center gap-5 sm:gap-6">
          <div className="rounded-3xl bg-white p-4 sm:p-6 shadow-2xl">
            {guestUrl ? (
              <QRCodeSVG value={guestUrl} size={qrSize} level="M" />
            ) : (
              <div
                className="animate-pulse rounded bg-neutral-200"
                style={{ width: qrSize, height: qrSize }}
              />
            )}
          </div>
          <div className="text-center">
            <p className="text-xl sm:text-2xl font-semibold">Scan. Pick a genre. Request a song.</p>
            <p className="mt-1 text-sm text-[var(--color-mist)]">Takes about five seconds.</p>
          </div>
        </section>

        <section className="flex flex-col justify-center gap-6 sm:gap-8 min-w-0">
          <div className="flex flex-wrap items-end gap-6 sm:gap-10">
            <div>
              <span className="tnum block text-[3.25rem] sm:text-[4.5rem] lg:text-[6rem] leading-none font-bold">
                {stats?.total_requests ?? 0}
              </span>
              <span className="mt-1 block text-sm uppercase tracking-[0.2em] text-[var(--color-mist)]">
                requests
              </span>
            </div>
            <div>
              <span
                className="tnum block text-[3.25rem] sm:text-[4.5rem] lg:text-[6rem] leading-none font-bold"
                style={{ color: "var(--color-cue-1)" }}
              >
                {stats?.unique_sessions ?? 0}
              </span>
              <span className="mt-1 block text-sm whitespace-nowrap uppercase tracking-[0.2em] text-[var(--color-mist)]">
                active users
              </span>
            </div>
            {stats && stats.pulse_total > 0 && (
              <PulseBar single={stats.pulse_single} committed={stats.pulse_committed} size="lg" />
            )}
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
                  {r.artwork_url ? (
                    // eslint-disable-next-line @next/next/no-img-element -- arbitrary remote CDN host, not worth next/image config
                    <img
                      src={r.artwork_url}
                      alt=""
                      width={40}
                      height={40}
                      className="h-10 w-10 shrink-0 rounded-lg object-cover"
                    />
                  ) : (
                    <span className="h-10 w-10 shrink-0 rounded-lg bg-[var(--color-ink-line)]" aria-hidden="true" />
                  )}
                  <span className="min-w-0 flex-1 truncate text-lg font-medium">{r.song_title}</span>
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
