"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { RequestAck } from "@/lib/types";
import Confirmation from "./Confirmation";
import RequestComposer from "./RequestComposer";
import { prettyEventName } from "./intent";
import { haptic } from "./motion";
import { useGuestHistory } from "./useGuestHistory";

function friendlyError(): string {
  if (typeof navigator !== "undefined" && navigator.onLine === false) {
    return "You're offline — the venue Wi-Fi dipped. Your words are safe.";
  }
  return "Couldn't reach the DJ just then. Your words are safe.";
}

/**
 * The whole guest surface: one input, one instant validation, one way back.
 *
 * Everything here is client-side — the page has no server data to wait on, and
 * a QR scan should paint before the guest's thumb reaches the screen.
 */
export default function GuestApp() {
  const [text, setText] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [ack, setAck] = useState<RequestAck | null>(null);
  const [submittedText, setSubmittedText] = useState("");
  const [eventName, setEventName] = useState<string | null>(null);
  // Remounts the composer on "ask again" so autofocus fires a second time.
  const [round, setRound] = useState(0);

  const { entries, add } = useGuestHistory();

  useEffect(() => {
    let alive = true;
    api
      .config()
      .then((cfg) => {
        if (alive) setEventName(prettyEventName(cfg.event_id));
      })
      .catch(() => {
        /* the header is decoration; a missing backend must not block the input */
      });
    return () => {
      alive = false;
    };
  }, []);

  const submit = useCallback(async () => {
    const value = text.trim();
    if (!value || pending) return;

    haptic(12);
    setPending(true);
    setError(null);

    try {
      const res = await api.submitRequest(value);
      add({
        id: res.request_id || `local_${Date.now()}`,
        text: value,
        waveLabel: res.wave_label || "",
        waveSize: res.wave_size || 0,
        joined: res.joined_existing_wave === true,
        at: Date.now(),
      });
      setSubmittedText(value);
      setAck(res);
      setText("");
      if (typeof window !== "undefined") window.scrollTo({ top: 0 });
    } catch {
      // Never surface a raw error to a guest, and never drop what they typed.
      setError(friendlyError());
    } finally {
      setPending(false);
    }
  }, [text, pending, add]);

  const askAgain = useCallback(() => {
    setAck(null);
    setSubmittedText("");
    setError(null);
    setText("");
    setRound((r) => r + 1);
    if (typeof window !== "undefined") window.scrollTo({ top: 0 });
  }, []);

  const eventLine = eventName ? `${eventName} · live` : "The DJ is listening";

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
      {/* Persistent live region: the confirmation carries its own, but the
          composer's pending/failure states need one that already exists in the
          DOM to be announced at all. */}
      <p className="sr-only" role="status" aria-live="polite">
        {pending ? "Sending your request" : (error ?? "")}
      </p>

      {ack ? (
        <Confirmation
          ack={ack}
          submittedText={submittedText}
          history={entries}
          onAskAgain={askAgain}
        />
      ) : (
        <RequestComposer
          key={round}
          text={text}
          onTextChange={setText}
          onSubmit={submit}
          pending={pending}
          error={error}
          eventLine={eventLine}
        />
      )}
    </main>
  );
}
