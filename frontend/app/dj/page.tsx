"use client";

/**
 * DJ dashboard (M6) — the screen the DJ actually reads mid-set.
 *
 * Deliberately plain: a list of requested songs ordered by request_count,
 * highest first, with one-click Played/Dismiss on every row. Both actions are
 * soft deletes on the backend — the row just leaves this list.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import type { DJStatus, EventRecord } from "@/lib/types";
import { BucketBoard } from "../components/dj/BucketBoard";
import { RequestRow } from "../components/dj/RequestRow";
import { TopBar } from "../components/dj/TopBar";
import { useDashboardFeed } from "../components/dj/useDashboardFeed";
import { useFlipReorder } from "../components/dj/useFlipReorder";
import { PinGate } from "../components/shared/PinGate";

const ACTIVE_EVENT_KEY = "cue_dj_active_event";
// Same event backend/app/db.py's DEV_EVENT_SLUG guards against for guest
// resolution -- it also has the newest created_at of any active event, so
// without this a fresh browser with no stored preference (a new laptop, a
// cleared cache) would silently default the whole dashboard to the empty
// dev event instead of the real one. Still fully selectable from the
// dropdown -- events.list() isn't filtered, just this fallback pick.
const DEV_EVENT_SLUG = "dj-cue-dev-test";

export default function DJDashboardPage() {
  return (
    <PinGate role="dj">
      <DJDashboard />
    </PinGate>
  );
}

function DJDashboard() {
  const [events, setEvents] = useState<EventRecord[]>([]);
  const [activeEventId, setActiveEventId] = useState<string | null>(null);
  const [loadingEvents, setLoadingEvents] = useState(true);
  const [djStatusBusy, setDjStatusBusy] = useState(false);

  const loadEvents = useCallback(async (preferId?: string) => {
    const { events: list } = await api.events.list();
    setEvents(list);
    if (preferId && list.some((e) => e.id === preferId)) {
      setActiveEventId(preferId);
      return;
    }
    const stored =
      typeof window !== "undefined" ? window.localStorage.getItem(ACTIVE_EVENT_KEY) : null;
    if (stored && list.some((e) => e.id === stored)) {
      setActiveEventId(stored);
    } else if (list.some((e) => e.slug !== DEV_EVENT_SLUG)) {
      setActiveEventId(list.find((e) => e.slug !== DEV_EVENT_SLUG)!.id);
    } else if (list.length > 0) {
      setActiveEventId(list[0].id);
    } else {
      const created = await api.events.create("DJPrashant-PDX");
      setEvents([created]);
      setActiveEventId(created.id);
    }
  }, []);

  useEffect(() => {
    loadEvents()
      .catch(() => undefined)
      .finally(() => setLoadingEvents(false));
  }, [loadEvents]);

  useEffect(() => {
    if (activeEventId && typeof window !== "undefined") {
      window.localStorage.setItem(ACTIVE_EVENT_KEY, activeEventId);
    }
  }, [activeEventId]);

  const { state, status, notice, setRequestStatus } = useDashboardFeed(activeEventId);

  const activeEvent = events.find((e) => e.id === activeEventId) ?? null;

  const onChangeDjStatus = useCallback(
    (next: DJStatus) => {
      if (!activeEventId || djStatusBusy) return;
      setDjStatusBusy(true);
      // Optimistic: a DJ tapping this between songs needs it to feel instant.
      setEvents((prev) =>
        prev.map((e) => (e.id === activeEventId ? { ...e, dj_status: next } : e)),
      );
      api.events
        .setDjStatus(activeEventId, next)
        .catch(() => loadEvents(activeEventId))
        .finally(() => setDjStatusBusy(false));
    },
    [activeEventId, djStatusBusy, loadEvents],
  );

  const requests = state?.requests ?? [];
  // Only present once the event has genre_buckets configured -- every other
  // event (today's default) keeps the plain ranked list below.
  const buckets = state?.buckets ?? null;
  const listRef = useRef<HTMLUListElement>(null);
  useFlipReorder(listRef, requests.map((r) => r.id).join("|"));

  return (
    <main className="flex h-dvh flex-col overflow-hidden bg-ink text-chalk">
      <TopBar
        events={events}
        activeEventId={activeEventId}
        onSelectEvent={setActiveEventId}
        stats={state?.stats ?? null}
        status={status}
        djStatus={activeEvent?.dj_status ?? null}
        onChangeDjStatus={onChangeDjStatus}
        djStatusBusy={djStatusBusy}
      />

      {notice && (
        <p
          role="status"
          className="shrink-0 border-b border-ink-line/80 bg-ink-raised/80 px-5 py-2.5 text-[13px] text-mist xl:px-8"
        >
          {notice}
        </p>
      )}

      <div className="min-h-0 flex-1 overflow-y-auto px-5 py-5 xl:px-8 xl:py-7">
        <div className={buckets && buckets.length > 0 ? "mx-auto w-full" : "mx-auto w-full max-w-2xl"}>
          {loadingEvents || !state ? (
            <WaitingForTheRoom connected={Boolean(state)} />
          ) : buckets && buckets.length > 0 ? (
            <BucketBoard
              buckets={buckets}
              onPlayed={(id) => setRequestStatus(id, "played")}
              onDismiss={(id) => setRequestStatus(id, "dismissed")}
            />
          ) : requests.length > 0 ? (
            <ul ref={listRef} className="flex flex-col gap-3">
              {requests.map((request, i) => (
                <RequestRow
                  key={request.id}
                  request={request}
                  rank={i}
                  onPlayed={() => setRequestStatus(request.id, "played")}
                  onDismiss={() => setRequestStatus(request.id, "dismissed")}
                />
              ))}
            </ul>
          ) : (
            <WaitingForTheRoom connected />
          )}
        </div>
      </div>
    </main>
  );
}

function WaitingForTheRoom({ connected }: { connected: boolean }) {
  return (
    <div className="flex min-h-[24rem] items-center justify-center px-6">
      <div className="max-w-sm text-center">
        <span
          className="mx-auto mb-6 block h-2.5 w-2.5 rounded-full animate-pulse-ring"
          style={{ background: "var(--color-cue-1)" }}
          aria-hidden="true"
        />
        <h2 className="text-xl font-semibold tracking-[-0.02em] text-chalk">
          {connected ? "Listening for requests" : "Connecting to the floor"}
        </h2>
        <p className="mt-2.5 text-sm leading-relaxed text-mist/80">
          {connected
            ? "Requests show up here the moment a guest sends one, ranked by how many people asked."
            : "Reaching the DJ-Cue backend. The dashboard fills in as soon as it answers."}
        </p>
      </div>
    </div>
  );
}
