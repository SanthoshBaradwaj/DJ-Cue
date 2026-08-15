// Shared API client. Owned by the integrator — UI modules import from here
// and must not hand-roll fetches or socket handling.

import type {
  DashboardState,
  EventRecord,
  RequestAck,
  RequestStatus,
  Song,
  WSMessage,
} from "./types";

const LAN_HOST_RE = /^(localhost|127\.0\.0\.1|192\.168\.\d{1,3}\.\d{1,3}|10\.\d{1,3}\.\d{1,3}\.\d{1,3}|172\.(1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})$/;

/**
 * Resolve the backend origin.
 *
 * Two deployment shapes share this codebase:
 * - Laptop-on-venue-wifi: frontend and backend run on the same machine, one
 *   port apart. A phone that opens http://192.168.1.5:3000 talks to
 *   http://192.168.1.5:8000 with zero configuration.
 * - Hosted (the default here): frontend and backend deploy as one Vercel
 *   project via vercel.json's `services` + path `rewrites`
 *   (/api/*, /ws/* -> backend, everything else -> frontend), so they share
 *   one domain and a relative path is already correct -- base is "".
 * NEXT_PUBLIC_API_BASE overrides either, for a backend on its own domain.
 */
export function apiBase(): string {
  const override = process.env.NEXT_PUBLIC_API_BASE;
  if (override !== undefined) return override.replace(/\/$/, "");
  if (typeof window === "undefined") return "";
  const { protocol, hostname } = window.location;
  if (LAN_HOST_RE.test(hostname)) return `${protocol}//${hostname}:8000`;
  return "";
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
  health: () => json<{ ok: boolean; supabase: boolean; version: string }>("/api/health"),

  config: (eventId?: string) =>
    json<{ event_id: string; guest_url: string }>(
      `/api/config${eventId ? `?event_id=${encodeURIComponent(eventId)}` : ""}`,
    ),

  events: {
    list: () => json<{ events: EventRecord[] }>("/api/events"),
    create: (name: string) =>
      json<EventRecord>("/api/events", { method: "POST", body: JSON.stringify({ name }) }),
  },

  searchSongs: (q: string, genre?: string, limit = 8) =>
    json<{ songs: Song[] }>(
      `/api/catalog/search?q=${encodeURIComponent(q)}` +
        (genre ? `&genre=${encodeURIComponent(genre)}` : "") +
        `&limit=${limit}`,
    ),

  submitRequest: (input: {
    eventId: string;
    genre: string;
    songTitle: string;
    songArtist?: string;
    songId?: string | null;
  }) =>
    json<RequestAck>("/api/requests", {
      method: "POST",
      body: JSON.stringify({
        event_id: input.eventId,
        session_id: sessionId(),
        genre: input.genre,
        song_title: input.songTitle,
        song_artist: input.songArtist ?? "",
        song_id: input.songId ?? null,
      }),
    }),

  dashboard: (eventId: string) =>
    json<DashboardState>(`/api/dashboard?event_id=${encodeURIComponent(eventId)}`),

  setStatus: (requestId: string, status: RequestStatus, eventId: string) =>
    json<{ id: string; status: string }>(
      `/api/requests/${encodeURIComponent(requestId)}/status?event_id=${encodeURIComponent(eventId)}`,
      { method: "POST", body: JSON.stringify({ status }) },
    ),
};

export interface DashboardFeedHandlers {
  onState?: (state: DashboardState) => void;
  onMessage?: (msg: WSMessage) => void;
  onStatus?: (status: "connecting" | "live" | "polling") => void;
}

/**
 * Live dashboard feed with automatic degradation.
 *
 * A blank screen mid-set is the worst possible failure, so if the socket
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
