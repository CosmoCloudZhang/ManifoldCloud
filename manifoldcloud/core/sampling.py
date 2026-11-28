"""Choose the same sample rows on every machine without storing random numbers."""

import numpy as np


def uniform_from_id(identifier):
    """Map integer identifiers to repeatable float32 values in [0, 1)."""
    # SplitMix64 followed by the top 24 bits, an exactly representable float32 in [0, 1).
    hashed = np.asarray(identifier, dtype=np.int64).view(np.uint64).copy()
    hashed += np.uint64(0x9E3779B97F4A7C15)
    hashed = (hashed ^ (hashed >> 30)) * np.uint64(0xBF58476D1CE4E5B9)
    hashed = (hashed ^ (hashed >> 27)) * np.uint64(0x94D049BB133111EB)
    hashed ^= hashed >> 31
    return (hashed >> 40).astype(np.float32) * np.float32(2.0 ** -24)
