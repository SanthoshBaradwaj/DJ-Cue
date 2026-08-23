"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import type { FlushAck } from "@/lib/types";

/**
 * The secondary confirmation layer for a flush -- the operator PIN (gating
 * /present itself, and checked again server-side on the flush call) is the
 * access-control layer; this is the "do you actually mean it" layer, since
 * a flush is a hard delete with no undo. Deliberately harsher copy when the
 * selected event isn't the dev one -- a mis-tap here can empty a live
 * queue mid-party, not just a throwaway test event.
 */
export function ResetConfirmModal({
  eventId,
  eventLabel,
  isDev,
  onClose,
  onDone,
}: {
  eventId: string;
  eventLabel: string;
  isDev: boolean;
  onClose: () => void;
  onDone: (ack: FlushAck) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const confirm = () => {
    if (busy) return;
    setBusy(true);
    setError(null);
    api.events
      .flush(eventId)
      .then((ack) => onDone(ack))
      .catch(() => setError("Couldn't reach the server -- try again."))
      .finally(() => setBusy(false));
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="reset-confirm-heading"
      onClick={onClose}
      className="fixed inset-0 z-50 flex items-center justify-center bg-ink/80 backdrop-blur-sm p-4"
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-sm rounded-3xl border border-ink-line bg-ink-card p-6 shadow-2xl"
      >
        <p
          className="text-[11px] font-bold uppercase tracking-[0.14em]"
          style={{ color: isDev ? "var(--color-mist)" : "var(--color-danger)" }}
        >
          {isDev ? "Dev/Test event" : "Live event"}
        </p>
        <h2 id="reset-confirm-heading" className="mt-1 text-xl font-semibold text-chalk">
          Reset {eventLabel}?
        </h2>
        <p className="mt-2 text-[14px] leading-relaxed text-mist">
          This permanently deletes every queued song, request count, active-user count, and
          pulse vote for this event. It cannot be undone.
          {!isDev && " This is the LIVE event — anyone scanning right now will see an empty queue."}
        </p>
        {error && <p className="mt-3 text-[13px] font-medium text-danger">{error}</p>}
        <div className="mt-5 flex gap-2.5">
          <button
            type="button"
            onClick={onClose}
            className="tap h-12 flex-1 rounded-2xl border border-ink-line text-[15px] font-semibold text-chalk transition-colors active:bg-ink-line/70"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={confirm}
            disabled={busy}
            className="tap h-12 flex-1 rounded-2xl bg-danger text-[15px] font-bold text-white transition-all duration-150 active:scale-[0.985] disabled:opacity-50"
          >
            {busy ? "Resetting…" : "Reset"}
          </button>
        </div>
      </div>
    </div>
  );
}
