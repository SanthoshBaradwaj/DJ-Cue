# DJ-Cue

**A frictionless request queue for live venues: scan a QR, pick a genre, request a song. The DJ sees a ranked list instantly.**

No AI interpretation, no crowd-wave clustering, no tipping — just explicit
track requests, aggregated by how many people asked for the same song, tied
to a specific gig so data never bleeds across events.

---

## Run it

Two terminals. Requires a Supabase project (see below).

```bash
# Terminal 1 — start both servers
./scripts/dev.sh

# Terminal 2 — nothing else needed; open the URLs below
```

| Surface | URL | Who |
| --- | --- | --- |
| Guest | `http://<your-lan-ip>:3000` | Phones, via the QR |
| DJ dashboard | `http://localhost:3000/dj` | Tablet/laptop in the booth |
| Presenter (optional) | `http://localhost:3000/present` | Venue TV / projector |
| API health | `http://localhost:8000/api/health` | — |

Phones must be on the same wifi. The frontend derives the API host from its
own hostname, so scanning the QR from a phone just works.

---

## The guest flow (3-5 seconds)

1. Scan the QR. First screen is a grid of large genre buttons — Punjabi,
   Haryanvi, Bollywood, Tamil, Telugu — grouped North/South India. No typing.
2. Tap a genre. A text field appears; type a song and a dropdown of matches
   from the catalog shows up as you type.
3. Tap a match (or, if it's not in the catalog, tap "Request it anyway" to
   send the raw text). Done — the DJ's dashboard updates live.

Requesting the same song again from a *different* phone bumps its count.
Requesting it again from the *same* phone doesn't inflate the number — one
contribution per device per song, plus a short cooldown between submissions
of any kind, so a fast thumb can't manufacture demand.

## The DJ dashboard

A single ranked list, highest `request_count` at the top. Two buttons per
row: **Played** and **Dismiss** — both soft-delete the row off the dashboard
without deleting it from the database, so the full lifecycle (queued ->
played/dismissed, with timestamps) survives for post-event analysis. Events
are switchable from the top bar, and every request is scoped to one, so
"Bellevue Aug 21" and next week's gig never mix.

A **Taking requests / Not taking requests** toggle controls whether guests
can submit at all — flipping to closed is enforced inside the database
function itself, not just a label, so a guest genuinely cannot get a request
through while it's on. Every flip is timestamped in `dj_status_log` for a
timeline of when the floor was open. Guests can also optionally set a
"single & ready to talk" vs "committed" pulse from a small slider on their
home screen; the DJ dashboard and presenter screen show the aggregate split
once anyone has voted — it's a vibe signal, not a request.

---

## Setting up Supabase

DJ-Cue has **no in-memory or SQLite fallback** — every request is written to
Postgres via Supabase so a set survives the laptop restarting mid-night.

1. Create a project at [supabase.com](https://supabase.com) (or reuse one).
2. Apply the schema: the three migrations under a fresh project should create
   `events`, `songs`, `requests`, `request_taps`, and the
   `submit_song_request` function. If you're setting this up from scratch,
   the SQL lives in the migration history of the project this was built
   against — recreate it with the Supabase SQL editor or CLI, or ask an
   agent with Supabase MCP access to replay it.
3. Copy `.env.example` to `.env` and fill in `SUPABASE_URL` and
   `SUPABASE_ANON_KEY` from your project's API settings.
4. `./scripts/dev.sh` — the backend refuses to boot cleanly without these.

There are no user accounts in this product (guests are anonymous session
ids, the DJ dashboard has no login), so the backend talks to Supabase over
the anon/publishable key with row-level security enabled and permissive
policies — the same trust model as the API's own fully-open CORS.

---

## How aggregation works

One row per distinct song per event. A duplicate submission doesn't create a
second row — it increments `request_count` on the existing one. The whole
find-or-create-or-increment sequence runs as a single Postgres function
(`submit_song_request`) so two phones tapping the same song in the same
instant can't race each other into two rows or a lost increment.

Two rules stop one person from gaming the number:

- **Per-song cap** — a session (device) can contribute to a given request's
  count exactly once, enforced by a unique constraint on
  `(request_id, session_id)`, not just a time window.
- **Cooldown** — a session can't submit *anything* again for
  `CUE_SUBMIT_COOLDOWN` seconds (default 2.5) after its last submission.

See `CONTRACT.md` for the full API surface.

---

## Layout

```
backend/app/
  contracts.py         Pydantic models -- Event, Song, SongRequest, ...
  db.py                Supabase-backed store (find/create/increment, soft delete)
  genres.py            the genre buttons shown to guests
  events.py            in-process pub/sub feeding the dashboard websocket
  api/service.py        wires db.py to the websocket
  main.py               FastAPI routes
frontend/app/
  page.tsx              guest entry point
  components/guest/     GenreGrid -> SongSearch -> Confirmation
  dj/page.tsx            DJ dashboard
  components/dj/         TopBar, EventSwitcher, RequestRow, live feed hook
  present/                optional big-screen QR + live counts
scripts/
  dev.sh                 start both servers, load .env
```

## Tests

```bash
cd backend && python3 -m pytest -q     # route + validation tests against a fake service
cd frontend && npx tsc --noEmit        # clean
```

The core aggregation/dedupe/cooldown logic lives in the `submit_song_request`
Postgres function and is exercised directly against the database — see
`CONTRACT.md` for the behavioural contract it implements.

## Out of scope

No LLM interpretation, no crowd-wave clustering, no two-sided setlist
insertion, no tipping or payment mechanism, no streaming integration
(Tidal/Serato), no accounts. This is a request queue, not a mixing
co-pilot — DJ-Cue surfaces demand; the DJ decides what to play.
