// 1:1 mirror of backend/app/contracts.py. Frozen — see CONTRACT.md.

export interface Intent {
  languages: string[];
  genres: string[];
  moods: string[];
  artists: string[];
  eras: string[];
  energy_target: number;
  danceability: number;
  familiarity: number;
  tempo_hint: string | null;
  confidence: number;
  source: string;
  raw_keywords: string[];
  summary: string;
}

export interface Wave {
  id: string;
  event_id: string;
  label: string;
  summary: string;
  centroid: Intent;
  request_ids: string[];
  raw_count: number;
  unique_sessions: number;
  weight: number;
  momentum: number;
  share: number;
  top_keywords: string[];
  sample_texts: string[];
  created_at: number;
  updated_at: number;
}

export interface Track {
  id: string;
  title: string;
  artist: string;
  language: string;
  genres: string[];
  moods: string[];
  era: string;
  bpm: number;
  energy: number;
  danceability: number;
  popularity: number;
  duration_sec: number;
  audio_file: string | null;
  tags: string[];
}

export interface Candidate {
  track: Track;
  score: number;
  demand_score: number;
  vibe_score: number;
  bridge_score: number;
  bpm_delta: number | null;
  reasons: string[];
}

export interface WaveView {
  wave: Wave;
  candidates: Candidate[];
}

/** One slot in the DJ's planned set. `played_at` set once the needle passes it. */
export interface SetlistEntry {
  id: string;
  position: number;
  track: Track;
  /** Offset from the DJ's own exported history, e.g. "00:54:53". Display only. */
  cue_time: string | null;
  played_at: number | null;
  /** Set when CUE inserted this slot from a crowd wave rather than the DJ planning it. */
  inserted_from_wave_id: string | null;
}

export type TipState = "pending" | "captured" | "released";

/**
 * A tip is a promise, not a payment. It only reaches the DJ if the song it
 * names actually plays; anything still `pending` at the end of the set is
 * released and the guest is never charged.
 */
export interface Tip {
  id: string;
  event_id: string;
  session_id: string;
  track_id: string;
  wave_id: string | null;
  /** Minor units (paise) as an integer — never a float. */
  amount_minor: number;
  currency: string;
  state: TipState;
  created_at: number;
  settled_at: number | null;
}

/**
 * Where a requested track belongs inside the DJ's planned set.
 *
 * `bridge_out` / `bridge_in` are the two-sided fit: out of `after` and into
 * `before`. Both are shown because a track can be great on one edge and a
 * collision on the other, and that is the DJ's call to make.
 */
export interface SlotProposal {
  track: Track;
  wave_id: string | null;
  wave_label: string;
  position: number;
  after: Track | null;
  before: Track | null;
  score: number;
  demand_score: number;
  vibe_score: number;
  bridge_in: number;
  bridge_out: number;
  bpm_delta_in: number | null;
  bpm_delta_out: number | null;
  tip_minor: number;
  tip_broke_tie: boolean;
  reasons: string[];
}

export interface DJState {
  event_id: string;
  current_track: Track | null;
  started_at: number | null;
  queue: Track[];
  history: Track[];
  /** The DJ's plan. Empty for a freestyle event. */
  setlist: SetlistEntry[];
}

export interface EventStats {
  total_requests: number;
  unique_sessions: number;
  wave_count: number;
  compression_ratio: number;
  decisions_made: number;
  actionability: number;
  avg_interpret_ms: number;
  llm_enabled: boolean;
}

export interface DashboardState {
  event_id: string;
  waves: WaveView[];
  dj: DJState;
  stats: EventStats;
}

export interface RequestAck {
  request_id: string;
  session_id: string;
  message: string;
  intent_summary: string;
  wave_id: string | null;
  wave_label: string;
  wave_size: number;
  joined_existing_wave: boolean;
}

export type DJAction = "play" | "later" | "skip";

export interface WSMessage {
  type: "state" | "request" | "decision" | "now_playing";
  payload: Record<string, unknown>;
  ts: number;
}
