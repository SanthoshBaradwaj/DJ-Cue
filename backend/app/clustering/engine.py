"""Crowd wave clustering (M2).

Fifty people type fifty different things. The DJ can read five. This module is
the compression: it projects every request into the shared intent space from
``app.vectors``, clusters them, and emits at most ``settings.max_waves_shown``
waves with the receipts attached (raw count, honest unique-device count,
anti-manipulation weight, sample texts).

Two properties matter as much as the clustering itself:

* **The engine never raises.** It sits on the ingest path of a live event. If
  sklearn is missing, unhappy, or handed a degenerate matrix, we fall back to a
  greedy nearest-centroid pass and keep the floor moving.
* **Wave ids are stable across recomputes.** The dashboard is a live surface a
  DJ is reading mid-set; a wave whose membership largely persists keeps its id
  (and its ``created_at``) so cards do not shuffle or flicker under their eyes.
"""

from __future__ import annotations

import logging
import os
import threading
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from .. import taxonomy, vectors
from ..config import settings
from ..contracts import Intent, SongRequest, Wave, now_ts
from .antimanip import compute_weight

log = logging.getLogger("cue.clustering")

# Minimum Jaccard overlap (over request ids) for a new cluster to be considered
# "the same wave" as one from the previous recompute.
_ID_REUSE_JACCARD = 0.3

# Minimum centroid cosine similarity for two clusters to be allowed to merge
# when squeezing down to the display cap. This is the guard that keeps the cap
# from manufacturing a soup wave: a floor of 0.55 sits comfortably above the
# 0.58 similarity implied by ``cluster_threshold``, so same-family clusters
# (four separate house asks) still coalesce while a bhangra cluster is never
# fused into a Latin one just to hit a number. See ``_enforce_cap``.
MERGE_FLOOR = float(os.environ.get("CUE_MERGE_FLOOR", "0.55"))

_EPSILON = 1e-8

# sklearn costs seconds to import on a cold interpreter. Paying that on the
# first guest's submission would blow the ingest budget in the worst possible
# moment, so it is imported once and memoised here (and warmed at engine
# construction, i.e. at server boot).
_SKLEARN_UNLOADED = object()
_agglomerative = _SKLEARN_UNLOADED


def _load_agglomerative():
    """Return ``AgglomerativeClustering`` or ``None`` if sklearn is unusable."""
    global _agglomerative
    if _agglomerative is _SKLEARN_UNLOADED:
        try:
            from sklearn.cluster import AgglomerativeClustering

            _agglomerative = AgglomerativeClustering
            try:
                # A throwaway fit drags scipy's hierarchy module in now rather
                # than during the first real cluster.
                AgglomerativeClustering(
                    n_clusters=None, distance_threshold=0.5, linkage="average"
                ).fit(np.array([[0.0, 1.0], [1.0, 0.0], [0.9, 0.1]]))
            except Exception:  # pragma: no cover - warm-up is best effort
                pass
        except Exception as exc:  # pragma: no cover - env without sklearn
            log.warning("sklearn unavailable (%s); clustering will run greedy", exc)
            _agglomerative = None
    return _agglomerative


class WaveEngine:
    """Clusters an event's requests into waves. One instance per process."""

    def __init__(self, store) -> None:
        self.store = store
        # request_id -> intent vector. Re-embedding the whole history on every
        # submission is what would blow the ingest latency budget at 200
        # accumulated requests, so we never do it twice for the same request.
        self._vector_cache: Dict[str, np.ndarray] = {}
        self._lock = threading.RLock()
        _load_agglomerative()  # warm the import here, not on the ingest path

    # -- public API ---------------------------------------------------------

    def ingest(
        self,
        event_id: str,
        session_id: str,
        text: str,
        intent: Intent,
    ) -> Tuple[SongRequest, Wave, bool]:
        """Persist one guest submission and fold it into the wave map.

        Returns ``(request, wave, joined_existing_wave)`` -- the last flag is
        what powers "you just joined 11 others asking for this" in the guest
        acknowledgement, so it must mean *the wave existed before you*.
        """
        now = now_ts()
        safe_intent = _safe_sanitize(intent)

        prior = self.store.session_requests(event_id, session_id) if session_id else []
        weight, reason = compute_weight(prior, text or "", safe_intent, now)

        request = SongRequest(
            event_id=event_id,
            session_id=session_id or "",
            text=text or "",
            intent=safe_intent,
            weight=weight,
            discount_reason=reason,
            created_at=now,
        )

        known_wave_ids = {w.id for w in self.store.waves(event_id)}
        self.store.add_request(request)

        waves = self.recompute(event_id)
        wave = next((w for w in waves if request.id in w.request_ids), None)
        if wave is None:  # pragma: no cover - defensive; recompute owns every request
            wave = self._build_wave(event_id, [request], [self._vector_for(request)], now)
        joined_existing = wave.id in known_wave_ids
        return request, wave, joined_existing

    def recompute(self, event_id: str) -> List[Wave]:
        """Re-cluster the event from scratch and persist the result."""
        with self._lock:
            try:
                waves = self._recompute_unsafe(event_id)
            except Exception:  # pragma: no cover - the floor keeps moving
                log.exception("wave recompute failed for event %s", event_id)
                return self.waves(event_id)
        return waves

    def waves(self, event_id: str) -> List[Wave]:
        """Cached waves, heaviest first."""
        return sorted(
            self.store.waves(event_id), key=lambda w: (-w.weight, -w.raw_count, w.id)
        )

    def dominant(self, event_id: str) -> Optional[Wave]:
        current = self.waves(event_id)
        return current[0] if current else None

    # -- clustering ---------------------------------------------------------

    def _recompute_unsafe(self, event_id: str) -> List[Wave]:
        requests = self.store.requests(event_id)
        if not requests:
            self.store.set_waves(event_id, [])
            return []

        now = now_ts()
        matrix = np.vstack([self._vector_for(r) for r in requests])
        labels = self._cluster(matrix)

        groups: Dict[int, List[int]] = {}
        for index, label in enumerate(labels):
            groups.setdefault(int(label), []).append(index)

        weights = np.array([max(0.0, float(r.weight)) for r in requests], dtype=np.float64)
        clusters = self._enforce_cap(list(groups.values()), matrix, weights)

        waves: List[Wave] = []
        for members in clusters:
            waves.append(
                self._build_wave(
                    event_id,
                    [requests[i] for i in members],
                    [matrix[i] for i in members],
                    now,
                )
            )

        self._reuse_wave_ids(waves, self.store.waves(event_id))
        _dedupe_labels(waves)

        total = sum(w.weight for w in waves)
        for wave in waves:
            wave.share = (wave.weight / total) if total > 0 else 0.0
            wave.summary = _summarize(wave)

        waves.sort(key=lambda w: (-w.weight, -w.raw_count, w.id))

        self.store.set_waves(event_id, waves)
        mapping = {rid: w.id for w in waves for rid in w.request_ids}
        # A request whose cluster was left unshown by the cap must not keep
        # pointing at the wave it was in on an earlier recompute -- that stale
        # id would survive as a phantom membership on the presenter ticker.
        for request in requests:
            mapping.setdefault(request.id, "")
        if mapping:
            self.store.update_request_waves(event_id, mapping)

        # Drop cache entries for requests that no longer exist (event reset).
        live = {r.id for r in requests}
        for stale in [k for k in self._vector_cache if k not in live]:
            self._vector_cache.pop(stale, None)

        return waves

    def _cluster(self, matrix: np.ndarray) -> List[int]:
        """Agglomerative clustering, with a greedy fallback that cannot fail."""
        n = int(matrix.shape[0])
        if n < 2:
            return [0] * n
        AgglomerativeClustering = _load_agglomerative()
        if AgglomerativeClustering is None:
            return self._greedy_cluster(matrix)
        try:
            try:
                # sklearn >= 1.4 spells it ``metric``...
                model = AgglomerativeClustering(
                    n_clusters=None,
                    distance_threshold=settings.cluster_threshold,
                    metric="cosine",
                    linkage="average",
                )
                labels = model.fit_predict(matrix)
            except TypeError:
                # ...older releases spell it ``affinity``.
                model = AgglomerativeClustering(
                    n_clusters=None,
                    distance_threshold=settings.cluster_threshold,
                    affinity="cosine",
                    linkage="average",
                )
                labels = model.fit_predict(matrix)
            return [int(x) for x in labels]
        except Exception as exc:
            log.warning("sklearn clustering unavailable (%s); using greedy fallback", exc)
            return self._greedy_cluster(matrix)

    def _greedy_cluster(self, matrix: np.ndarray) -> List[int]:
        """Single-pass nearest-centroid assignment against the same threshold."""
        labels: List[int] = []
        sums: List[np.ndarray] = []
        counts: List[int] = []
        for i in range(int(matrix.shape[0])):
            row = matrix[i]
            best, best_sim = -1, -1.0
            for k in range(len(sums)):
                sim = vectors.cosine(row, sums[k] / counts[k])
                if sim > best_sim:
                    best, best_sim = k, sim
            if best >= 0 and (1.0 - best_sim) <= settings.cluster_threshold:
                sums[best] = sums[best] + row
                counts[best] += 1
                labels.append(best)
            else:
                sums.append(np.array(row, dtype=np.float64))
                counts.append(1)
                labels.append(len(sums) - 1)
        return labels

    def _enforce_cap(
        self,
        clusters: List[List[int]],
        matrix: np.ndarray,
        weights: np.ndarray,
    ) -> List[List[int]]:
        """Reduce to at most ``max_waves_shown`` clusters without inventing soup.

        50 raw requests -> <= 5 waves is the headline metric, so the cap is
        hard. But a cap enforced by merging unconditionally is worse than no
        cap: merging the lightest cluster into its *nearest* neighbour is only
        semantic while something genuinely near exists. Once it doesn't, each
        forced merge drags the target centroid further off, the next victim is
        then closest to that same drifting blob, and one wave becomes a garbage
        collector labelled "Mixed Requests" -- which is precisely the soup the
        product claims to eliminate.

        So the squeeze happens in two phases:

        1. **Merge honestly.** Fold the lightest cluster into its nearest
           neighbour only while that neighbour is at least ``MERGE_FLOOR``
           similar. This is what collapses four separate house asks into one
           house wave.
        2. **Then truncate.** If the event genuinely contains more distinct
           families than the DJ can read, keep the heaviest ``cap`` and let the
           long tail go unshown rather than smearing it across the survivors.
           The tail is still stored, still counted in ``total_requests``, and
           still scrolls on the presenter ticker -- it just isn't promoted to a
           card the DJ is asked to act on.
        """
        cap = max(1, int(settings.max_waves_shown))
        survivors = [list(c) for c in clusters if c]

        while len(survivors) > cap:
            centroids = [_mean(matrix, c) for c in survivors]
            order = sorted(
                range(len(survivors)),
                key=lambda i: (float(weights[survivors[i]].sum()), len(survivors[i])),
            )
            merged = False
            # The lightest cluster is the preferred victim, but if it has no
            # honest home the next-lightest may, so keep looking before giving
            # up on merging altogether.
            for victim in order:
                target, best_sim = -1, -2.0
                for i in range(len(survivors)):
                    if i == victim:
                        continue
                    sim = vectors.cosine(centroids[victim], centroids[i])
                    if sim > best_sim:
                        target, best_sim = i, sim
                if target >= 0 and best_sim >= MERGE_FLOOR:
                    survivors[target] = survivors[target] + survivors[victim]
                    survivors.pop(victim)
                    merged = True
                    break
            if not merged:
                break

        if len(survivors) > cap:
            survivors.sort(
                key=lambda c: (-float(weights[c].sum()), -len(c), c[0])
            )
            dropped = survivors[cap:]
            log.info(
                "event has %d distinct families; showing heaviest %d, %d "
                "request(s) left unshown",
                len(survivors),
                cap,
                sum(len(c) for c in dropped),
            )
            survivors = survivors[:cap]
        return survivors

    # -- wave construction --------------------------------------------------

    def _build_wave(
        self,
        event_id: str,
        members: List[SongRequest],
        member_vectors: Sequence[np.ndarray],
        now: float,
    ) -> Wave:
        centroid_intent = vectors.centroid([r.intent for r in members])
        mean_vector = np.mean(np.vstack(list(member_vectors)), axis=0)

        weight = float(sum(max(0.0, r.weight) for r in members))
        recent = float(
            sum(
                max(0.0, r.weight)
                for r in members
                if (now - r.created_at) <= settings.momentum_window_s
            )
        )

        keywords: Dict[str, int] = {}
        for request in members:
            for keyword in request.intent.raw_keywords:
                token = str(keyword).strip().lower()
                if token:
                    keywords[token] = keywords.get(token, 0) + 1
        top_keywords = sorted(keywords, key=lambda k: (-keywords[k], k))[:6]

        return Wave(
            event_id=event_id,
            label=vectors.label_for(centroid_intent),
            centroid=centroid_intent,
            request_ids=[r.id for r in members],
            raw_count=len(members),
            unique_sessions=len({r.session_id for r in members if r.session_id}),
            weight=weight,
            momentum=(recent / weight) if weight > 0 else 0.0,
            top_keywords=top_keywords,
            sample_texts=_sample_texts(members, member_vectors, mean_vector),
            created_at=min(r.created_at for r in members),
            updated_at=now,
        )

    def _reuse_wave_ids(self, waves: List[Wave], previous: List[Wave]) -> None:
        """Keep a wave's identity when its membership largely persists.

        Matching is greedy by descending Jaccard overlap of request ids, one
        previous wave to at most one new wave. Anything unmatched keeps the
        fresh id it was born with.
        """
        if not previous or not waves:
            return

        new_sets = [set(w.request_ids) for w in waves]
        old_sets = [set(w.request_ids) for w in previous]

        pairs: List[Tuple[float, int, int]] = []
        for i, new in enumerate(new_sets):
            for j, old in enumerate(old_sets):
                intersection = len(new & old)
                if not intersection:
                    continue
                union = len(new | old)
                jaccard = intersection / float(union) if union else 0.0
                if jaccard > _ID_REUSE_JACCARD:
                    pairs.append((jaccard, i, j))

        pairs.sort(key=lambda p: (-p[0], p[1], p[2]))
        taken_new: set = set()
        taken_old: set = set()
        for _, i, j in pairs:
            if i in taken_new or j in taken_old:
                continue
            taken_new.add(i)
            taken_old.add(j)
            waves[i].id = previous[j].id
            waves[i].created_at = previous[j].created_at

    # -- vectors ------------------------------------------------------------

    def _vector_for(self, request: SongRequest) -> np.ndarray:
        cached = self._vector_cache.get(request.id)
        if cached is not None:
            return cached
        try:
            vector = np.asarray(vectors.intent_vector(request.intent), dtype=np.float64)
        except Exception:  # pragma: no cover - defensive
            log.warning("could not vectorize request %s", request.id)
            vector = np.zeros(taxonomy.VECTOR_DIM, dtype=np.float64)
        if float(np.linalg.norm(vector)) < _EPSILON:
            # A zero row would make cosine distance undefined and take sklearn
            # down with it. Nudge it into a harmless corner of the space.
            vector = vector.copy()
            vector[-1] = 1e-3
        self._vector_cache[request.id] = vector
        return vector


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _safe_sanitize(intent: Intent) -> Intent:
    try:
        return intent.sanitized()
    except Exception:  # pragma: no cover - defensive
        return intent


def _mean(matrix: np.ndarray, indices: List[int]) -> np.ndarray:
    return np.mean(matrix[indices], axis=0)


def _sample_texts(
    members: List[SongRequest],
    member_vectors: Sequence[np.ndarray],
    mean_vector: np.ndarray,
) -> List[str]:
    """Up to three representative raw texts -- the receipts under the label."""
    scored: List[Tuple[float, int, str]] = []
    for request, vector in zip(members, member_vectors):
        text = (request.text or "").strip()
        if not text:
            continue
        scored.append((-vectors.cosine(vector, mean_vector), len(text), text))
    scored.sort()

    out: List[str] = []
    seen: set = set()
    for _, _, text in scored:
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(text if len(text) <= 100 else text[:99] + "…")
        if len(out) == 3:
            break
    return out


def _energy_phrase(energy: float) -> str:
    if energy >= 0.8:
        return "peak energy"
    if energy >= 0.6:
        return "high energy"
    if energy >= 0.4:
        return "mid tempo"
    return "slow burn"


def _summarize(wave: Wave) -> str:
    """One DJ-readable line: '12 people want Punjabi Bhangra, peak energy'."""
    people = wave.unique_sessions or wave.raw_count
    who = "1 person wants" if people == 1 else "%d people want" % people

    centroid = wave.centroid
    parts: List[str] = []
    if centroid.languages:
        parts.append(taxonomy.display(centroid.languages[0]))
    if centroid.genres:
        parts.append(taxonomy.display(centroid.genres[0]))
    # A merged wave can have no single dominant language or genre; its label is
    # then the most honest short description we have.
    what = " ".join(parts) if parts else (wave.label or "something new")

    line = "%s %s, %s" % (who, what, _energy_phrase(centroid.energy_target))
    if wave.raw_count >= 3 and wave.momentum >= 0.6:
        line += " — rising"
    return line


def _distinguishers(intent: Intent) -> List[str]:
    """Words that could tell two same-labelled waves apart, best first."""
    out: List[str] = []
    for mood in intent.moods:
        out.append(taxonomy.display(mood))
    for era in intent.eras:
        out.append(taxonomy.display(era))
    for genre in intent.genres[1:]:
        out.append(taxonomy.display(genre))
    for language in intent.languages:
        out.append(taxonomy.display(language))
    if intent.energy_target >= 0.75:
        out.append("Peak")
    elif intent.energy_target <= 0.4:
        out.append("Mellow")
    else:
        out.append("Uptempo")
    return out


def _dedupe_labels(waves: List[Wave]) -> None:
    """Labels are the DJ's handle on a wave -- two identical ones is a bug."""
    used: set = set()
    for wave in waves:
        base = wave.label or "Requests"
        if base.lower() not in used:
            used.add(base.lower())
            wave.label = base
            continue
        for word in _distinguishers(wave.centroid):
            if word.lower() in base.lower():
                continue
            candidate = "%s %s" % (base, word)
            if candidate.lower() not in used:
                used.add(candidate.lower())
                wave.label = candidate
                break
        else:
            index = 2
            while ("%s %d" % (base, index)).lower() in used:
                index += 1
            wave.label = "%s %d" % (base, index)
            used.add(wave.label.lower())
