# DJ-Cue — Frozen Interface Contract

Binding for the API, the Guest UI, and the DJ Dashboard.
Backend serves on `:8000`, Next.js dev server on `:3000`.

Do not change any path, field name, or type here without updating every module.

## Transport

Hosted deployment (the default): frontend and backend deploy as one Vercel
project via `vercel.json`'s `services` + path `rewrites`
(`/api/*`, `/ws/*` → backend, everything else → frontend), so a relative
path is already correct. Local dev: the browser computes the API base from
its own hostname (`http://<hostname>:8000`) when it detects a LAN address.
`NEXT_PUBLIC_API_BASE` overrides either. FastAPI enables permissive CORS.
Use `frontend/lib/api.ts` — never hand-roll a fetch.

## REST

| Method | Path | Body | Returns |
| --- | --- | --- | --- |
| GET | `/api/health` | — | `{ok, supabase, version, db}` |
| GET | `/api/config?event_id=` | — | `{event_id, guest_url, dj_status}` |
| GET | `/api/genres` | — | `{genres: Genre[]}` |
| GET | `/api/events` | — | `{events: Event[]}` |
| POST | `/api/events` | `{name}` | `Event` |
| POST | `/api/events/{id}/status` | `{status}` | `Event` |
| POST | `/api/events/{id}/pulse` | `{session_id, status}` | `PulseAck` |
| GET | `/api/catalog/search?q=&genre=&limit=` | — | `{songs: Song[]}` |
| POST | `/api/requests` | `{event_id, session_id, genre, song_title, song_artist?, song_id?, artwork_url?}` | `RequestAck` |
| GET | `/api/dashboard?event_id=` | — | `DashboardState` |
| POST | `/api/requests/{id}/status?event_id=` | `{status}` | `SongRequest` |

`status` (on requests) is one of `"queued" \| "played" \| "dismissed"`.
Setting `played` or `dismissed` is a **soft delete** — the row leaves the
dashboard's queued list but is never removed from the database, so the full
lifecycle survives for post-event analysis.

`dj_status` on events is `"open" \| "closed"`. Flipping to `"closed"` is
enforced *inside* `submit_song_request` (see below) — a guest cannot submit
while closed regardless of what the client does, and gets `RequestAck` back
with `request_id: null` and a polite `message`. Every flip is also appended
to `dj_status_log (event_id, status, changed_at)` for a timeline of when the
DJ opened/closed the floor.

`pulse` status is `"single" \| "committed"` — optional, guest-set, never
required, aggregated into `EventStats.pulse_single` / `pulse_committed` /
`pulse_total`. One vote per session per event; voting again overwrites the
same guest's prior vote. Capped at 5 real status *changes* per session per
event (re-selecting the already-active status is never counted) — enforced
inside `set_pulse_vote`, which returns `PulseAck { status, toggle_count,
limited, message }`; once `limited` is true the vote is rejected and
`message` carries a light "that's enough changing" line for the UI.

Real-tempo (`bpm`) is resolved server-side, once, at submit time, only for
a song picked from a live Deezer search result (`song_id` starting with
`deezer:`) — a direct read of Deezer's own per-track `bpm` field, never an
estimate. It has no bearing on iTunes-sourced picks or the static
"trending" seed shown before a guest starts typing, which is why `bpm` is
frequently `null` on a `SongRequest`.

## WebSocket

`ws://<host>:8000/ws/dashboard?event_id=<id>`

Server pushes `WSMessage = {type, payload, ts}`:

- `"state"` — payload is a full `DashboardState`. Sent on connect and after
  every mutation. **This is the primary channel**; a client that only handles
  `"state"` is fully correct.
- `"new_request"` — payload `{song_title, request_count, already_counted}`.
  A lightweight ping; the `"state"` frame that follows is authoritative.
- `"status_change"` — payload `{request_id, status}`.

Clients must auto-reconnect with backoff and fall back to polling
`/api/dashboard` every 3s if the socket cannot be established. A dead socket
must never leave a blank screen on the DJ's tablet.

## Types

See `frontend/lib/types.ts` — a 1:1 mirror of `backend/app/contracts.py`.
Key shapes:

```ts
Event    { id, name, slug, status, dj_status, created_at } // dj_status: "open" | "closed"
Genre    { key, label, region }              // region: "north" | "south" | "other"
Song     { id, title, artist, genre, artwork_url }
SongRequest {
  id, event_id, song_id, song_title, song_artist, genre,
  request_count, status, artwork_url, bpm, created_at, updated_at
}                                              // status: "queued" | "played" | "dismissed"
RequestAck { request_id, song_title, request_count, already_counted, message }
PulseAck { status, toggle_count, limited, message }
EventStats {
  total_requests, unique_songs, unique_sessions,
  pulse_single, pulse_committed, pulse_total
}
DashboardState { event_id, requests: SongRequest[], stats: EventStats }
```

`GENRES` includes a catch-all `{ key: "other", label: "Other genre" }` for
songs that don't fit any listed genre — it does not bias the catalog search
term the way a real genre's label does.

## Aggregation & anti-spam (server-side, not a client concern)

A guest submission never creates a duplicate row for a song that's already
queued in that event — it increments `request_count` on the existing row.
Two rules keep one phone from inflating that number:

1. **Per-song cap.** A session can contribute to a given queued request's
   count exactly once, permanently (until that row leaves `queued`).
2. **Cooldown.** A session cannot submit *anything* again for
   `CUE_SUBMIT_COOLDOWN` seconds (default 2.5) after its last submission.

Both live in the `submit_song_request` Postgres function so the whole
find-or-create-or-increment sequence is one atomic round trip — two phones
tapping the same song at the same instant cannot race each other.

## Routes

- `/` — Guest mobile web app. QR code target. Genre grid -> song search ->
  confirmation.
- `/dj` — DJ dashboard, tablet/desktop, dark. Ranked request list with
  Played/Dismiss.
- `/present` — Optional big-screen QR + live counts.

## Session identity

The guest's anonymous session id is generated client-side, stored in
`localStorage` under `cue_session_id`, and sent with every request. No
accounts, no auth — this id is the only thing the anti-spam system keys on.

## Events

Every request is tied to an `event_id` (`Event` model — e.g. "Bellevue Aug
21"), so data from different gigs never mixes. The guest's QR encodes
`?event=<id>` in its URL; if absent, the client resolves the most recently
created active event via `/api/config`.
