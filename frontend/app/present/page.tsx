"use client";

/**
 * Presenter screen — projected on a venue TV/monitor so guests know how to
 * join. One job: get the room to scan, then make it visibly alive (live
 * request count, top requests climbing) so people believe it's working.
 */

import { useEffect, useState } from "react";
import { QRCodeSVG } from "qrcode.react";
import { api, connectDashboard } from "@/lib/api";
import type { DashboardState, FlushAck } from "@/lib/types";
import { PulseBar } from "../components/shared/PulseBar";
import { PinGate } from "../components/shared/PinGate";
import { ResetConfirmModal } from "../components/present/ResetConfirmModal";

const ACTIVE_EVENT_KEY = "cue_dj_active_event";
// Separate from ACTIVE_EVENT_KEY on purpose -- /dj's event choice is a
// different concern from /present's own dev/prod lens, and this key is
// sessionStorage (resets when the screen's browser is closed) so a TV left
// in dev mode overnight doesn't silently stay there for the next event.
const ENV_KEY = "cue_present_env";
type Env = "prod" | "dev";

export default function PresentPage() {
  return (
    <PinGate role="present">
      <Present />
    </PinGate>
  );
}

function Present() {
  const [env, setEnv] = useState<Env>("prod");
  const [eventId, setEventId] = useState<string | null>(null);
  const [eventName, setEventName] = useState<string>("");
  const [guestUrl, setGuestUrl] = useState<string>("");
  const [state, setState] = useState<DashboardState | null>(null);
  const [status, setStatus] = useState<"connecting" | "live" | "polling">("connecting");
  const [showReset, setShowReset] = useState(false);
  const [flushToast, setFlushToast] = useState<FlushAck | null>(null);
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
    const stored =
      typeof window !== "undefined" ? window.sessionStorage.getItem(ENV_KEY) : null;
    if (stored === "dev") setEnv("dev");
  }, []);

  useEffect(() => {
    if (typeof window !== "undefined") window.sessionStorage.setItem(ENV_KEY, env);
  }, [env]);

  useEffect(() => {
    let alive = true;
    const resolveTarget = async (): Promise<string | undefined> => {
      if (env === "dev") {
        const devEvent = await api.events.getDev();
        return devEvent.id;
      }
      const fromUrl =
        typeof window !== "undefined"
          ? new URLSearchParams(window.location.search).get("event")
          : null;
      const stored =
        typeof window !== "undefined" ? window.localStorage.getItem(ACTIVE_EVENT_KEY) : null;
      return fromUrl || stored || undefined;
    };
    resolveTarget()
      .then((resolved) => api.config(resolved))
      .then((c) => {
        if (!alive) return;
        setEventId(c.event_id);
        setGuestUrl(c.guest_url);
      })
      .catch(() => {
        if (!alive) return;
        setEventId(null);
        if (typeof window !== "undefined") {
          setGuestUrl(`${window.location.protocol}//${window.location.host}`);
        }
      });
    return () => {
      alive = false;
    };
  }, [env]);

  useEffect(() => {
    if (!eventId) return;
    return connectDashboard(eventId, { onState: setState, onStatus: setStatus });
  }, [eventId]);

  useEffect(() => {
    api.events
      .list()
      .then(({ events }) => {
        const match = events.find((e) => e.id === eventId);
        setEventName(match?.name ?? (env === "dev" ? "Dev/Test" : ""));
      })
      .catch(() => undefined);
  }, [eventId, env]);

  useEffect(() => {
    if (!flushToast) return;
    const timer = setTimeout(() => setFlushToast(null), 5000);
    return () => clearTimeout(timer);
  }, [flushToast]);

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

        <div className="flex items-center gap-3">
          {/* Operator-only controls: which event this screen is pointed at,
              and the reset button. Small and out of the way -- this row is
              for whoever's running the laptop, not the room. */}
          <div
            role="group"
            aria-label="Environment"
            className="flex items-center gap-0.5 rounded-full border border-[var(--color-ink-line)] bg-[var(--color-ink-raised)] p-0.5 text-[11px] font-bold uppercase tracking-[0.08em]"
          >
            <button
              type="button"
              onClick={() => setEnv("prod")}
              aria-pressed={env === "prod"}
              className="rounded-full px-2.5 py-1 transition-colors"
              style={
                env === "prod"
                  ? { background: "var(--color-go)", color: "var(--color-ink)" }
                  : { color: "var(--color-mist)" }
              }
            >
              Live
            </button>
            <button
              type="button"
              onClick={() => setEnv("dev")}
              aria-pressed={env === "dev"}
              className="rounded-full px-2.5 py-1 transition-colors"
              style={
                env === "dev"
                  ? { background: "var(--color-hold)", color: "var(--color-ink)" }
                  : { color: "var(--color-mist)" }
              }
            >
              Dev
            </button>
          </div>

          <button
            type="button"
            onClick={() => setShowReset(true)}
            disabled={!eventId}
            className="tap rounded-full border border-[var(--color-ink-line)] px-3 py-1.5 text-[11px] font-bold uppercase tracking-[0.08em] text-[var(--color-danger)] transition-colors active:bg-[var(--color-danger)]/10 disabled:opacity-40"
          >
            Reset
          </button>

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
        </div>
      </header>

      {flushToast && (
        <p
          role="status"
          className="rounded-2xl border border-[var(--color-ink-line)] bg-[var(--color-ink-raised)] px-4 py-2.5 text-sm text-[var(--color-mist)]"
        >
          Reset done — cleared {flushToast.requests_removed} song
          {flushToast.requests_removed === 1 ? "" : "s"}, {flushToast.taps_removed} user
          {flushToast.taps_removed === 1 ? "" : "s"}.
        </p>
      )}

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

      {showReset && eventId && (
        <ResetConfirmModal
          eventId={eventId}
          eventLabel={eventName || (env === "dev" ? "Dev/Test" : "this event")}
          isDev={env === "dev"}
          onClose={() => setShowReset(false)}
          onDone={(ack) => {
            setShowReset(false);
            setFlushToast(ack);
          }}
        />
      )}
    </main>
  );
}
