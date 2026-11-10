"""Stage 2 (CPU-bound): read, clean and summarise each month; sequential vs threads vs processes.

    python -m nyc_taxi.stage2_cpu --workers 1 2 4 --repeats 3

Every method must return exactly the same month summaries as the sequential run. Each configuration
runs once untimed (it also fills the file cache), then `repeats` timed runs; speedups use the medians.
"""

from __future__ import annotations

import argparse
import multiprocessing as mp
import statistics
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from pathlib import Path

from bench_common import first_run_outlier, write_result
from nyc_taxi.config import DATA_DIR, MONTHS, file_name
from nyc_taxi.summaries import combine, summarise_month, summary_key


def run_method(method: str, paths: list[Path], workers: int = 1, start_method: str | None = None) -> list[dict]:
    if method == "sequential":
        return [summarise_month(p) for p in paths]
    if method == "threads":
        with ThreadPoolExecutor(max_workers=workers) as pool:
            return list(pool.map(summarise_month, paths))
    if method == "processes":
        ctx = mp.get_context(start_method)
        with ProcessPoolExecutor(max_workers=workers, mp_context=ctx) as pool:
            return list(pool.map(summarise_month, paths))
    raise ValueError(f"unknown method {method}")


def run(paths: list[Path], workers_list: list[int], repeats: int, start_method: str | None = None) -> dict:
    configs = [("sequential", 1)] + [(m, w) for m in ("threads", "processes") for w in workers_list]
    rows, reference, t_seq, t_seq_mean = [], None, None, None
    for method, w in configs:
        times = []
        for i in range(repeats + 1):  # run 0 is the untimed warm-up
            t0 = time.perf_counter()
            out = run_method(method, paths, w, start_method)
            if i > 0:
                times.append(time.perf_counter() - t0)
            key = summary_key(out)
            if reference is None:
                reference = key
            elif key != reference:
                raise AssertionError(f"{method} x{w} produced different summaries from the sequential run")
        median, mean = statistics.median(times), statistics.fmean(times)
        if method == "sequential":
            t_seq, t_seq_mean = median, mean
        rows.append({"method": method, "workers": w, "runs_s": times, "median_s": median, "mean_s": mean,
                     "sd_s": statistics.stdev(times) if len(times) > 1 else 0.0,
                     "first_run_outlier": first_run_outlier(times), "speedup": t_seq / median,
                     "speedup_of_means": t_seq_mean / mean, "efficiency": t_seq / median / w,
                     "identical_to_sequential": True})
    return {"files": [p.name for p in paths], "repeats": repeats, "warmup": "one untimed run per configuration",
            "speedup_from": "median",
            "start_method": start_method or mp.get_start_method(), "rows": rows,
            "month_summaries": reference, "yearly": combine(reference)}


def main(argv=None) -> dict:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--months", nargs="+", default=MONTHS)
    ap.add_argument("--data-dir", type=Path, default=DATA_DIR)
    ap.add_argument("--workers", nargs="+", type=int, default=[1, 2, 4])
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--start-method", choices=["fork", "spawn", "forkserver"], default=None)
    ap.add_argument("--name", default="stage2_cpu")
    ap.add_argument("--no-save", action="store_true")
    args = ap.parse_args(argv)
    paths = [args.data_dir / file_name(m) for m in args.months]
    res = run(paths, args.workers, args.repeats, args.start_method)
    for r in res["rows"]:
        print(f"{r['method']:>10} x{r['workers']}  median={r['median_s']:.2f}s  mean={r['mean_s']:.2f}s  "
              f"sd={r['sd_s']:.2f}  "
              f"speedup={r['speedup']:.2f}  efficiency={r['efficiency']:.2f}")
    if not args.no_save:
        write_result(args.name, res, seed=None, subdir="06_nyc_taxi_pipeline")
    return res


if __name__ == "__main__":
    main()
