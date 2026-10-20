"""Timing helpers: repeat a callable, report mean, median and sample standard deviation.

A first run more than OUTLIER_FACTOR times slower than the median is flagged as an outlier
(information only, never a failure): it usually means a cold start such as fresh memory pages.
"""

from __future__ import annotations

import statistics
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from typing import Any

OUTLIER_FACTOR = 3.0


def first_run_outlier(runs: tuple[float, ...] | list[float], factor: float = OUTLIER_FACTOR) -> bool:
    """True when the first run is more than `factor` times slower than the median of all runs."""
    return len(runs) > 1 and runs[0] > factor * statistics.median(runs)


@dataclass(frozen=True)
class TimingStats:
    runs: tuple[float, ...]

    @property
    def mean(self) -> float:
        return statistics.fmean(self.runs)

    @property
    def median(self) -> float:
        return statistics.median(self.runs)

    @property
    def first_run_outlier(self) -> bool:
        return first_run_outlier(self.runs)

    @property
    def sd(self) -> float:
        return statistics.stdev(self.runs) if len(self.runs) > 1 else 0.0

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["runs"] = list(self.runs)
        d["mean"] = self.mean
        d["median"] = self.median
        d["first_run_outlier"] = self.first_run_outlier
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
