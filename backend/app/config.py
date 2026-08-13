"""Runtime configuration.

Everything AI-related is optional by design. CUE's interpreter is deterministic
first: with no API key present the system is fully functional offline, and a key
only upgrades interpretation quality. This is a demo-safety decision -- a live
pitch must never depend on a network round-trip.
"""

from __future__ import annotations

import os
from typing import Optional


def _flag(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


class Settings:
    # --- server ---
    host: str = os.environ.get("CUE_HOST", "0.0.0.0")
    port: int = int(os.environ.get("CUE_PORT", "8000"))
    db_path: str = os.environ.get("CUE_DB", "cue.db")
    default_event_id: str = os.environ.get("CUE_EVENT_ID", "default")

    # Public base URL encoded into the guest QR code. On a venue LAN this
    # should be the machine's IP so phones can reach it.
    public_url: Optional[str] = os.environ.get("CUE_PUBLIC_URL")

    # --- AI enhancement layer (all optional) ---
    openai_api_key: Optional[str] = os.environ.get("OPENAI_API_KEY")
    anthropic_api_key: Optional[str] = os.environ.get("ANTHROPIC_API_KEY")
    llm_model: str = os.environ.get("CUE_LLM_MODEL", "gpt-4o-mini")
    llm_timeout_s: float = float(os.environ.get("CUE_LLM_TIMEOUT", "2.5"))
    llm_enabled: bool = _flag("CUE_LLM_ENABLED", True)

    # --- clustering ---
    # Cosine distance below which two intents merge into one wave. Tuned so 50
    # chaotic requests compress to <= 5 waves (the PRD success metric) without
    # collapsing genuinely different asks together.
    cluster_threshold: float = float(os.environ.get("CUE_CLUSTER_THRESHOLD", "0.42"))
    max_waves_shown: int = int(os.environ.get("CUE_MAX_WAVES", "5"))
    momentum_window_s: float = float(os.environ.get("CUE_MOMENTUM_WINDOW", "120"))

    # --- anti-manipulation ---
    # Nth request from the same session is worth repeat_decay ** (n-1).
    repeat_decay: float = float(os.environ.get("CUE_REPEAT_DECAY", "0.45"))
    rapid_fire_window_s: float = float(os.environ.get("CUE_RAPID_WINDOW", "8"))
    rapid_fire_penalty: float = float(os.environ.get("CUE_RAPID_PENALTY", "0.25"))
    duplicate_similarity: float = float(os.environ.get("CUE_DUP_SIM", "0.82"))
    session_min_weight: float = float(os.environ.get("CUE_MIN_WEIGHT", "0.05"))

    # --- ranking ---
    candidates_per_wave: int = int(os.environ.get("CUE_CANDIDATES", "3"))
    weight_demand: float = float(os.environ.get("CUE_W_DEMAND", "0.30"))
    weight_vibe: float = float(os.environ.get("CUE_W_VIBE", "0.45"))
    weight_bridge: float = float(os.environ.get("CUE_W_BRIDGE", "0.25"))
    max_bpm_bridge: int = int(os.environ.get("CUE_MAX_BPM_BRIDGE", "16"))

    @property
    def has_llm(self) -> bool:
        return bool(
            self.llm_enabled and (self.openai_api_key or self.anthropic_api_key)
        )

    @property
    def llm_provider(self) -> Optional[str]:
        if not self.llm_enabled:
            return None
        if self.openai_api_key:
            return "openai"
        if self.anthropic_api_key:
            return "anthropic"
        return None


settings = Settings()
