"""Amdahl's and Gustafson's laws.

P is the parallel fraction of the work, N the number of workers.
Earlier bug: main.py computed Gustafson as N - (1 - P) * N, which gives 3.60 for N = 4, P = 0.9.
The law is S = N - (1 - P)(N - 1) (equivalently (1 - P) + P * N), which gives 3.70.
"""


def _check(p: float, n: int) -> None:
    if not 0.0 <= p <= 1.0:
        raise ValueError("P must be between 0 and 1")
    if n < 1:
        raise ValueError("N must be >= 1")


def amdahl_speedup(p: float, n: int) -> float:
    _check(p, n)
    return 1.0 / ((1.0 - p) + p / n)


def gustafson_speedup(p: float, n: int) -> float:
    _check(p, n)
    return n - (1.0 - p) * (n - 1)
