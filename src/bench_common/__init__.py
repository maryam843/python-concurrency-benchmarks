"""Small helpers shared by every experiment: timing statistics, machine info, result files."""

from bench_common.results import machine_info, write_result
from bench_common.timing import OUTLIER_FACTOR, TimingStats, efficiency, first_run_outlier, speedup, time_repeats

__all__ = ["OUTLIER_FACTOR", "TimingStats", "efficiency", "first_run_outlier", "machine_info", "speedup",
           "time_repeats", "write_result"]
