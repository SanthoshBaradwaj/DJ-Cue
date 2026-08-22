"use client";

// The single place the DJ dashboard talks to the outside world. The socket,
// its backoff, and the polling fallback all live in lib/api.ts's
// connectDashboard() — this hook just wires it to component state and adds
// the one thing the transport layer can't own: an optimistic status update
// so a tap feels instant instead of waiting for the next socket push.

import { useCallback, useEffect, useState } from "react";
import { api, connectDashboard } from "@/lib/api";
import type { DashboardState, RequestStatus } from "@/lib/types";

export type FeedStatus = "connecting" | "live" | "polling";

export function useDashboardFeed(eventId: string | null) {
  const [state, setState] = useState<DashboardState | null>(null);
  const [status, setStatus] = useState<FeedStatus>("connecting");
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    if (!eventId) return;
    setState(null);
    const stop = connectDashboard(eventId, {
      onState: (s) => {
        setState(s);
        setNotice(null);
      },
      onStatus: setStatus,
    });
    return stop;
  }, [eventId]);

  useEffect(() => {
    if (!eventId || state) return;
    const t = setTimeout(
      () =>
        setNotice(
          "No response from the DJ-Cue backend yet — retrying. The dashboard fills in the moment it answers.",
        ),
      4000,
    );
    return () => clearTimeout(t);
  }, [eventId, state]);

  const setRequestStatus = useCallback(
    async (requestId: string, next: RequestStatus) => {
      if (!eventId) return;
      // Fold the row out of the list immediately; the next "state" push
      // confirms it, but a DJ tapping a 48px button mid-set must never
      // wonder if it registered. On the bucket board this means the slot
      // goes blank right away -- the backend's own dynamic replacement
      // (promoting the next-ranked backlog song into that slot) arrives on
      // the next push shortly after, same as it always does server-side.
      setState((prev) =>
        prev
          ? {
              ...prev,
              requests: prev.requests.filter((r) => r.id !== requestId),
              buckets: prev.buckets
                ? prev.buckets.map((b) => ({
                    ...b,
                    requests: b.requests.map((r) => (r?.id === requestId ? null : r)),
                  }))
                : prev.buckets,
            }
          : prev,
      );
      try {
        await api.setStatus(requestId, next, eventId);
      } catch {
        setNotice("That action didn't reach the backend. Tap again when the connection returns.");
      }
    },
    [eventId],
  );

  return { state, status, notice, setRequestStatus };
}
