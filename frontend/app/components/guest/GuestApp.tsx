"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import type { DJStatus, PulseStatus, RequestAck } from "@/lib/types";
import Confirmation from "./Confirmation";
import GenreGrid from "./GenreGrid";
import SongSearch from "./SongSearch";

type Step = "genre" | "song" | "confirm";

function friendlyError(): string {
  if (typeof navigator !== "undefined" && navigator.onLine === false) {
    return "You're offline — the venue Wi-Fi dipped. Try again in a second.";
  }
  return "Couldn't reach the DJ just then. Try again in a second.";
}

/**
 * The whole guest surface: genre grid -> song search -> confirmation.
 *
 * Everything here is client-side so a QR scan paints before the guest's
 * thumb reaches the screen. The event id comes from the QR's own URL
 * (`?event=`) when present, and otherwise resolves to whichever event the DJ
 * most recently started.
 */
export default function GuestApp() {
  const [eventId, setEventId] = useState<string | null>(null);
  const [step, setStep] = useState<Step>("genre");
  const [genre, setGenre] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [ack, setAck] = useState<RequestAck | null>(null);
  const [djStatus, setDjStatus] = useState<DJStatus | undefined>(undefined);
  const [pulse, setPulse] = useState<PulseStatus | null>(null);
  const [pulseLimited, setPulseLimited] = useState(false);
  const [pulsePending, setPulsePending] = useState(false);

  const eventIdRef = useRef(eventId);
  useEffect(() => {
    eventIdRef.current = eventId;
  }, [eventId]);

  // How often to re-check dj_status while the app is open. The DJ flipping
  // open<->closed must reach a phone that already has this page open --
  // without this, a guest sees a stale "taking requests" (or is stuck on
  // the closed screen after the DJ reopens) until they manually reload.
  const STATUS_POLL_MS = 4000;

  useEffect(() => {
    let alive = true;
    const fromUrl =
      typeof window !== "undefined"
        ? new URLSearchParams(window.location.search).get("event")
        : null;

    const refreshStatus = (idHint?: string | null) => {
      api
        .config(idHint ?? fromUrl ?? undefined)
        .then((cfg) => {
          if (!alive) return;
          setEventId(cfg.event_id);
          setDjStatus(cfg.dj_status);
        })
        .catch(() => {
          if (fromUrl && alive) setEventId((prev) => prev ?? fromUrl);
          /* dj status stays whatever it last was; next poll tick retries */
        });
    };

    refreshStatus();
    const timer = setInterval(() => refreshStatus(eventIdRef.current), STATUS_POLL_MS);
    return () => {
      alive = false;
      clearInterval(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- eventIdRef sidesteps re-subscribing the interval on every id change
  }, []);

  const pickGenre = useCallback((key: string) => {
    setGenre(key);
    setError(null);
    setStep("song");
  }, []);

  const changePulse = useCallback(
    (status: PulseStatus) => {
      if (!eventId || pulsePending || pulseLimited) return;
      setPulsePending(true);
      api.events
        .setPulse(eventId, status)
        .then((ack) => {
          if (ack.limited) {
            setPulseLimited(true);
            return;
          }
          if (ack.status) setPulse(ack.status);
        })
        .catch(() => undefined)
        .finally(() => setPulsePending(false));
    },
    [eventId, pulsePending, pulseLimited],
  );

  const submit = useCallback(
    async (song: {
      title: string;
      artist?: string;
      songId?: string | null;
      artworkUrl?: string | null;
      album?: string | null;
      popularity?: number | null;
    }) => {
      if (pending || !genre) return;
      setPending(true);
      setError(null);
      try {
        let resolvedEventId = eventId;
        if (!resolvedEventId) {
          const cfg = await api.config();
          resolvedEventId = cfg.event_id;
          setEventId(resolvedEventId);
        }
        const res = await api.submitRequest({
          eventId: resolvedEventId,
          genre,
          songTitle: song.title,
          songArtist: song.artist,
          songId: song.songId,
          artworkUrl: song.artworkUrl,
          album: song.album,
          popularity: song.popularity,
        });
        if (!res.request_id) {
          setError(res.message || friendlyError());
          return;
        }
        setAck(res);
        setStep("confirm");
      } catch {
        setError(friendlyError());
      } finally {
        setPending(false);
      }
    },
    [pending, genre, eventId],
  );

  const requestAnother = useCallback(() => {
    setAck(null);
    setError(null);
    setStep("song");
  }, []);

  const changeGenre = useCallback(() => {
    setAck(null);
    setError(null);
    setGenre(null);
    setStep("genre");
  }, []);

  const backToGenres = useCallback(() => {
    setError(null);
    setStep("genre");
  }, []);

  const eventLine = eventId ? "Live now" : "Connecting…";

  return (
    <main
      className="mx-auto flex min-h-dvh w-full max-w-[560px] flex-col px-5"
      style={{
        paddingTop: "calc(env(safe-area-inset-top) + 1.5rem)",
        paddingBottom: "calc(env(safe-area-inset-bottom) + 2rem)",
        paddingLeft: "calc(env(safe-area-inset-left) + 1.25rem)",
        paddingRight: "calc(env(safe-area-inset-right) + 1.25rem)",
      }}
    >
      <p className="sr-only" role="status" aria-live="polite">
        {pending ? "Sending your request" : (error ?? "")}
      </p>

      {step === "genre" && (
        <GenreGrid
          eventLine={eventLine}
          djStatus={djStatus}
          pulse={pulse}
          pulseLimited={pulseLimited}
          pulsePending={pulsePending}
          onPick={pickGenre}
          onPulseChange={changePulse}
        />
      )}

      {step === "song" && genre && (
        <SongSearch
          genreKey={genre}
          pending={pending}
          error={error}
          onBack={backToGenres}
          onSubmit={submit}
        />
      )}

      {step === "confirm" && ack && (
        <Confirmation ack={ack} onRequestAnother={requestAnother} onChangeGenre={changeGenre} />
      )}
    </main>
  );
}
