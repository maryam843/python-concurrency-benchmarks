"""Benchmark every sum method at n = 1e6, 1e7, 1e8.

    python -m parallel_sum.benchmark --sizes 1e6 1e7 1e8 --workers 4 --repeats 3
"""

from __future__ import annotations

import argparse
import multiprocessing as mp

from bench_common import efficiency, speedup, time_repeats, write_result
from parallel_sum.functions import calculate_sum_sequential
from parallel_sum.numpy_sum import numpy_sum
from parallel_sum.pool_sum import calculate_sum_pool
from parallel_sum.processing import calculate_sum_multiprocessing
from parallel_sum.shared_array import parallel_process_sum
from parallel_sum.threads import calculate_sum_parallel


def methods(workers: int, start_method: str | None):
    """name -> (callable n -> sum, number of workers it uses)."""
    return {
        "sequential": (lambda n: calculate_sum_sequential(n)[0], 1),
        "threads": (lambda n: calculate_sum_parallel(n, workers)[0], workers),
        "processes_queue": (lambda n: calculate_sum_multiprocessing(n, workers, start_method)[0], workers),
        "processes_shared_array_int64": (lambda n: parallel_process_sum(n, workers, "q", start_method), workers),
        "pool_map": (lambda n: calculate_sum_pool(n, workers, start_method), workers),
        "numpy_vectorised": (numpy_sum, 1),
    }


def benchmark(sizes: list[int], workers: int, repeats: int, start_method: str | None = None) -> dict:
    rows = []
    for fn, _ in methods(workers, start_method).values():
        fn(1000)  # warm-up: one-time imports and lazy initialisation are not timed
    for n in sizes:
        expected = n * (n + 1) // 2
        t_seq = None
        for name, (fn, p) in methods(workers, start_method).items():
            stats, value = time_repeats(lambda fn=fn, n=n: fn(n), repeats)
            if value != expected:
                raise AssertionError(f"{name} gave {value} for n={n}, expected {expected}")
            if name == "sequential":
                t_seq = stats.mean
            assert t_seq is not None
            rows.append({
                "n": n, "method": name, "workers": p,
                "mean_s": stats.mean, "sd_s": stats.sd, "runs_s": list(stats.runs),
                "speedup": speedup(t_seq, stats.mean),
                "efficiency": efficiency(t_seq, stats.mean, p),
                "sum": value, "correct": True,
            })
    return {"sizes": sizes, "workers": workers, "repeats": repeats,
            "start_method": start_method or mp.get_start_method(), "rows": rows}


def format_table(res: dict) -> str:
    lines = ["| n | Method | p | Mean (s) | SD (s) | Speedup | Efficiency |", "|---|---|---|---|---|---|---|"]
    for r in res["rows"]:
        lines.append(f"| {r['n']:.0e} | {r['method']} | {r['workers']} | {r['mean_s']:.4f} | {r['sd_s']:.4f} "
                     f"| {r['speedup']:.2f} | {r['efficiency']:.2f} |")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> dict:
    ap = argparse.ArgumentParser(description="Parallel sum of 1..n")
    ap.add_argument("--sizes", nargs="+", type=float, default=[1e6, 1e7, 1e8])
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--start-method", choices=["fork", "spawn", "forkserver"], default=None)
    ap.add_argument("--no-save", action="store_true")
    args = ap.parse_args(argv)
    sizes = [int(s) for s in args.sizes]
    res = benchmark(sizes, args.workers, args.repeats, args.start_method)
    print(format_table(res))
    if not args.no_save:
        path = write_result("parallel_sum", res, seed=None, subdir="02_parallel_sum")
        print(f"saved {path.name}")
    return res


if __name__ == "__main__":
    main()
