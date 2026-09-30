"""Timing helpers: repeat a callable, report mean and sample standard deviation."""

from __future__ import annotations

import statistics
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class TimingStats:
    runs: tuple[float, ...]

    @property
    def mean(self) -> float:
        return statistics.fmean(self.runs)

    @property
    def sd(self) -> float:
        return statistics.stdev(self.runs) if len(self.runs) > 1 else 0.0

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["runs"] = list(self.runs)
        d["mean"] = self.mean
        d["sd"] = self.sd
        return d


def time_repeats(fn: Callable[[], Any], repeats: int) -> tuple[TimingStats, Any]:
    """Run fn `repeats` times; return the timings and the last return value."""
    if repeats < 1:
        raise ValueError("repeats must be >= 1")
    runs = []
    result = None
    for _ in range(repeats):
        t0 = time.perf_counter()
        result = fn()
        runs.append(time.perf_counter() - t0)
    return TimingStats(tuple(runs)), result


def speedup(t_sequential: float, t_parallel: float) -> float:
    if t_parallel <= 0:
        raise ValueError("parallel time must be positive")
    return t_sequential / t_parallel


def efficiency(t_sequential: float, t_parallel: float, workers: int) -> float:
    """Parallel efficiency S/p, where p is the number of workers that actually ran."""
    if workers < 1:
        raise ValueError("workers must be >= 1")
    return speedup(t_sequential, t_parallel) / workers
