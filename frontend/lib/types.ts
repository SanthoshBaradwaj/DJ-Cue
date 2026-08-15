// 1:1 mirror of backend/app/contracts.py. Frozen — see CONTRACT.md.

export type DJStatus = "open" | "closed";

/** Optional, guest-set crowd-pulse signal. Purely informational -- never
 * gates anything, and never shown per-person, only as an aggregate. */
export type PulseStatus = "single" | "committed";

export interface EventRecord {
  id: string;
  name: string;
  slug: string;
  status: "active" | "ended";
  /** The DJ's own availability signal, shown to guests before they spend
   * time searching. */
  dj_status: DJStatus;
  created_at: number;
}

export interface Genre {
  key: string;
  label: string;
  /** Informational only, never rendered as a section grouping — "other"
   * covers genres that aren't a North/South India regional language. */
  region: "north" | "south" | "other";
}

/** A search result from the iTunes Search API -- `id` is an iTunes track id,
 * not a row in our own database. There is no local catalog anymore. */
export interface Song {
  id: string;
  title: string;
  artist: string;
  genre: string;
  artwork_url: string | null;
}

export type RequestStatus = "queued" | "played" | "dismissed";

/** One row per distinct song per event. Duplicate submissions bump
 * `request_count` on this row rather than creating a new one. */
export interface SongRequest {
  id: string;
  event_id: string;
  song_id: string | null;
  song_title: string;
  song_artist: string;
  genre: string;
  request_count: number;
  status: RequestStatus;
  artwork_url: string | null;
  created_at: number;
  updated_at: number;
}

export interface RequestAck {
  request_id: string | null;
  song_title: string;
  request_count: number;
  /** This device already contributed to this song's count (or is inside the
   * submit cooldown) — the tap still feels acknowledged, it just didn't move
   * the number. */
  already_counted: boolean;
  message: string;
}

export interface EventStats {
  total_requests: number;
  unique_songs: number;
  unique_sessions: number;
  pulse_single: number;
  pulse_committed: number;
  pulse_total: number;
}

export interface DashboardState {
  event_id: string;
  requests: SongRequest[];
  stats: EventStats;
}

export interface DBHealth {
  ok: boolean;
  latency_ms: number | null;
  total_requests_all_time: number | null;
  last_insert_at: number | null;
  error: string | null;
}

export interface HealthReport {
  ok: boolean;
  supabase: boolean;
  version: string;
  db: DBHealth;
}

export interface WSMessage {
  type: "state" | "new_request" | "status_change";
  payload: Record<string, unknown>;
  ts: number;
}
