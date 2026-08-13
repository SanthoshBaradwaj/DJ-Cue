# CUE — Frozen Interface Contract

Binding for M4 (API), M5 (Guest UI), M6 (DJ Dashboard), M7 (Demo harness).
Backend serves on `:8000`, Next.js dev server on `:3000`.

Do not change any path, field name, or type here without updating every module.

## Transport

The browser computes the API base at runtime from its own hostname
(`http://<hostname>:8000`), so a phone that opens `http://192.168.1.5:3000`
automatically talks to `http://192.168.1.5:8000`. FastAPI enables permissive
CORS. Use `frontend/lib/api.ts` — never hand-roll a fetch.

## REST

| Method | Path | Body | Returns |
| --- | --- | --- | --- |
| GET | `/api/health` | — | `{ok, llm_enabled, track_count, version}` |
| GET | `/api/config` | — | `{event_id, guest_url, llm_enabled}` |
| POST | `/api/requests` | `{text, session_id?, event_id?}` | `RequestAck` |
| GET | `/api/dashboard?event_id=` | — | `DashboardState` |
| POST | `/api/decisions` | `{track_id, action, wave_id?, event_id?}` | `{ok, dj: DJState}` |
| GET | `/api/catalog/search?q=&limit=` | — | `{tracks: Track[]}` |
| GET | `/api/stats?event_id=` | — | `EventStats` |
| POST | `/api/demo/seed` | `{count?, event_id?, delay_ms?}` | `{ok, seeded}` |
| POST | `/api/demo/reset` | `{event_id?}` | `{ok}` |

`action` is one of `"play" | "later" | "skip"`.

## WebSocket

`ws://<host>:8000/ws/dashboard?event_id=default`

Server pushes `WSMessage = {type, payload, ts}`:

- `"state"` — payload is a full `DashboardState`. Sent on connect and after
  every mutation. **This is the primary channel**; a client that only handles
  `"state"` is fully correct.
- `"request"` — payload `{text, wave_label, wave_id, session_id}`. A lightweight
  ping for the live ticker animation, sent just before the `"state"` that
  includes it.
- `"decision"` — payload `{action, track, wave_id}`.
- `"now_playing"` — payload `{track}` (or `{track: null}`).

Clients must auto-reconnect with backoff and fall back to polling
`/api/dashboard` every 3s if the socket cannot be established. A dead socket
must never leave a blank screen on stage.

## Types

See `frontend/lib/types.ts` — a 1:1 mirror of `backend/app/contracts.py`.
Key shapes:

```ts
Intent   { languages, genres, moods, artists, eras, energy_target,
           danceability, familiarity, tempo_hint, confidence, source,
           raw_keywords, summary }
Wave     { id, event_id, label, summary, centroid, request_ids, raw_count,
           unique_sessions, weight, momentum, share, top_keywords,
           sample_texts, created_at, updated_at }
Track    { id, title, artist, language, genres, moods, era, bpm, energy,
           danceability, popularity, duration_sec, audio_file, tags }
Candidate{ track, score, demand_score, vibe_score, bridge_score, bpm_delta,
           reasons }
WaveView { wave, candidates }
DJState  { event_id, current_track, started_at, queue, history }
DashboardState { event_id, waves: WaveView[], dj, stats }
EventStats { total_requests, unique_sessions, wave_count, compression_ratio,
             decisions_made, actionability, avg_interpret_ms, llm_enabled }
RequestAck { request_id, session_id, message, intent_summary, wave_id,
             wave_label, wave_size, joined_existing_wave }
```

## Routes

- `/` — Guest mobile web app (M5). QR code target.
- `/dj` — DJ dashboard, tablet/desktop, dark (M6).
- `/present` — Big-screen QR + live stats for the pitch (M7).

## Session identity

The guest's anonymous session id is generated client-side, stored in
`localStorage` under `cue_session_id`, and sent with every request. No accounts,
no auth — this id is the only thing the anti-manipulation system keys on.
