"""Pool benchmarks for the squares task at n = 1e5 and 1e6.

    python -m connection_pool.benchmark --sizes 1e5 1e6 --repeats 3

apply_async with one task per item is not run above n = 1e6: every item becomes its own task,
AsyncResult object and pair of pickled messages. At 1e6 that already takes about two minutes on a
4-core machine, and at 1e7 ten million AsyncResult objects would be pending at once.
"""

from __future__ import annotations

import argparse
import multiprocessing as mp

from bench_common import speedup, time_repeats, write_result
from connection_pool.square import (
    concurrent_futures,
    default_workers,
    pool_apply_async,
    pool_apply_async_chunked,
    pool_map,
    sequential_squares,
)

APPLY_ASYNC_PER_ITEM_MAX_N = 10**6


def methods(workers: int, start_method: str | None):
    return {
        "sequential": lambda xs: sequential_squares(xs),
        "pool_map": lambda xs: pool_map(xs, workers, start_method),
        "apply_async_per_item": lambda xs: pool_apply_async(xs, workers, start_method),
        "apply_async_chunked": lambda xs: pool_apply_async_chunked(xs, workers, start_method=start_method),
        "process_pool_executor_chunksize": lambda xs: concurrent_futures(xs, workers, start_method),
    }


def benchmark(sizes: list[int], workers: int, repeats: int, slow_repeats: int,
              start_method: str | None = None) -> dict:
    rows, skipped = [], []
    for n in sizes:
        numbers = list(range(n))
        expected = [x * x for x in numbers]
        t_seq = None
        for name, fn in methods(workers, start_method).items():
            if name == "apply_async_per_item" and n > APPLY_ASYNC_PER_ITEM_MAX_N:
                skipped.append({"n": n, "method": name, "reason": "one task per item does not scale; see docstring"})
                continue
            reps = slow_repeats if name == "apply_async_per_item" and n >= 10**6 else repeats
            stats, out = time_repeats(lambda fn=fn, numbers=numbers: fn(numbers), reps)
            if out != expected:
                raise AssertionError(f"{name} returned wrong squares for n={n}")
            if name == "sequential":
                t_seq = stats.mean
            assert t_seq is not None
            rows.append({"n": n, "method": name, "workers": 1 if name == "sequential" else workers,
                         "repeats": reps, "mean_s": stats.mean, "sd_s": stats.sd, "runs_s": list(stats.runs),
                         "speedup": speedup(t_seq, stats.mean), "correct": True})
    return {"sizes": sizes, "workers": workers, "start_method": start_method or mp.get_start_method(),
            "rows": rows, "skipped": skipped}


def format_table(res: dict) -> str:
    lines = ["| n | Method | Runs | Mean (s) | SD (s) | Speedup vs sequential |", "|---|---|---|---|---|---|"]
    for r in res["rows"]:
        lines.append(f"| {r['n']:.0e} | {r['method']} | {r['repeats']} | {r['mean_s']:.4f} | {r['sd_s']:.4f} "
                     f"| {r['speedup']:.3f} |")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> dict:
    ap = argparse.ArgumentParser(description="Squares with Pool.map, apply_async and ProcessPoolExecutor")
    ap.add_argument("--sizes", nargs="+", type=float, default=[1e5, 1e6])
    ap.add_argument("--workers", type=int, default=default_workers())
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--slow-repeats", type=int, default=1, help="runs for apply_async per item at n >= 1e6")
    ap.add_argument("--start-method", choices=["fork", "spawn", "forkserver"], default=None)
    ap.add_argument("--no-save", action="store_true")
    args = ap.parse_args(argv)
    res = benchmark([int(s) for s in args.sizes], args.workers, args.repeats, args.slow_repeats, args.start_method)
    print(format_table(res))
    if not args.no_save:
        path = write_result("pool_squares", res, seed=None, subdir="03_connection_pool")
        print(f"saved {path.name}")
    return res


if __name__ == "__main__":
    main()
