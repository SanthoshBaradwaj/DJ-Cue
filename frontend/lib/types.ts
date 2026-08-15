// 1:1 mirror of backend/app/contracts.py. Frozen — see CONTRACT.md.

export interface EventRecord {
  id: string;
  name: string;
  slug: string;
  status: "active" | "ended";
  created_at: number;
}

export interface Genre {
  key: string;
  label: string;
  region: "north" | "south";
}

export interface Song {
  id: string;
  title: string;
  artist: string;
  genre: string;
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
}

export interface DashboardState {
  event_id: string;
  requests: SongRequest[];
  stats: EventStats;
}

export interface WSMessage {
  type: "state" | "new_request" | "status_change";
  payload: Record<string, unknown>;
  ts: number;
}
