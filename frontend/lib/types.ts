// 1:1 mirror of backend/app/contracts.py. Frozen — see CONTRACT.md.

export type DJStatus = "open" | "closed";

/** Optional, guest-set crowd-pulse signal. Purely informational -- never
 * gates anything, and never shown per-person, only as an aggregate. */
export type PulseStatus = "single" | "committed";

export interface PulseAck {
  status: PulseStatus | null;
  /** Real changes only -- re-selecting the active status doesn't count. */
  toggle_count: number;
  /** True once this session has hit the 5-change cap for the event. */
  limited: boolean;
  message: string | null;
}

/** One column of a DJ's genre-quota chart. `genres` maps to this app's own
 * genre keys; a request must match one of them to belong in this bucket. */
export interface GenreBucket {
  label: string;
  genres: string[];
  slots: number;
}

/** Per-event configuration, entirely opt-in. Every field defaults to "off"
 * so an event with no settings behaves exactly like the app always has. */
export interface EventSettings {
  queue_cap: number | null;
  genre_buckets: GenreBucket[];
  /** Shared budget across a fresh request and an upvote on an existing one
   * -- null means unlimited (today's behavior). */
  max_actions_per_session: number | null;
  allow_cross_genre_backfill: boolean;
  chart_rank_order: string[];
  show_public_queue: boolean;
  first_time_prompt_enabled: boolean;
  instagram_handle: string | null;
  venue_name: string | null;
  start_time: string | null;
  confirmation_toast_copy: string | null;
}

export interface EventRecord {
  id: string;
  name: string;
  slug: string;
  status: "active" | "ended";
  /** The DJ's own availability signal, shown to guests before they spend
   * time searching. */
  dj_status: DJStatus;
  created_at: number;
  settings: EventSettings;
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
  album: string | null;
  release_date: string | null;
  /** Deezer's own catalog rank -- a relative popularity score, not a
   * literal stream count. Always null for an iTunes-sourced result. */
  popularity: number | null;
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
  /** Real, measured tempo from Deezer's catalog metadata -- never AI
   * estimated. Only present for a Deezer-sourced pick; null otherwise. */
  bpm: number | null;
  album: string | null;
  release_date: string | null;
  popularity: number | null;
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
