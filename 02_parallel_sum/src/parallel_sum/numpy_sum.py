"""Vectorised sum with NumPy, one process.

The array is built in blocks so n = 1e8 needs about 80 MB at a time instead of 800 MB.
int64 holds the total up to n of about 4.29e9.
"""

import numpy as np

BLOCK = 10_000_000


def numpy_sum(n: int, block: int = BLOCK) -> int:
    if n < 0:
        raise ValueError("n must be >= 0")
    if n > 4_294_967_295:
        raise ValueError("n too large for an int64 total")
    total = 0
    for start in range(1, n + 1, block):
        stop = min(start + block, n + 1)
        total += int(np.arange(start, stop, dtype=np.int64).sum())
    return total
