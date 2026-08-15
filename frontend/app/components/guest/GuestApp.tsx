"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { RequestAck } from "@/lib/types";
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

  useEffect(() => {
    let alive = true;
    const fromUrl =
      typeof window !== "undefined"
        ? new URLSearchParams(window.location.search).get("event")
        : null;
    if (fromUrl) {
      setEventId(fromUrl);
      return;
    }
    api
      .config()
      .then((cfg) => {
        if (alive) setEventId(cfg.event_id);
      })
      .catch(() => {
        /* resolved lazily on submit if this never lands */
      });
    return () => {
      alive = false;
    };
  }, []);

  const pickGenre = useCallback((key: string) => {
    setGenre(key);
    setError(null);
    setStep("song");
  }, []);

  const submit = useCallback(
    async (song: { title: string; artist?: string; songId?: string | null }) => {
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

      {step === "genre" && <GenreGrid eventLine={eventLine} onPick={pickGenre} />}

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
