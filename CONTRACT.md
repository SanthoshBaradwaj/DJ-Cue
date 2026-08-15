# DJ-Cue — Frozen Interface Contract

Binding for the API, the Guest UI, and the DJ Dashboard.
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
| GET | `/api/health` | — | `{ok, supabase, version}` |
| GET | `/api/config?event_id=` | — | `{event_id, guest_url}` |
| GET | `/api/genres` | — | `{genres: Genre[]}` |
| GET | `/api/events` | — | `{events: Event[]}` |
| POST | `/api/events` | `{name}` | `Event` |
| GET | `/api/catalog/search?q=&genre=&limit=` | — | `{songs: Song[]}` |
| POST | `/api/requests` | `{event_id, session_id, genre, song_title, song_artist?, song_id?}` | `RequestAck` |
| GET | `/api/dashboard?event_id=` | — | `DashboardState` |
| POST | `/api/requests/{id}/status?event_id=` | `{status}` | `SongRequest` |

`status` is one of `"queued" \| "played" \| "dismissed"`. Setting `played` or
`dismissed` is a **soft delete** — the row leaves the dashboard's queued list
but is never removed from the database, so the full lifecycle survives for
post-event analysis.

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
Event    { id, name, slug, status, created_at }
Genre    { key, label, region }              // region: "north" | "south"
Song     { id, title, artist, genre }
SongRequest {
  id, event_id, song_id, song_title, song_artist, genre,
  request_count, status, created_at, updated_at
}                                              // status: "queued" | "played" | "dismissed"
RequestAck { request_id, song_title, request_count, already_counted, message }
EventStats { total_requests, unique_songs, unique_sessions }
DashboardState { event_id, requests: SongRequest[], stats: EventStats }
```

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
