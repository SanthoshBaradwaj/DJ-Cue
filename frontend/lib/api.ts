// Shared API client. Owned by the integrator — UI modules import from here and
// must not hand-roll fetches or socket handling.

import type {
  DashboardState,
  DJAction,
  DJState,
  EventStats,
  RequestAck,
  SetlistEntry,
  SlotProposal,
  Tip,
  Track,
  WSMessage,
} from "./types";

/**
 * Resolve the backend origin from the browser's own hostname.
 *
 * This is what makes the venue demo work: a phone that scans the QR and opens
 * http://192.168.1.5:3000 will talk to http://192.168.1.5:8000 without any
 * configuration. Hardcoding localhost would break every device but the laptop.
 */
export function apiBase(): string {
  const override = process.env.NEXT_PUBLIC_API_BASE;
  if (override) return override.replace(/\/$/, "");
  if (typeof window === "undefined") return "http://127.0.0.1:8000";
  const { protocol, hostname } = window.location;
  return `${protocol}//${hostname}:8000`;
}

export function wsBase(): string {
  return apiBase().replace(/^http/, "ws");
}

const SESSION_KEY = "cue_session_id";

/** Anonymous, client-generated. No accounts — this is all the identity there is. */
export function sessionId(): string {
  if (typeof window === "undefined") return "ssr";
  let id = window.localStorage.getItem(SESSION_KEY);
  if (!id) {
    id =
      "sess_" +
      Math.random().toString(36).slice(2, 10) +
      Date.now().toString(36).slice(-4);
    window.localStorage.setItem(SESSION_KEY, id);
  }
  return id;
}

async function json<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${apiBase()}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new Error(`${res.status} ${res.statusText} ${detail}`.trim());
  }
  return (await res.json()) as T;
}

export const api = {
  health: () =>
    json<{
      ok: boolean;
      llm_enabled: boolean;
      track_count: number;
      version: string;
    }>("/api/health"),

  config: () =>
    json<{ event_id: string; guest_url: string; llm_enabled: boolean }>(
      "/api/config",
    ),

  submitRequest: (text: string, eventId = "default") =>
    json<RequestAck>("/api/requests", {
      method: "POST",
      body: JSON.stringify({
        text,
        session_id: sessionId(),
        event_id: eventId,
      }),
    }),

  dashboard: (eventId = "default") =>
    json<DashboardState>(`/api/dashboard?event_id=${encodeURIComponent(eventId)}`),

  setlist: (eventId = "default") =>
    json<{
      event_id: string;
      setlist: SetlistEntry[];
      upcoming: SetlistEntry[];
      current_track: Track | null;
    }>(`/api/setlist?event_id=${encodeURIComponent(eventId)}`),

  /** Import a set. `unmatched` is the half that matters — titles are reported, never guessed. */
  loadSetlist: (
    entries: { cue_time?: string; title: string }[],
    eventId = "default",
  ) =>
    json<{ ok: boolean; loaded: number; unmatched: string[]; upcoming: SetlistEntry[] }>(
      "/api/setlist",
      { method: "POST", body: JSON.stringify({ entries, event_id: eventId }) },
    ),

  advanceSetlist: (eventId = "default") =>
    json<{ ok: boolean; dj: DJState }>("/api/setlist/advance", {
      method: "POST",
      body: JSON.stringify({ event_id: eventId }),
    }),

  insertions: (eventId = "default") =>
    json<{
      event_id: string;
      proposals: SlotProposal[];
      tip_totals: Record<string, number>;
    }>(`/api/insertions?event_id=${encodeURIComponent(eventId)}`),

  /** Accept a proposal into the set. Does NOT settle the tip — playing does. */
  acceptInsertion: (
    trackId: string,
    position: number,
    waveId?: string | null,
    eventId = "default",
  ) =>
    json<{ ok: boolean; dj: DJState }>("/api/insertions/accept", {
      method: "POST",
      body: JSON.stringify({
        track_id: trackId,
        position,
        wave_id: waveId ?? null,
        event_id: eventId,
      }),
    }),

  tips: (eventId = "default") =>
    json<{ event_id: string; tips: Tip[]; totals: Record<string, number> }>(
      `/api/tips?event_id=${encodeURIComponent(eventId)}`,
    ),

  /** Authorise a tip against one track. Nothing is charged at this point. */
  createTip: (
    trackId: string,
    amountMinor: number,
    waveId?: string | null,
    eventId = "default",
  ) =>
    json<{ ok: boolean; tip: Tip }>("/api/tips", {
      method: "POST",
      body: JSON.stringify({
        track_id: trackId,
        amount_minor: amountMinor,
        wave_id: waveId ?? null,
        session_id: sessionId(),
        event_id: eventId,
      }),
    }),

  decide: (
    trackId: string,
    action: DJAction,
    waveId?: string | null,
    eventId = "default",
  ) =>
    json<{ ok: boolean; dj: DashboardState["dj"] }>("/api/decisions", {
      method: "POST",
      body: JSON.stringify({
        track_id: trackId,
        action,
        wave_id: waveId ?? null,
        event_id: eventId,
      }),
    }),

  search: (q: string, limit = 10) =>
    json<{ tracks: Track[] }>(
      `/api/catalog/search?q=${encodeURIComponent(q)}&limit=${limit}`,
    ),

  stats: (eventId = "default") =>
    json<EventStats>(`/api/stats?event_id=${encodeURIComponent(eventId)}`),

  seed: (count = 50, eventId = "default", delayMs = 120) =>
    json<{ ok: boolean; seeded: number }>("/api/demo/seed", {
      method: "POST",
      body: JSON.stringify({ count, event_id: eventId, delay_ms: delayMs }),
    }),

  reset: (eventId = "default") =>
    json<{ ok: boolean }>("/api/demo/reset", {
      method: "POST",
      body: JSON.stringify({ event_id: eventId }),
    }),
};

export interface DashboardFeedHandlers {
  onState?: (state: DashboardState) => void;
  onMessage?: (msg: WSMessage) => void;
  onStatus?: (status: "connecting" | "live" | "polling") => void;
}

/**
 * Live dashboard feed with automatic degradation.
 *
 * A blank screen mid-pitch is the worst possible failure, so if the socket
 * cannot be established (or drops), this silently falls back to polling. The
 * caller sees the same onState callbacks either way.
 */
export function connectDashboard(
  eventId: string,
  handlers: DashboardFeedHandlers,
): () => void {
  let socket: WebSocket | null = null;
  let pollTimer: ReturnType<typeof setInterval> | null = null;
  let retryTimer: ReturnType<typeof setTimeout> | null = null;
  let attempts = 0;
  let closed = false;

  const startPolling = () => {
    if (pollTimer || closed) return;
    handlers.onStatus?.("polling");
    const tick = async () => {
      try {
        handlers.onState?.(await api.dashboard(eventId));
      } catch {
        /* keep trying — the backend may still be booting */
      }
    };
    void tick();
    pollTimer = setInterval(tick, 3000);
  };

  const stopPolling = () => {
    if (pollTimer) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
  };

  const connect = () => {
    if (closed) return;
    handlers.onStatus?.("connecting");
    try {
      socket = new WebSocket(
        `${wsBase()}/ws/dashboard?event_id=${encodeURIComponent(eventId)}`,
      );
    } catch {
      startPolling();
      return;
    }

    socket.onopen = () => {
      attempts = 0;
      stopPolling();
      handlers.onStatus?.("live");
    };

    socket.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data) as WSMessage;
        handlers.onMessage?.(msg);
        if (msg.type === "state") {
          handlers.onState?.(msg.payload as unknown as DashboardState);
        }
      } catch {
        /* ignore malformed frame */
      }
    };

    const retry = () => {
      if (closed) return;
      socket = null;
      attempts += 1;
      // Degrade to polling quickly rather than staring at a dead screen.
      if (attempts >= 2) startPolling();
      const delay = Math.min(1000 * 2 ** attempts, 10000);
      retryTimer = setTimeout(connect, delay);
    };

    socket.onerror = () => socket?.close();
    socket.onclose = retry;
  };

  // Seed immediately so the UI paints before the socket handshake completes.
  void api
    .dashboard(eventId)
    .then((s) => handlers.onState?.(s))
    .catch(() => undefined);
  connect();

  return () => {
    closed = true;
    stopPolling();
    if (retryTimer) clearTimeout(retryTimer);
    if (socket) {
      socket.onclose = null;
      socket.close();
    }
  };
}
