"""M2 -- crowd wave clustering and anti-manipulation.

Public surface:

    from app.clustering import WaveEngine

``WaveEngine`` turns a stream of individual requests into the small set of
waves a DJ can actually act on, with manipulation-resistant weights attached.
"""

from .engine import WaveEngine

__all__ = ["WaveEngine"]
