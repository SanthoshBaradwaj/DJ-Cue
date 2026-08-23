"""Runtime configuration.

DJ-Cue is a frictionless request queue: a guest picks a genre, picks (or
types) a song, and it lands on the DJ's dashboard. Everything here is either
server transport or the two anti-spam knobs -- there is no AI layer to
configure.
"""

from __future__ import annotations

import os
from typing import Optional


# Fallback Supabase project for the hosted deployment. The anon/publishable
# key is *meant* to be public -- Supabase's own docs say so -- it is rate
# limited and every table it can touch sits behind the RLS policies applied
# in the schema migration, the same trust boundary as this API's wide-open
# CORS. Baking it in means `./scripts/dev.sh` and a from-scratch Vercel
# deploy both work with zero env-var setup; SUPABASE_URL / SUPABASE_ANON_KEY
# still override it for anyone pointing at their own project.
_FALLBACK_SUPABASE_URL = "https://tzgvqffgndsntptylpbq.supabase.co"
_FALLBACK_SUPABASE_ANON_KEY = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InR6Z3ZxZmZnbmRzbnRwdHlscGJxIiwicm9sZSI6ImFub24iLCJpYXQi"
    "OjE3ODY3NTEyMjIsImV4cCI6MjEwMjMyNzIyMn0.3yttF43VxVIJi1VQD_jbuJE2p0V9p_hzG6xTSDvSkyE"
)


class Settings:
    # --- server ---
    host: str = os.environ.get("CUE_HOST", "0.0.0.0")
    port: int = int(os.environ.get("CUE_PORT", "8000"))

    # Public base URL encoded into the guest QR code. On a venue LAN this
    # should be the machine's IP so phones can reach it.
    public_url: Optional[str] = os.environ.get("CUE_PUBLIC_URL")

    # --- Supabase (system of record) ---
    supabase_url: Optional[str] = os.environ.get("SUPABASE_URL") or _FALLBACK_SUPABASE_URL
    # There are no user accounts in this product -- guests are anonymous
    # session ids and the DJ dashboard has no login -- so the backend talks
    # to Supabase the same way a trusted client would, with RLS policies
    # scoped to what this app actually needs.
    supabase_key: Optional[str] = (
        os.environ.get("SUPABASE_ANON_KEY")
        or os.environ.get("SUPABASE_KEY")
        or _FALLBACK_SUPABASE_ANON_KEY
    )

    # --- anti-spam ---
    # A session cannot submit *anything* again within this window -- stops a
    # fast thumb from firing off five requests in two seconds.
    submit_cooldown_s: float = float(os.environ.get("CUE_SUBMIT_COOLDOWN", "2.5"))

    # --- operator PIN ---
    # There are no accounts anywhere in this app -- guests are anonymous and
    # the DJ dashboard never had a login either -- but /dj and /present are
    # both reachable by anyone with the URL, and /present in particular can
    # flush an event's live data. This one shared PIN (not a per-person
    # account, there's only ever one operator) gates the dashboard pages
    # client-side and every DJ-only write server-side, so finding the API
    # path in devtools doesn't bypass it. "3006" is an explicit placeholder
    # -- override with CUE_OPERATOR_PIN before a real event.
    operator_pin: str = os.environ.get("CUE_OPERATOR_PIN", "3006")

    @property
    def has_supabase(self) -> bool:
        return bool(self.supabase_url and self.supabase_key)


settings = Settings()
