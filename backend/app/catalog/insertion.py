"""Setlist-aware insertion (M3b).

The ranker answers "what should the DJ play next?". This module answers a
different and, for a DJ who already has a plan, more useful question: **where in
the set he is already committed to does a crowd request belong?**

That difference is not cosmetic. ``ranker.bridge_score`` is *one-sided* -- it
measures mixability out of the currently playing track and stops there. A slot
in a planned set has two neighbours, so a candidate has to survive both:

    ... Chaleya ──▶ [ the crowd wants this ] ──▶ Jhoome Jo Pathaan ...
                 ^                            ^
                 bridge_out                   bridge_in

A track that lands beautifully out of Chaleya but collides with Jhoome Jo
Pathaan is a bad insert, and a one-sided score cannot see it. Averaging the two
sides does not fix it either: mean(1.0, 0.2) and mean(0.6, 0.6) both give 0.6,
which would call a train wreck equivalent to a pair of decent transitions. So
the two sides are combined with a **harmonic** mean, which punishes imbalance --
H(1.0, 0.2) = 0.33 against H(0.6, 0.6) = 0.60.

Tips enter here and nowhere else, deliberately. A tip never adds score: it only
orders candidates that are already effectively tied (see ``TIE_BAND``). Money
resolves a coin-flip; it cannot buy a worse mix. Keeping that rule in one place
is what stops "guest paid" from quietly becoming "guest outranks the room" --
the property ``antimanip.py`` exists to protect.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple

from ..config import settings
from ..contracts import DJState, SetlistEntry, SlotProposal, Tip, Track, Wave
from . import ranker

# Two candidate placements whose scores differ by less than this are, for a
# DJ's purposes, the same decision -- both mix, both serve the room. That is
# the only window a tip is allowed to act in. Small on purpose: widen it and
# money starts overriding real musical fit.
TIE_BAND = 0.04

# How far ahead to consider inserting. The set moves fast (this DJ transitions
# roughly once a minute), and proposing a slot twenty tracks out is noise -- by
# the time he gets there the room has changed.
DEFAULT_HORIZON = 5


def _harmonic(a: float, b: float) -> float:
    """Mean that punishes imbalance -- one bad side sinks the pair."""
    if a <= 0.0 or b <= 0.0:
        return 0.0
    return 2.0 * a * b / (a + b)


def transition_fit(from_track: Optional[Track], to_track: Optional[Track]):
    """Mixability of ``from_track`` -> ``to_track``.

    Returns ``(fit, bpm_delta, kind)``. An open end (nothing before or after)
    is neutral rather than free: the DJ still has to get out of it somehow, and
    scoring it 1.0 would make appending to the end of the set always look best.
    """
    if from_track is None or to_track is None:
        return ranker.NEUTRAL_BRIDGE, None, "open"

    fit, kind, _delta = ranker.bpm_relationship(to_track.bpm, from_track.bpm)
    energy = ranker._energy_fit(to_track.energy, from_track.energy)
    score = ranker._clamp(0.7 * fit + 0.3 * energy)
    return score, int(to_track.bpm - from_track.bpm), kind


def _slot_neighbours(
    dj: DJState, upcoming: Sequence[SetlistEntry], index: int
) -> Tuple[Optional[Track], Optional[Track]]:
    """What plays either side of an insert placed *before* ``upcoming[index]``.

    At the head of the queue the left neighbour is whatever is on the decks
    right now -- inserting at position 0 means "play this next", so it has to
    mix out of the live track, not out of nothing.
    """
    after = upcoming[index - 1].track if index > 0 else dj.current_track
    before = upcoming[index].track if index < len(upcoming) else None
    return after, before


def _reasons(
    wave: Wave,
    track: Track,
    after: Optional[Track],
    before: Optional[Track],
    bridge_out: float,
    bridge_in: float,
    kind_out: str,
    kind_in: str,
    matched_artist: Optional[str],
    hits: Sequence[str],
    tip_minor: int,
    tip_broke_tie: bool,
) -> List[str]:
    """Short, number-grounded lines. The DJ is reading these mid-set."""
    out: List[str] = []

    if matched_artist:
        out.append("%s named by %d requests" % (matched_artist, wave.raw_count))
    elif hits:
        out.append('Asked for "%s"' % hits[0])
    else:
        out.append("Matches the %s wave (%d people)" % (wave.label, wave.unique_sessions))

    # The placement itself -- this is the part that is new to the DJ.
    if after is not None:
        label = {
            "double": "double-time out of",
            "half": "half-time out of",
        }.get(kind_out, "%+d BPM out of" % (track.bpm - after.bpm))
        out.append("%s %s" % (label, after.title))
    if before is not None:
        label = {
            "double": "double-time into",
            "half": "half-time into",
        }.get(kind_in, "%+d BPM into" % (before.bpm - track.bpm))
        out.append("%s %s" % (label, before.title))

    weaker = min(bridge_out, bridge_in)
    if weaker < 0.45:
        side = after.title if bridge_out < bridge_in else (before.title if before else "the next track")
        out.append("Rough edge against %s" % side)

    if tip_minor > 0:
        out.append(
            "Tipped %s%s"
            % (_money(tip_minor), " — broke a tie" if tip_broke_tie else "")
        )

    seen, unique = set(), []
    for line in out:
        if line not in seen:
            seen.add(line)
            unique.append(line)
    return unique[:4]


def _money(minor: int) -> str:
    return "₹%s" % ("%.2f" % (minor / 100.0)).rstrip("0").rstrip(".")


def propose_slots(
    wave: Wave,
    tracks: Sequence[Track],
    dj: DJState,
    tips: Optional[Sequence[Tip]] = None,
    horizon: int = DEFAULT_HORIZON,
    limit: int = 3,
) -> List[SlotProposal]:
    """Best (track, position) placements for one wave inside the DJ's set.

    Each candidate track is tried in every slot within ``horizon``; the best
    slot per track survives, so the DJ never sees the same song proposed three
    times in three places. Never raises -- this feeds a live screen.
    """
    upcoming = dj.upcoming(limit=horizon)
    if not tracks:
        return []

    # Live tips, summed per track. Only PENDING money counts: already-captured
    # tips were earned by a track that has played, and released ones are void.
    tip_by_track: Dict[str, int] = {}
    for tip in tips or []:
        if tip.is_live and tip.amount_minor > 0:
            tip_by_track[tip.track_id] = (
                tip_by_track.get(tip.track_id, 0) + int(tip.amount_minor)
            )

    demand = ranker.demand_score(wave)
    best: Dict[str, SlotProposal] = {}

    # len(upcoming) + 1 boundaries: before each upcoming track, plus the tail.
    for index in range(len(upcoming) + 1):
        after, before = _slot_neighbours(dj, upcoming, index)
        for track in tracks:
            vibe, matched_artist, hits, _base = ranker.vibe_score(wave, track)
            bridge_out, delta_out, kind_out = transition_fit(after, track)
            bridge_in, delta_in, kind_in = transition_fit(track, before)
            bridge = _harmonic(bridge_out, bridge_in)

            score = ranker._clamp(
                settings.weight_demand * demand
                + settings.weight_vibe * vibe
                + settings.weight_bridge * bridge,
                high=3.0,
            )

            tip_minor = tip_by_track.get(track.id, 0)
            proposal = SlotProposal(
                track=track,
                wave_id=wave.id,
                wave_label=wave.label,
                position=index,
                after=after,
                before=before,
                score=score,
                demand_score=demand,
                vibe_score=vibe,
                bridge_in=bridge_in,
                bridge_out=bridge_out,
                bpm_delta_in=delta_in,
                bpm_delta_out=delta_out,
                tip_minor=tip_minor,
                reasons=_reasons(
                    wave, track, after, before, bridge_out, bridge_in,
                    kind_out, kind_in, matched_artist, hits, tip_minor, False,
                ),
            )

            incumbent = best.get(track.id)
            if incumbent is None or proposal.score > incumbent.score:
                best[track.id] = proposal

    ordered = _order_with_tips(list(best.values()))
    return ordered[:limit]


def _order_with_tips(proposals: List[SlotProposal]) -> List[SlotProposal]:
    """Rank by score, letting tips settle ties -- and only ties.

    Sorting by ``(score, tip)`` together would be wrong: floating-point scores
    almost never collide exactly, so the tip term would never fire. Instead the
    list is grouped into bands of near-equal score and each band is ordered by
    tip, which is the literal reading of "a tip only wins when two songs
    clash".
    """
    proposals.sort(key=lambda p: -p.score)

    result: List[SlotProposal] = []
    i = 0
    while i < len(proposals):
        # Everything within TIE_BAND of the band leader is one decision.
        band = [proposals[i]]
        j = i + 1
        while j < len(proposals) and (proposals[i].score - proposals[j].score) < TIE_BAND:
            band.append(proposals[j])
            j += 1

        if len(band) > 1 and any(p.tip_minor > 0 for p in band):
            before = [p.track.id for p in band]
            band.sort(key=lambda p: (-p.tip_minor, -p.score))
            if [p.track.id for p in band] != before:
                # Only claim credit when the tip actually changed the order.
                winner = band[0]
                winner.tip_broke_tie = True
                winner.reasons = [
                    r for r in winner.reasons if not r.startswith("Tipped ")
                ] + ["Tipped %s — broke a tie" % _money(winner.tip_minor)]

        result.extend(band)
        i = j
    return result


__all__ = ["DEFAULT_HORIZON", "TIE_BAND", "propose_slots", "transition_fit"]
