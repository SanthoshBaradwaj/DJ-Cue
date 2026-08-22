// Shared API client. Owned by the integrator — UI modules import from here
// and must not hand-roll fetches or socket handling.

import type {
  DashboardState,
  DJStatus,
  EventRecord,
  EventSettings,
  FirstTimeAnswerAck,
  HealthReport,
  PulseAck,
  PulseStatus,
  RequestAck,
  RequestStatus,
  Song,
  SongRequest,
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
  health: () => json<HealthReport>("/api/health"),

  config: (eventId?: string) =>
    json<{ event_id: string; guest_url: string; dj_status: DJStatus; settings: EventSettings }>(
      `/api/config${eventId ? `?event_id=${encodeURIComponent(eventId)}` : ""}`,
    ),

  events: {
    list: () => json<{ events: EventRecord[] }>("/api/events"),
    create: (name: string) =>
      json<EventRecord>("/api/events", { method: "POST", body: JSON.stringify({ name }) }),
    setDjStatus: (eventId: string, status: DJStatus) =>
      json<EventRecord>(`/api/events/${encodeURIComponent(eventId)}/status`, {
        method: "POST",
        body: JSON.stringify({ status }),
      }),
    setPulse: (eventId: string, status: PulseStatus) =>
      json<PulseAck>(`/api/events/${encodeURIComponent(eventId)}/pulse`, {
        method: "POST",
        body: JSON.stringify({ session_id: sessionId(), status }),
      }),
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
    artworkUrl?: string | null;
    album?: string | null;
    popularity?: number | null;
    catalogUrl?: string | null;
    durationSeconds?: number | null;
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
        artwork_url: input.artworkUrl ?? null,
        album: input.album ?? null,
        popularity: input.popularity ?? null,
        catalog_url: input.catalogUrl ?? null,
        duration_seconds: input.durationSeconds ?? null,
      }),
    }),

  dashboard: (eventId: string) =>
    json<DashboardState>(`/api/dashboard?event_id=${encodeURIComponent(eventId)}`),

  firstTimeAnswer: (eventId: string, answer: "yes" | "no") =>
    json<FirstTimeAnswerAck>("/api/first-time-answer", {
      method: "POST",
      body: JSON.stringify({ event_id: eventId, session_id: sessionId(), answer }),
    }),

  setStatus: (requestId: string, status: RequestStatus, eventId: string) =>
    json<{ id: string; status: string }>(
      `/api/requests/${encodeURIComponent(requestId)}/status?event_id=${encodeURIComponent(eventId)}`,
      { method: "POST", body: JSON.stringify({ status }) },
    ),

  // Re-attempts catalog resolution for whichever of bpm/release_date/
  // catalog_url/duration_seconds a request is still missing -- a no-op on
  // the backend (no external calls) once every field is already filled.
  refreshRequestMetadata: (requestId: string, eventId: string) =>
    json<SongRequest>(
      `/api/requests/${encodeURIComponent(requestId)}/refresh?event_id=${encodeURIComponent(eventId)}`,
      { method: "POST" },
    ),
};

export interface DashboardFeedHandlers {
  onState?: (state: DashboardState) => void;
  onMessage?: (msg: WSMessage) => void;
  onStatus?: (status: "connecting" | "live" | "polling") => void;
}

/** How often the reliable baseline poll runs, regardless of websocket state. */
const POLL_INTERVAL_MS = 2500;

/**
 * Live dashboard feed with a poll that never stops.
 *
 * The backend can run as more than one instance behind the host's load
 * balancer, and this app's push channel (an in-process pub/sub -- see
 * events.py) only reaches whichever instance actually handled a write. A
 * websocket that happens to land on a *different* instance stays open and
 * simply never receives that update -- indistinguishable, from the client's
 * side, from "live." So polling is not a fallback here, it's the floor: it
 * always runs, every `POLL_INTERVAL_MS`, straight against the database
 * (the one place guaranteed to be consistent across instances). The
 * websocket is a pure latency optimization on top -- when it happens to
 * land on the right instance, updates arrive faster than the next poll
 * tick; when it doesn't, the poll still catches up within one interval.
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
  let live = false;

  const poll = async () => {
    try {
      handlers.onState?.(await api.dashboard(eventId));
    } catch {
      /* keep trying — the backend may still be booting */
    }
  };

  const connect = () => {
    if (closed) return;
    if (!live) handlers.onStatus?.("connecting");
    try {
      socket = new WebSocket(
        `${wsBase()}/ws/dashboard?event_id=${encodeURIComponent(eventId)}`,
      );
    } catch {
      handlers.onStatus?.("polling");
      return;
    }

    socket.onopen = () => {
      attempts = 0;
      live = true;
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
      live = false;
      attempts += 1;
      handlers.onStatus?.("polling");
      const delay = Math.min(1000 * 2 ** attempts, 10000);
      retryTimer = setTimeout(connect, delay);
    };

    socket.onerror = () => socket?.close();
    socket.onclose = retry;
  };

  // Seed immediately so the UI paints before the socket handshake completes.
  void poll();
  pollTimer = setInterval(poll, POLL_INTERVAL_MS);
  connect();

  return () => {
    closed = true;
    if (pollTimer) clearInterval(pollTimer);
    if (retryTimer) clearTimeout(retryTimer);
    if (socket) {
      socket.onclose = null;
      socket.close();
    }
  };
}
