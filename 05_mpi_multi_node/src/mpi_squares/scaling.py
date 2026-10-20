"""Single-machine scaling table for calculate_squares.py: mpiexec -n 1/2/4, several n, repeated runs.

    python -m mpi_squares.scaling --ranks 1 2 4 --sizes 1e7 1e8 --repeats 5 --pause 2

Back-to-back runs alternated between fast and slow, so every run (warm-up included) now waits a short
pause first, and speedups use the median of the runs. Peak memory is the largest seen in any run.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from bench_common import OUTLIER_FACTOR, first_run_outlier, write_result

SCRIPT = Path(__file__).resolve().parents[2] / "calculate_squares.py"


def root_needs_permission() -> bool:
    """True when running as root without PCB_ALLOW_ROOT=1, so Open MPI will refuse to start."""
    return hasattr(os, "geteuid") and os.geteuid() == 0 and os.environ.get("PCB_ALLOW_ROOT") != "1"


def mpi_env() -> dict:
    env = dict(os.environ)
    # allow more ranks than cores on small CI runners
    env.setdefault("OMPI_MCA_rmaps_base_oversubscribe", "1")
    # running as root (containers, Colab) only when asked for with PCB_ALLOW_ROOT=1
    if os.environ.get("PCB_ALLOW_ROOT") == "1":
        env.setdefault("OMPI_ALLOW_RUN_AS_ROOT", "1")
        env.setdefault("OMPI_ALLOW_RUN_AS_ROOT_CONFIRM", "1")
    return env


def run_once(ranks: int, n: int, gather: bool = True, timeout: float = 600) -> dict:
    mpiexec = shutil.which("mpiexec")
    if mpiexec is None:
        raise RuntimeError("mpiexec not found; install an MPI runtime (e.g. apt install openmpi-bin)")
    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / "summary.json"
        cmd = [mpiexec, "-n", str(ranks), sys.executable, str(SCRIPT), str(n), "--json", str(out)]
        if not gather:
            cmd.append("--no-gather")
        subprocess.run(cmd, check=True, capture_output=True, text=True, env=mpi_env(), timeout=timeout)
        return json.loads(out.read_text())


def _paused_run(ranks: int, n: int, gather: bool, pause_s: float) -> dict:
    time.sleep(pause_s)  # let the previous run's memory be handed back first
    return run_once(ranks, n, gather)


def scaling(ranks_list: list[int], sizes: list[int], repeats: int, gather: bool = True, pause_s: float = 2.0) -> dict:
    rows = []
    for n in sizes:
        base = None
        for ranks in ranks_list:
            _paused_run(ranks, n, gather, pause_s)  # warm-up run, not timed (first-touch memory, page cache)
            runs = [_paused_run(ranks, n, gather, pause_s) for _ in range(repeats)]
            ref = runs[0]
            if any(r["checksum_mod_2_64"] != ref["checksum_mod_2_64"] or r["length"] != n for r in runs):
                raise AssertionError(f"inconsistent results for n={n}, ranks={ranks}")
            if ref["last_square"] != n * n:
                raise AssertionError(f"last square wrong for n={n}")
            times = [r["time_s"] for r in runs]
            median = statistics.median(times)
            if ranks == ranks_list[0]:
                base = (median, ranks, ref["checksum_mod_2_64"])
            elif ref["checksum_mod_2_64"] != base[2]:
                raise AssertionError(f"checksum differs between rank counts for n={n}")
            speedup = base[0] / median
            outlier = first_run_outlier(times)
            if outlier:
                print(f"info: n={n:.0e} ranks={ranks}: first timed run {times[0]:.3f} s is more than "
                      f"{OUTLIER_FACTOR:g}x the median {median:.3f} s")
            rows.append({
                "n": n, "ranks": ranks, "gather": gather, "runs_s": times, "median_s": median,
                "mean_s": statistics.fmean(times), "sd_s": statistics.stdev(times) if len(times) > 1 else 0.0,
                "first_run_outlier": outlier,
                "speedup_vs_1_rank": speedup, "efficiency": speedup / (ranks / base[1]),
                "length": ref["length"], "last_square": ref["last_square"],
                "checksum_mod_2_64": ref["checksum_mod_2_64"],
                "peak_rss_mb_rank0_max": max(r["peak_rss_mb_rank0"] for r in runs),
                "peak_rss_mb_per_rank_max": max(max(r["peak_rss_mb_per_rank"]) for r in runs),
            })
    return {"ranks": ranks_list, "sizes": sizes, "repeats": repeats, "pause_s": pause_s, "gather": gather,
            "speedup_from": "median", "rows": rows}


def format_table(res: dict) -> str:
    lines = ["| n | Ranks | Median (s) | Mean (s) | SD (s) | Speedup vs 1 rank | Efficiency | Peak RSS rank 0 (MB) |",
             "|---|---|---|---|---|---|---|---|"]
    for r in res["rows"]:
        lines.append(f"| {r['n']:.0e} | {r['ranks']} | {r['median_s']:.3f} | {r['mean_s']:.3f} | {r['sd_s']:.3f} "
                     f"| {r['speedup_vs_1_rank']:.2f} | {r['efficiency']:.2f} | {r['peak_rss_mb_rank0_max']:.0f} |")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> dict:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--ranks", nargs="+", type=int, default=[1, 2, 4])
    ap.add_argument("--sizes", nargs="+", type=float, default=[1e7, 1e8])
    ap.add_argument("--repeats", type=int, default=5)
    ap.add_argument("--pause", type=float, default=2.0, help="seconds to wait before each run")
    ap.add_argument("--no-gather", action="store_true")
    ap.add_argument("--no-save", action="store_true")
    args = ap.parse_args(argv)
    if args.repeats < 5:
        ap.error("--repeats must be at least 5 (the median of fewer runs is not reliable here)")
    res = scaling(args.ranks, [int(s) for s in args.sizes], args.repeats, gather=not args.no_gather,
                  pause_s=args.pause)
    print(format_table(res))
    if not args.no_save:
        name = "mpi_squares_scaling" + ("_reduce_only" if args.no_gather else "_gatherv")
        path = write_result(name, res, seed=None, subdir="05_mpi_multi_node")
        print(f"saved {path.name}")
    return res


if __name__ == "__main__":
    main()
