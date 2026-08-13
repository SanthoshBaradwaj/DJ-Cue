# CUE

**Turns a room full of shouted song requests into a handful of decisions a DJ can act on — slotted into the set he already planned.**

Fifty people asking for fifty different things becomes four or five *Crowd Waves*. Each wave gets placed at a specific point in the DJ's existing setlist, judged against the track before it **and** the track after it. Guests can put money behind a request; the DJ only gets paid if he actually plays it.

---

## Run the demo from a clean slate

Two terminals. Nothing to configure, no API key needed.

```bash
# Terminal 1 — start both servers
./scripts/dev.sh

# Terminal 2 — run the party
python3 scripts/demo_party.py
```

`demo_party.py` walks the whole product loop end to end:

1. Imports the DJ's set from [`data/setlist.txt`](data/setlist.txt)
2. 20 **distinct** phones submit in their own words — Hinglish, emoji, negation, vagueness
3. One guy spams the same request 10× from one phone and **fails** to manufacture a wave
4. CUE proposes where each crowd wave belongs *inside* the DJ's plan
5. Two guests tip specific songs
6. The DJ accepts a slot, plays it, and one tip settles — the other is released, uncharged

Add `--fast` to skip the pauses.

| Surface | URL | Who |
| --- | --- | --- |
| Guest | `http://<your-lan-ip>:3000` | Phones, via the QR |
| DJ dashboard | `http://localhost:3000/dj` | Tablet/laptop in the booth |
| Presenter | `http://localhost:3000/present` | The big screen |
| API health | `http://localhost:8000/api/health` | — |

Phones must be on the same wifi. The frontend derives the API host from its own hostname, so scanning the QR from a phone just works.

**Reset between runs:** `curl -X POST localhost:8000/api/demo/reset -H 'content-type: application/json' -d '{}'`

---

## Using the DJ's own playlist

The set lives in **[`data/setlist.txt`](data/setlist.txt)**, not in code. Paste in his exported history:

```
00:54:53  Buzz - Badshah - Aastha Gill
00:56:27  Uyi Amma
00:57:10  Tauba Tauba Bad Newz
00:58:10  JAWAN Chaleya
00:59:09  Jhoome Jo Pathaan
01:00:05  Akhiyaan Gulaab
01:00:59  Garmi
```

Format is `HH:MM:SS  Title`. Extra words are fine — `"JAWAN Chaleya"` and `"Tauba Tauba Bad Newz"` both resolve correctly.

**Every track named here must exist in the catalog** (`backend/app/catalog/library.py`). A title that can't be resolved *confidently* is reported as `unmatched` rather than guessed at — deliberately. The catalog's fuzzy search will match `"Zzzz Not A Real Song"` to `"Not Like Us"` on the shared word "not", and a wrong song in the set means every insertion around it gets scored against neighbours the DJ isn't actually playing. Silent wrong data is worse than an honest miss.

To add a track, copy an existing `_t(...)` row in `library.py`. **BPM and energy drive slot scoring directly** — if you have real values from Rekordbox or Serato, use those. The five tracks added for this DJ's set carry estimates, marked as such in the file.

---

## Adding an LLM API key

**Entirely optional.** CUE's interpreter is deterministic-first: a curated music-domain lexicon (769 entries — artists, song titles, genre slang, Hinglish, emoji, negation) handles interpretation with no network call, in under a millisecond. An LLM only *enhances* it, behind a hard timeout with silent fallback. A dropped venue wifi cannot break the demo.

### 1. Open `.env`

It's already in the repo root (copy `.env.example` if missing). Paste your key on line 12:

```bash
ANTHROPIC_API_KEY=sk-ant-...
```

Or use OpenAI instead:

```bash
OPENAI_API_KEY=sk-...
```

> If **both** are set, OpenAI wins. Leave the one you don't want blank.

### 2. Restart

```bash
./scripts/dev.sh
```

### 3. Confirm it took

The startup line tells you:

```
Loaded .env (LLM key found — enhancement layer will be active)
```

And `/api/health` flips over:

```bash
curl -s localhost:8000/api/health
# {"ok":true,"llm_enabled":true,"llm_provider":"anthropic", ...}
```

If it still says `llm_enabled:false`, the key didn't reach the process. `.env` is read by `scripts/dev.sh` **before** Python starts, because `app/config.py` reads `os.environ` at import time — a key exported into an already-running server is invisible to it. Restart rather than re-export.

### Choosing a model

Default is **`claude-haiku-4-5`**, and that's a latency decision, not a cost one. Interpretation runs on the ingest path with a hard 2.5s budget paid on *every* submission. A model that pauses to think will miss the deadline, silently fall back to the rules engine, and bill you for nothing.

For more nuance on messy Hinglish, raise both together in `.env`:

```bash
CUE_LLM_MODEL=claude-sonnet-5
CUE_LLM_TIMEOUT=8
```

**`.env` is gitignored.** Never commit it. `.env.example` is the template that is committed.

---

## How it works

```
guest text ──▶ M1 Interpreter ──▶ Intent (42-dim)
                                     │
                                     ▼
                            M2 Wave Clustering ──▶ Crowd Waves
                                     │                  │
                                     ▼                  ▼
                            M3 Ranker ──▶ M3b Insertion ◀── the DJ's setlist
                                                     │
                                                     ▼
                                            M4 WebSocket ──▶ DJ Dashboard
```

### We cluster structured intent, not raw text

`"Diljit"`, `"bhangra pls"`, `"we need dhol RIGHT NOW"` and `"punjabi wedding chaos"` share almost no words. A naive text embedding scatters them across four clusters. M1 first projects every request into a 42-dimensional intent space (language × genre × mood × era × energy/danceability/familiarity), and M2 clusters *there* — so those four land on nearly the same point and form one wave.

It also makes the result explainable on stage: every wave shows the actual words people typed underneath the label it derived.

### Insertion is two-sided

A slot in a planned set has two neighbours, so a candidate has to survive both:

```
... Chaleya (105) ──▶ [ the crowd wants this ] ──▶ Jhoome Jo Pathaan (122) ...
                   ^                            ^
                   bridge_out                   bridge_in
```

`Garmi` mixes beautifully out of Chaleya (0.91) and collides into Jhoome (0.30, +22 BPM). A one-sided score rates it **best of three at 0.61**; the two-sided score correctly drops it to 0.45.

The two sides combine with a **harmonic** mean, not an average — `mean(1.0, 0.2)` and `mean(0.6, 0.6)` both give 0.6, which would call a train wreck equivalent to two decent transitions. `H(1.0, 0.2) = 0.33`.

CUE places; **the DJ mixes.** The dashboard shows a bare BPM delta on each edge and nothing more — no transition score. He's the one orchestrating it.

### Tips settle ties, and only pay on delivery

A tip **never adds score.** Proposals are grouped into bands of near-equal score (`TIE_BAND = 0.04`) and tips only order *within* a band. Money resolves a coin-flip; it cannot buy a worse mix. `test_a_tip_cannot_leapfrog_a_clearly_better_fit` holds ₹5000 against a better placement and asserts the money loses.

Payout is conditional:

| State | Meaning |
| --- | --- |
| `pending` | Authorised, nothing charged. Accepting into the set does **not** settle it — a set can still change. |
| `captured` | The song played. The DJ earned it. |
| `released` | Set ended, song never played. Guest is not charged. |

### Anti-manipulation

Every count the DJ sees is unique anonymous sessions. Rapid-fire and near-duplicate requests from one device are heavily discounted — never rejected, the guest still gets a warm ack. One person with a fast thumb cannot manufacture a wave.

### No API key, no torch

The interpreter is deterministic-first (above). Clustering is scikit-learn agglomerative over cosine distance in the structured intent space — instant, deterministic, zero download. The PRD suggested `all-MiniLM`, but that pulls ~2GB of transformers for a similarity function the intent space gives us more cheaply and more controllably.

### Audio with no assets

The dashboard synthesises a loop per track in the browser (WebAudio), parameterised by that track's own BPM, energy and genre — so a bhangra pick reads as dhol-and-minor-pentatonic and a house pick as four-on-the-floor. Deterministic per track id. Drop an MP3 into `audio/` and the backend matches it by filename and plays the real thing instead. Either way a PLAY decision is an 8-second crossfade, never a cut.

---

## Layout

```
data/setlist.txt      the DJ's set — edit this, not code
backend/app/
  taxonomy.py         canonical vocabularies + vector-space layout
  contracts.py        every cross-module type
  vectors.py          intent projection, similarity, wave labelling
  store.py            in-memory authority + SQLite mirror
  interpreter/        M1  text -> Intent (rules + optional LLM)
  clustering/         M2  waves + anti-manipulation
  catalog/            M3  library + ranker
    insertion.py      M3b two-sided setlist placement
    audio.py          match drop-in files to tracks
  api/service.py      M4  service layer
frontend/app/
  page.tsx            M5  guest
  dj/                 M6  DJ dashboard
  components/dj/
    SetPanel.tsx      the set, with crowd requests slotted in
    audioEngine.ts    two decks + crossfade + synth
  present/            M7  presenter screen
scripts/
  dev.sh              start both servers, load .env
  demo_party.py       the end-to-end multi-guest demo
```

## Tests

```bash
cd backend && python3 -m pytest -q     # 149 passed, 1 xfailed
cd frontend && npx tsc --noEmit        # clean
```

`tests/test_integration.py` is the gate — it drives the real pipeline with the real corpus and asserts the headline metrics. `tests/test_setlist.py` covers insertion and the tip lifecycle.

## Configuration

All optional. See `backend/app/config.py`.

| Variable | Default | Effect |
| --- | --- | --- |
| `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` | unset | Enables the LLM enhancement layer |
| `CUE_LLM_MODEL` | `claude-haiku-4-5` | Interpretation model |
| `CUE_LLM_TIMEOUT` | `2.5` | Seconds before falling back to rules |
| `CUE_CLUSTER_THRESHOLD` | `0.42` | Lower = more, tighter waves |
| `CUE_MAX_WAVES` | `5` | Hard cap on waves shown |
| `CUE_MERGE_FLOOR` | `0.55` | Min similarity to allow a merge under the cap |
| `CUE_AUDIO_DIR` | `audio/` | Where drop-in audio is looked for |
| `CUE_PUBLIC_URL` | auto | Overrides the URL in the QR |

## Known limitations

- **Cycled-corpus purity.** Seeding past ~145 requests without a reset lets the intentionally-vague "noise" bucket bridge unrelated clusters into one `Mixed Requests` card. Root cause and why a similarity gate can't fix it: `test_waves_stay_pure_when_the_corpus_cycles` (a strict `xfail`, so it fails loudly if someone accidentally fixes it).
- **Proposals cluster at one slot.** Each candidate independently picks its best gap and they often agree, so several stack above the same track.
- **Single-instance only.** The store is in-memory-authoritative with SQLite as a mirror, and the skip list lives on the service object. Two instances behind a load balancer would hold different events. Horizontal hosting needs the store to become the authority first.
- **Catalog is hand-curated** (218 tracks). The intended fix is to import the DJ's actual library — real analysed BPMs, and everything in it is guaranteed playable.

## Out of scope

No streaming integration, no camera/mic, no accounts, no Rekordbox/Serato hooks. Tipping is a **mechanism only** — state transitions and UI, no payment provider, no money actually moves.
