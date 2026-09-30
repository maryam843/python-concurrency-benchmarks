"""Stage 1 (I/O-bound): download the year sequentially vs with 4 and 8 threads, 3 runs each.

    python -m nyc_taxi.stage1_io --workers 1 4 8 --repeats 3
    python -m nyc_taxi.stage1_io --from-disk        # if the files are already cached: time reading them instead

Each run downloads into a fresh temporary folder that is deleted afterwards, so no run is served
from a local copy. Every run's files are checked against the SHA-256 in the first run.
"""

from __future__ import annotations

import argparse
import shutil
import statistics
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pyarrow.parquet as pq

from bench_common import write_result
from nyc_taxi.config import DATA_DIR, MONTHS, file_name
from nyc_taxi.download import download_months


def time_downloads(months, workers, url_for=None, tmp_root=None) -> tuple[float, dict[str, str], int]:
    d = Path(tempfile.mkdtemp(prefix="taxi_dl_", dir=tmp_root))
    try:
        t0 = time.perf_counter()
        info = download_months(months, d, workers, url_for)
        elapsed = time.perf_counter() - t0
    finally:
        shutil.rmtree(d, ignore_errors=True)
    return elapsed, {i["file"]: i["sha256"] for i in info}, sum(i["bytes"] for i in info)


def _read_table(path: Path) -> int:
    return pq.read_table(path).num_rows


def time_disk_reads(months, workers, data_dir: Path) -> tuple[float, int]:
    paths = [data_dir / file_name(m) for m in months]
    t0 = time.perf_counter()
    if workers == 1:
        rows = sum(_read_table(p) for p in paths)
    else:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            rows = sum(pool.map(_read_table, paths))
    return time.perf_counter() - t0, rows


def run(months, workers_list, repeats, from_disk=False, data_dir=DATA_DIR, url_for=None, tmp_root=None) -> dict:
    rows, reference = [], None
    for w in workers_list:
        times = []
        for _ in range(repeats):
            if from_disk:
                t, n = time_disk_reads(months, w, data_dir)
                check = n
            else:
                t, check, n = time_downloads(months, w, url_for, tmp_root)
            if reference is None:
                reference = check
            elif check != reference:
                raise AssertionError(f"workers={w}: downloaded files differ from the first run")
            times.append(t)
        rows.append({"workers": w, "runs_s": times, "mean_s": statistics.fmean(times),
                     "sd_s": statistics.stdev(times) if len(times) > 1 else 0.0,
                     ("rows" if from_disk else "bytes"): n})
    base = rows[0]["mean_s"]
    for r in rows:
        r["speedup_vs_first"] = base / r["mean_s"]
        if not from_disk:
            r["throughput_mb_s"] = r["bytes"] / r["mean_s"] / 1e6
    return {"mode": "read_from_disk" if from_disk else "download", "months": months, "repeats": repeats,
            "rows": rows}


def main(argv=None) -> dict:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--months", nargs="+", default=MONTHS)
    ap.add_argument("--workers", nargs="+", type=int, default=[1, 4, 8])
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--from-disk", action="store_true")
    ap.add_argument("--data-dir", type=Path, default=DATA_DIR)
    ap.add_argument("--no-save", action="store_true")
    args = ap.parse_args(argv)
    res = run(args.months, args.workers, args.repeats, args.from_disk, args.data_dir)
    for r in res["rows"]:
        extra = f"  {r['throughput_mb_s']:.1f} MB/s" if "throughput_mb_s" in r else ""
        print(f"workers={r['workers']}  mean={r['mean_s']:.2f}s  sd={r['sd_s']:.2f}  "
              f"speedup={r['speedup_vs_first']:.2f}{extra}")
    if not args.no_save:
        write_result(f"stage1_{res['mode']}", res, seed=None, subdir="06_nyc_taxi_pipeline")
    return res


if __name__ == "__main__":
    main()
