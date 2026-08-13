// DEV-ONLY SCAFFOLDING.
//
// Reachable exclusively through `/dj?mock=1` so the dashboard can be built,
// screenshotted and demoed while M4 is still landing. Nothing here is imported
// by the live code path — with no query param the page talks to the real feed
// through lib/api.ts.

import type {
  Candidate,
  DashboardState,
  Intent,
  Track,
  WaveView,
} from "@/lib/types";

let seq = 0;
const uid = (p: string) => `${p}_${(seq += 1).toString(36)}`;

function intent(over: Partial<Intent>): Intent {
  return {
    languages: [],
    genres: [],
    moods: [],
    artists: [],
    eras: [],
    energy_target: 0.7,
    danceability: 0.7,
    familiarity: 0.6,
    tempo_hint: null,
    confidence: 0.8,
    source: "llm",
    raw_keywords: [],
    summary: "",
    ...over,
  };
}

function track(
  id: string,
  title: string,
  artist: string,
  language: string,
  era: string,
  bpm: number,
  energy: number,
  genres: string[],
  duration_sec = 208,
): Track {
  return {
    id,
    title,
    artist,
    language,
    genres,
    moods: [],
    era,
    bpm,
    energy,
    danceability: Math.min(0.98, energy + 0.05),
    popularity: 0.78,
    duration_sec,
    audio_file: null,
    tags: [],
  };
}

function candidate(
  t: Track,
  score: number,
  bpmDelta: number | null,
  reasons: string[],
): Candidate {
  return {
    track: t,
    score,
    demand_score: Math.min(1, score + 0.06),
    vibe_score: Math.min(1, score - 0.04),
    bridge_score: bpmDelta === null ? 0.5 : Math.max(0, 1 - Math.abs(bpmDelta) / 20),
    bpm_delta: bpmDelta,
    reasons,
  };
}

const CURRENT = track(
  "trk_illegal",
  "Illegal Weapon 2.0",
  "Jasmine Sandlas, Garry Sandhu",
  "Punjabi",
  "2010s",
  128,
  0.81,
  ["Bhangra", "Dance"],
  201,
);

const now = () => Date.now() / 1000;

function waveView(
  rank: number,
  label: string,
  summary: string,
  rawCount: number,
  uniqueSessions: number,
  share: number,
  momentum: number,
  keywords: string[],
  samples: string[],
  centroid: Partial<Intent>,
  candidates: Candidate[],
): WaveView {
  return {
    wave: {
      id: `wave_${rank}`,
      event_id: "default",
      label,
      summary,
      centroid: intent(centroid),
      request_ids: Array.from({ length: rawCount }, () => uid("req")),
      raw_count: rawCount,
      unique_sessions: uniqueSessions,
      weight: share,
      momentum,
      share,
      top_keywords: keywords,
      sample_texts: samples,
      created_at: now() - 900,
      updated_at: now(),
    },
    candidates,
  };
}

const WAVES: WaveView[] = [
  waveView(
    1,
    "High-Energy Punjabi",
    "The floor wants dhol, and it wants it now.",
    16,
    12,
    0.34,
    0.82,
    ["punjabi", "bhangra", "dhol", "peak time", "ap dhillon"],
    [
      "put on some punjabi bangers please",
      "we need brown munde RIGHT NOW",
      "bhangra time, everyone is already up",
    ],
    {
      languages: ["Punjabi"],
      genres: ["Bhangra", "Punjabi Pop"],
      moods: ["hype"],
      energy_target: 0.87,
      summary: "Loud, fast Punjabi with heavy percussion",
    },
    [
      candidate(
        track("trk_brown", "Brown Munde", "AP Dhillon, Gurinder Gill", "Punjabi", "2020s", 130, 0.86, ["Punjabi Hip-Hop"], 197),
        0.94,
        2,
        ["Named by 5 people directly", "+2 BPM — beatmatches the current track", "Peak-time energy 0.86"],
      ),
      candidate(
        track("trk_3peg", "3 Peg", "Sharry Mann", "Punjabi", "2010s", 128, 0.79, ["Bhangra"], 213),
        0.88,
        0,
        ["Same tempo — mix on the downbeat", "Bhangra staple for this crowd age", "12 unique devices in this wave"],
      ),
      candidate(
        track("trk_wakhra", "Wakhra Swag", "Navv Inder, Badshah", "Punjabi", "2010s", 134, 0.88, ["Bhangra", "Hip-Hop"], 224),
        0.85,
        6,
        ["Lifts energy +0.07 for the peak", "Bridges Punjabi into hip-hop wave", "Matches 'dhol' keyword"],
      ),
    ],
  ),
  waveView(
    2,
    "2000s Bollywood Nostalgia",
    "A pocket of the room wants to sing along.",
    11,
    8,
    0.234,
    0.41,
    ["bollywood", "2000s", "throwback", "sing-along"],
    [
      "any 2000s bollywood?",
      "dus bahane please, that is my song",
      "old school hindi party songs would go off",
    ],
    {
      languages: ["Hindi"],
      genres: ["Bollywood"],
      eras: ["2000s"],
      energy_target: 0.74,
      summary: "Nostalgic Hindi dancefloor classics",
    },
    [
      candidate(
        track("trk_dus", "Dus Bahane", "KK, Shaan", "Hindi", "2000s", 132, 0.83, ["Bollywood", "Dance"], 245),
        0.91,
        4,
        ["Requested by name 3 times", "+4 BPM — safe blend", "Highest sing-along factor in catalog"],
      ),
      candidate(
        track("trk_disco", "It's The Time To Disco", "Shaan, KK, Loy Mendonsa", "Hindi", "2000s", 126, 0.78, ["Bollywood"], 268),
        0.84,
        -2,
        ["Era match: 2000s", "Slight tempo drop resets the floor", "Familiarity 0.92"],
      ),
      candidate(
        track("trk_party", "Where's The Party Tonight", "Shaan, KK", "Hindi", "2000s", 124, 0.76, ["Bollywood"], 251),
        0.79,
        -4,
        ["Same album era as two requests", "Keeps Hindi vocals on the floor"],
      ),
    ],
  ),
  waveView(
    3,
    "Peak-Time House",
    "The back of the room is asking for four-on-the-floor.",
    9,
    6,
    0.191,
    0.63,
    ["house", "peak time", "4x4", "fisher"],
    [
      "more house please",
      "keep the 4x4 going all night",
      "something peak time and dumb",
    ],
    {
      genres: ["House", "Tech House"],
      moods: ["driving"],
      energy_target: 0.9,
      tempo_hint: "125-128",
      summary: "Driving tech house, no vocals needed",
    },
    [
      candidate(
        track("trk_losing", "Losing It", "Fisher", "English", "2010s", 126, 0.91, ["Tech House"], 224),
        0.9,
        -2,
        ["Genre named 4 times", "Energy 0.91 — highest in wave", "Instrumental: clean vocal handoff"],
      ),
      candidate(
        track("trk_body", "Body", "Loud Luxury, brando", "English", "2010s", 122, 0.84, ["House"], 164),
        0.82,
        -6,
        ["Cools tempo before the Punjabi run", "Crossover appeal to wave 2"],
      ),
      candidate(
        track("trk_onekiss", "One Kiss", "Calvin Harris, Dua Lipa", "English", "2010s", 124, 0.8, ["House", "Pop"], 214),
        0.8,
        -4,
        ["Broadest recognition of the three", "Bridges house into pop requests"],
      ),
    ],
  ),
  waveView(
    4,
    "Afrobeats Cooldown",
    "A small group wants the tempo to breathe.",
    6,
    3,
    0.128,
    -0.12,
    ["afrobeats", "slow", "vibe", "rema"],
    [
      "afrobeats?",
      "calm down by rema would be perfect",
      "slow it down a bit, something like essence",
    ],
    {
      genres: ["Afrobeats"],
      moods: ["smooth"],
      energy_target: 0.6,
      summary: "Mid-tempo Afrobeats to reset the room",
    },
    [
      candidate(
        track("trk_essence", "Essence", "Wizkid, Tems", "English", "2020s", 106, 0.62, ["Afrobeats"], 249),
        0.83,
        -22,
        ["Named directly twice", "Large tempo drop — use as a reset", "Energy 0.62 fits a cooldown"],
      ),
      candidate(
        track("trk_calm", "Calm Down", "Rema", "English", "2020s", 107, 0.66, ["Afrobeats", "Pop"], 219),
        0.81,
        -21,
        ["Explicit request in this wave", "Highest global familiarity"],
      ),
      candidate(
        track("trk_last", "Last Last", "Burna Boy", "English", "2020s", 99, 0.58, ["Afrobeats"], 172),
        0.72,
        -29,
        ["Deepest cooldown option", "Sets up a rebuild into house"],
      ),
    ],
  ),
  waveView(
    5,
    "Throwback Hip-Hop",
    "Two people, but they are loud about it.",
    5,
    2,
    0.106,
    0.08,
    ["hip hop", "throwback", "2000s", "club classics"],
    [
      "throw it back to 2003",
      "in da club!!",
      "some old hip hop for the uncles",
    ],
    {
      genres: ["Hip-Hop"],
      eras: ["2000s"],
      energy_target: 0.72,
      summary: "Early-2000s club rap",
    },
    [
      candidate(
        track("trk_indaclub", "In Da Club", "50 Cent", "English", "2000s", 90, 0.74, ["Hip-Hop"], 233),
        0.76,
        -38,
        ["Requested by name", "Only 2 unique devices — low demand"],
      ),
      candidate(
        track("trk_yeah", "Yeah!", "Usher, Lil Jon, Ludacris", "English", "2000s", 105, 0.82, ["Hip-Hop", "Crunk"], 250),
        0.74,
        -23,
        ["Crosses over to the Bollywood wave's era", "Energy holds the floor"],
      ),
      candidate(
        track("trk_crazy", "Crazy In Love", "Beyoncé, JAY-Z", "English", "2000s", 99, 0.79, ["R&B", "Hip-Hop"], 236),
        0.71,
        -29,
        ["Widest appeal in a thin wave", "Era match: 2000s"],
      ),
    ],
  ),
];

export function mockState(): DashboardState {
  return {
    event_id: "default",
    waves: WAVES.map((w) => ({
      wave: { ...w.wave, updated_at: now() },
      candidates: w.candidates.map((c) => ({ ...c })),
    })),
    dj: {
      event_id: "default",
      current_track: CURRENT,
      started_at: now() - 74,
      queue: [
        track("trk_kala", "Kala Chashma", "Amar Arshi, Neha Kakkar", "Hindi", "2010s", 132, 0.89, ["Bollywood"], 226),
        track("trk_gallan", "Gallan Goodiyaan", "Various Artists", "Hindi", "2010s", 128, 0.85, ["Bollywood"], 292),
        track("trk_makhna", "Makhna", "Tanishk Bagchi", "Hindi", "2010s", 124, 0.8, ["Bollywood"], 205),
      ],
      history: [
        track("trk_naach", "Naach Meri Rani", "Guru Randhawa, Nikhita Gandhi", "Hindi", "2020s", 122, 0.8, ["Pop"], 195),
        track("trk_tarara", "Ta Ra Rum Pum", "Shaan", "Hindi", "2000s", 118, 0.72, ["Bollywood"], 214),
      ],
      setlist: [],
    },
    stats: {
      total_requests: 47,
      unique_sessions: 31,
      wave_count: 5,
      compression_ratio: 5 / 47,
      decisions_made: 6,
      actionability: 0.83,
      avg_interpret_ms: 340,
      llm_enabled: true,
    },
  };
}

/** Empty-state fixture: the first ten seconds a judge sees. */
export function mockEmptyState(): DashboardState {
  return {
    event_id: "default",
    waves: [],
    dj: {
      event_id: "default",
      current_track: null,
      started_at: null,
      queue: [],
      history: [],
      setlist: [],
    },
    stats: {
      total_requests: 0,
      unique_sessions: 0,
      wave_count: 0,
      compression_ratio: 0,
      decisions_made: 0,
      actionability: 0,
      avg_interpret_ms: 0,
      llm_enabled: true,
    },
  };
}

/** Raw guest phrasing for the live ticker simulation. */
export const MOCK_INCOMING: { text: string; wave_id: string; wave_label: string }[] = [
  { text: "brown munde pleaseeee", wave_id: "wave_1", wave_label: "High-Energy Punjabi" },
  { text: "we want bhangra", wave_id: "wave_1", wave_label: "High-Energy Punjabi" },
  { text: "something with dhol in it", wave_id: "wave_1", wave_label: "High-Energy Punjabi" },
  { text: "dus bahane!!", wave_id: "wave_2", wave_label: "2000s Bollywood Nostalgia" },
  { text: "play old bollywood party songs", wave_id: "wave_2", wave_label: "2000s Bollywood Nostalgia" },
  { text: "more house pls", wave_id: "wave_3", wave_label: "Peak-Time House" },
  { text: "fisher losing it", wave_id: "wave_3", wave_label: "Peak-Time House" },
  { text: "afrobeats after this one?", wave_id: "wave_4", wave_label: "Afrobeats Cooldown" },
  { text: "calm down rema", wave_id: "wave_4", wave_label: "Afrobeats Cooldown" },
  { text: "in da club for the throwback", wave_id: "wave_5", wave_label: "Throwback Hip-Hop" },
  { text: "ap dhillon anything", wave_id: "wave_1", wave_label: "High-Energy Punjabi" },
  { text: "kala chashma next!!", wave_id: "wave_2", wave_label: "2000s Bollywood Nostalgia" },
  { text: "keep it punjabi all night", wave_id: "wave_1", wave_label: "High-Energy Punjabi" },
  { text: "one kiss calvin harris", wave_id: "wave_3", wave_label: "Peak-Time House" },
];
