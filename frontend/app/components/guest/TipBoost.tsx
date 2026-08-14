"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Track } from "@/lib/types";

/** Preset tip amounts in ₹, mapped to minor units (paise). */
const TIP_PRESETS = [
  { label: "₹50", minor: 5000 },
  { label: "₹100", minor: 10000 },
  { label: "₹200", minor: 20000 },
  { label: "₹500", minor: 50000 },
] as const;

type TipStatus = "idle" | "loading" | "sending" | "sent" | "error";

interface CandidateTrack {
  id: string;
  title: string;
  artist: string;
  bpm: number;
}

/**
 * "Boost your request" — Lets the guest select a specific song from their
 * requested wave/vibe and tip to boost it to the DJ.
 */
export default function TipBoost({
  waveId,
}: {
  waveId: string | null;
}) {
  const [status, setStatus] = useState<TipStatus>("loading");
  const [candidates, setCandidates] = useState<CandidateTrack[]>([]);
  const [selectedTrackId, setSelectedTrackId] = useState<string | null>(null);
  const [tippedAmount, setTippedAmount] = useState<number | null>(null);
  const [tippedTrack, setTippedTrack] = useState<CandidateTrack | null>(null);

  // Resolve all candidate tracks for this wave from the dashboard state.
  useEffect(() => {
    if (!waveId) {
      setStatus("idle");
      return;
    }
    let alive = true;
    api
      .dashboard()
      .then((dash) => {
        if (!alive) return;
        const view = dash.waves.find((w) => w.wave.id === waveId);
        const tracks = (view?.candidates ?? []).map((c) => ({
          id: c.track.id,
          title: c.track.title,
          artist: c.track.artist,
          bpm: c.track.bpm,
        }));
        if (tracks.length > 0) {
          setCandidates(tracks);
          setSelectedTrackId(tracks[0].id);
          setStatus("idle");
        } else {
          // Fallback: search catalog for tracks matching wave label
          const q = view?.wave.label || "";
          if (q) {
            api
              .search(q, 3)
              .then((res) => {
                if (!alive) return;
                const searchTracks = (res.tracks ?? []).map((t: Track) => ({
                  id: t.id,
                  title: t.title,
                  artist: t.artist,
                  bpm: t.bpm,
                }));
                if (searchTracks.length > 0) {
                  setCandidates(searchTracks);
                  setSelectedTrackId(searchTracks[0].id);
                }
                setStatus("idle");
              })
              .catch(() => {
                if (alive) setStatus("idle");
              });
          } else {
            setStatus("idle");
          }
        }
      })
      .catch(() => {
        if (alive) setStatus("idle");
      });
    return () => {
      alive = false;
    };
  }, [waveId]);

  const activeTrack = candidates.find((c) => c.id === selectedTrackId) ?? candidates[0] ?? null;

  const sendTip = useCallback(
    async (minor: number) => {
      if (!activeTrack || !waveId || status === "sending" || status === "sent") return;
      setStatus("sending");
      try {
        await api.createTip(activeTrack.id, minor, waveId);
        setTippedAmount(minor);
        setTippedTrack(activeTrack);
        setStatus("sent");
      } catch {
        setStatus("error");
        setTimeout(() => setStatus("idle"), 2500);
      }
    },
    [activeTrack, waveId, status],
  );

  if (status === "loading" || candidates.length === 0 || !waveId) return null;

  const sent = status === "sent";

  return (
    <section
      className="mt-6 rounded-2xl border border-ink-line/80 bg-ink-card/70 p-5 backdrop-blur-xl animate-rise"
      style={{
        borderColor: "color-mix(in oklab, var(--color-tip) 30%, var(--color-ink-line))",
        animationDelay: "240ms",
        animationFillMode: "backwards",
      }}
    >
      {sent && tippedTrack ? (
        /* ---- Success state ---- */
        <div className="flex flex-col items-center text-center py-2 animate-rise">
          <span
            className="flex h-11 w-11 items-center justify-center rounded-full shadow-[0_0_24px_-4px_rgba(216,201,163,0.6)]"
            style={{
              background: "color-mix(in oklab, var(--color-tip) 22%, transparent)",
              border: "1px solid var(--color-tip)",
            }}
          >
            <svg
              viewBox="0 0 24 24"
              className="h-5 w-5"
              fill="none"
              stroke="var(--color-tip)"
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
              <path d="M20 6 9 17l-5-5" />
            </svg>
          </span>
          <p className="mt-3.5 text-[16px] font-semibold text-chalk">
            Tipped{" "}
            <span style={{ color: "var(--color-tip)" }} className="font-bold">
              ₹{((tippedAmount ?? 0) / 100).toFixed(0)}
            </span>{" "}
            on {tippedTrack.title}
          </p>
          <p className="mt-1 text-[13px] text-mist/80">
            The DJ earns this only if {tippedTrack.title} actually plays.
          </p>
        </div>
      ) : (
        /* ---- Song selection + tip chips ---- */
        <div className="flex flex-col">
          <div className="flex items-center justify-between gap-2">
            <span className="text-[12px] font-bold uppercase tracking-[0.14em] text-mist/90">
              Boost with a tip
            </span>
            <span
              className="tnum text-[11px] font-medium"
              style={{ color: "var(--color-tip)" }}
            >
              Conditional payout
            </span>
          </div>

          <p className="mt-1.5 text-[13px] text-mist/75">
            Pick which song to boost to the top of the DJ&apos;s queue:
          </p>

          {/* Candidate songs list */}
          <div className="mt-3.5 flex flex-col gap-2">
            {candidates.map((c) => {
              const isSelected = c.id === activeTrack?.id;
              return (
                <button
                  key={c.id}
                  type="button"
                  onClick={() => setSelectedTrackId(c.id)}
                  className="tap flex items-center justify-between rounded-xl border px-3.5 py-2.5 text-left transition-all duration-150 active:scale-[0.985]"
                  style={{
                    borderColor: isSelected
                      ? "var(--color-tip)"
                      : "var(--color-ink-line)",
                    background: isSelected
                      ? "color-mix(in oklab, var(--color-tip) 12%, transparent)"
                      : "color-mix(in oklab, var(--color-ink-raised) 60%, transparent)",
                  }}
                >
                  <div className="min-w-0 flex-1 pr-2">
                    <p
                      className={`truncate text-[14px] font-semibold ${
                        isSelected ? "text-chalk" : "text-chalk/80"
                      }`}
                    >
                      {c.title}
                    </p>
                    <p className="truncate text-[12px] text-mist/70">
                      {c.artist}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="tnum text-[11px] text-mist/50">
                      {c.bpm} bpm
                    </span>
                    <span
                      className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-full border transition-colors ${
                        isSelected
                          ? "border-[var(--color-tip)] bg-[var(--color-tip)] text-ink"
                          : "border-ink-line bg-transparent"
                      }`}
                    >
                      {isSelected && (
                        <svg
                          viewBox="0 0 16 16"
                          className="h-3 w-3 fill-current"
                          aria-hidden="true"
                        >
                          <path d="M13.78 4.22a.75.75 0 0 1 0 1.06l-7.25 7.25a.75.75 0 0 1-1.06 0L2.22 9.28a.751.751 0 0 1 .018-1.042.751.751 0 0 1 1.042-.018L6 10.94l6.72-6.72a.75.75 0 0 1 1.06 0Z" />
                        </svg>
                      )}
                    </span>
                  </div>
                </button>
              );
            })}
          </div>

          {/* Tip amounts */}
          <div className="mt-4 pt-3 border-t border-ink-line/60">
            <div className="flex items-center justify-between mb-2.5">
              <span className="text-[12px] font-medium text-mist">
                Select tip amount:
              </span>
              {activeTrack && (
                <span className="truncate text-[12px] font-semibold text-chalk/90 max-w-[14rem]">
                  for {activeTrack.title}
                </span>
              )}
            </div>

            <div className="grid grid-cols-4 gap-2">
              {TIP_PRESETS.map((preset) => (
                <button
                  key={preset.minor}
                  type="button"
                  disabled={status === "sending"}
                  onClick={() => sendTip(preset.minor)}
                  className="tap flex h-12 items-center justify-center rounded-xl border text-[15px] font-bold transition-all duration-150 active:scale-[0.95] disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-ink"
                  style={{
                    borderColor:
                      "color-mix(in oklab, var(--color-tip) 45%, transparent)",
                    background:
                      "color-mix(in oklab, var(--color-tip) 10%, transparent)",
                    color: "var(--color-tip)",
                    ["--tw-ring-color" as string]: "var(--color-tip)",
                  }}
                >
                  {status === "sending" ? (
                    <span className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
                  ) : (
                    preset.label
                  )}
                </button>
              ))}
            </div>

            {status === "error" && (
              <p className="mt-2 text-center text-[12px] text-hold animate-rise">
                Couldn&apos;t send tip — please try again.
              </p>
            )}

            <p className="mt-2.5 text-center text-[11px] text-mist/60">
              Only charged if the DJ plays your chosen song.
            </p>
          </div>
        </div>
      )}
    </section>
  );
}
