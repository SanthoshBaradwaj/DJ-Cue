"""Runtime configuration.

DJ-Cue is a frictionless request queue: a guest picks a genre, picks (or
types) a song, and it lands on the DJ's dashboard. Everything here is either
server transport or the two anti-spam knobs -- there is no AI layer to
configure.
"""

from __future__ import annotations

import os
from typing import Optional


class Settings:
    # --- server ---
    host: str = os.environ.get("CUE_HOST", "0.0.0.0")
    port: int = int(os.environ.get("CUE_PORT", "8000"))

    # Public base URL encoded into the guest QR code. On a venue LAN this
    # should be the machine's IP so phones can reach it.
    public_url: Optional[str] = os.environ.get("CUE_PUBLIC_URL")

    # --- Supabase (system of record) ---
    supabase_url: Optional[str] = os.environ.get("SUPABASE_URL")
    # The anon/publishable key. There are no user accounts in this product --
    # guests are anonymous session ids and the DJ dashboard has no login --
    # so the backend talks to Supabase the same way a trusted client would,
    # with RLS policies scoped to what this app actually needs.
    supabase_key: Optional[str] = os.environ.get("SUPABASE_ANON_KEY") or os.environ.get(
        "SUPABASE_KEY"
    )

    # --- anti-spam ---
    # A session cannot submit *anything* again within this window -- stops a
    # fast thumb from firing off five requests in two seconds.
    submit_cooldown_s: float = float(os.environ.get("CUE_SUBMIT_COOLDOWN", "2.5"))

    @property
    def has_supabase(self) -> bool:
        return bool(self.supabase_url and self.supabase_key)


settings = Settings()
