"""Two CPU-bound workloads (also used in the notebook), seeded so results can be checked.

Both are pure-Python loops, so they hold the GIL the whole time.
"""

from __future__ import annotations

import random


def generate_and_add_numbers(n: int = 1000, seed: int | None = None) -> int:
    """Add n random integers in [0, 1_000_000]."""
    rng = random.Random(seed)
    total = 0
    for _ in range(n):
        total += rng.randint(0, 1000000)
    return total


def generate_and_join_letters(n: int = 1000, seed: int | None = None) -> str:
    """Join n random printable ASCII characters (codes 33..126)."""
    rng = random.Random(seed)
    letters = ""
    for _ in range(n):
        letters += chr(rng.randint(33, 126))
    return letters


WORKLOADS = {
    "numbers": generate_and_add_numbers,
    "letters": generate_and_join_letters,
}


def run_task(task: tuple[str, int, int]) -> int | str:
    """Run one (workload name, n, seed) task. Module-level so it pickles under 'spawn'."""
    name, n, seed = task
    return WORKLOADS[name](n, seed)
