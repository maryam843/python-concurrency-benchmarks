"""Stage 3 (MPI): months are dealt round-robin to the ranks; rank 0 gathers the month summaries.

Run one job (from the repo root):
    mpiexec -n 4 python 06_nyc_taxi_pipeline/stage3_mpi.py --json out.json

Scaling table with 1/2/4 ranks, 3 runs each, checked against a sequential run:
    python -m nyc_taxi.stage3_mpi --ranks 1 2 4 --repeats 3

Every mpiexec call adds --report-bindings, and the binding lines (without the host name) are saved.
One extra row runs with --bind-to none (1 rank by default) to show what Open MPI's default binding
costs. The sequential run is timed as well, so each row has a speedup vs sequential next to the
speedup vs 1 rank. Speedups use medians.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import socket
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from bench_common import OUTLIER_FACTOR, first_run_outlier, write_result
from nyc_taxi.config import DATA_DIR, MONTHS, file_name
from nyc_taxi.summaries import combine, summarise_month, summary_key

SCRIPT = Path(__file__).resolve().parents[2] / "stage3_mpi.py"


def my_share(items: list, rank: int, size: int) -> list:
    """Round-robin: rank r gets items r, r + size, r + 2*size, ..."""
    return items[rank::size]


def run(comm, paths: list[Path]) -> dict | None:
    """Every rank summarises its months; rank 0 returns all month summaries and the yearly result."""
    from mpi4py import MPI

    rank, size = comm.Get_rank(), comm.Get_size()
    comm.Barrier()
    t0 = MPI.Wtime()
    mine = [summarise_month(p) for p in my_share(paths, rank, size)]
    t_local = MPI.Wtime() - t0
    gathered = comm.gather(mine, root=0)
    t_max_local = comm.reduce(t_local, op=MPI.MAX, root=0)
    comm.Barrier()
    elapsed = MPI.Wtime() - t0
    if rank != 0:
        return None
    months = [m for part in gathered for m in part]
    return {"ranks": size, "time_s": elapsed, "max_rank_compute_s": t_max_local,
            "month_summaries": summary_key(months), "yearly": combine(months)}


def mpi_env() -> dict:
    from mpi_squares.scaling import mpi_env as env

    return env()


def binding_lines(output: str) -> list[str]:
    """The --report-bindings lines, with the "[host:pid]" prefix (and any host name) removed."""
    host = socket.gethostname()
    lines = []
    for line in output.splitlines():
        if "bound" in line:
            line = re.sub(r"^\[[^\]]*\]\s*", "", line.strip())
            lines.append(line.replace(host, "[host]") if host else line)
    return lines


def run_job(ranks: int, months: list[str], data_dir: Path, timeout: float = 1800,
            mpi_args: tuple[str, ...] = ()) -> tuple[dict, float]:
    mpiexec = shutil.which("mpiexec")
    if mpiexec is None:
        raise RuntimeError("mpiexec not found; install an MPI runtime (e.g. apt install openmpi-bin)")
    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / "s.json"
        cmd = [mpiexec, "--report-bindings", *mpi_args, "-n", str(ranks), sys.executable, str(SCRIPT),
               "--json", str(out), "--data-dir", str(data_dir), "--months", *months]
        t0 = time.perf_counter()
        proc = subprocess.run(cmd, check=True, capture_output=True, text=True, env=mpi_env(), timeout=timeout)
        wall = time.perf_counter() - t0
        doc = json.loads(out.read_text())
    doc["month_summaries"] = summary_key(doc["month_summaries"])
    doc["bindings"] = binding_lines(proc.stderr + proc.stdout)
    return doc, wall


def _row(ranks: int, months: list[str], data_dir: Path, repeats: int, reference: list,
         binding: str, mpi_args: tuple[str, ...] = ()) -> dict:
    times, walls, bindings = [], [], []
    for _ in range(repeats):
        doc, wall = run_job(ranks, months, data_dir, mpi_args=mpi_args)
        if doc["month_summaries"] != reference:
            raise AssertionError(f"{ranks} ranks ({binding}) produced different summaries from the sequential run")
        times.append(doc["time_s"])
        walls.append(wall)
        bindings = bindings or doc["bindings"]
    if first_run_outlier(times):
        print(f"info: {ranks} ranks ({binding}): first timed run {times[0]:.2f} s is more than "
              f"{OUTLIER_FACTOR:g}x the median {statistics.median(times):.2f} s")
    return {"ranks": ranks, "binding": binding, "runs_s": times, "median_s": statistics.median(times),
            "mean_s": statistics.fmean(times), "sd_s": statistics.stdev(times) if len(times) > 1 else 0.0,
            "first_run_outlier": first_run_outlier(times), "wall_incl_startup_mean_s": statistics.fmean(walls),
            "identical_to_sequential": True, "bindings": bindings}


def scaling(months: list[str], data_dir: Path, ranks_list: list[int], repeats: int,
            bind_none_ranks: int | None = 1) -> dict:
    paths = [data_dir / file_name(m) for m in months]
    reference = summary_key([summarise_month(p) for p in paths])  # sequential, untimed (also warms the file cache)
    seq_runs = []
    for _ in range(repeats):
        t0 = time.perf_counter()
        done = [summarise_month(p) for p in paths]
        seq_runs.append(time.perf_counter() - t0)
        if summary_key(done) != reference:
            raise AssertionError("the sequential run is not reproducible")
    seq = statistics.median(seq_runs)
    rows = [_row(ranks, months, data_dir, repeats, reference, "default") for ranks in ranks_list]
    extra = None
    if bind_none_ranks:
        extra = _row(bind_none_ranks, months, data_dir, repeats, reference, "none", ("--bind-to", "none"))
    base = rows[0]
    for r in rows + ([extra] if extra else []):
        r["speedup_vs_1_rank"] = base["median_s"] / r["median_s"]
        r["efficiency"] = r["speedup_vs_1_rank"] / (r["ranks"] / base["ranks"])
        r["speedup_vs_sequential"] = seq / r["median_s"]
    return {"months": months, "repeats": repeats, "speedup_from": "median",
            "sequential": {"runs_s": seq_runs, "median_s": seq, "mean_s": statistics.fmean(seq_runs)},
            "rows": rows, "bind_to_none": extra, "yearly": combine(reference)}


def main(argv=None) -> dict:
    ap = argparse.ArgumentParser(description="Stage 3 MPI scaling runner")
    ap.add_argument("--months", nargs="+", default=MONTHS)
    ap.add_argument("--data-dir", type=Path, default=DATA_DIR)
    ap.add_argument("--ranks", nargs="+", type=int, default=[1, 2, 4])
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--bind-none-ranks", type=int, default=1, help="ranks for the extra --bind-to none row (0: skip)")
    ap.add_argument("--no-save", action="store_true")
    args = ap.parse_args(argv)
    res = scaling(args.months, args.data_dir, args.ranks, args.repeats, args.bind_none_ranks)
    print(f"sequential  median={res['sequential']['median_s']:.2f}s")
    for r in res["rows"] + ([res["bind_to_none"]] if res["bind_to_none"] else []):
        print(f"ranks={r['ranks']} binding={r['binding']}  median={r['median_s']:.2f}s  mean={r['mean_s']:.2f}s  "
              f"sd={r['sd_s']:.2f}  vs 1 rank={r['speedup_vs_1_rank']:.2f}  "
              f"vs sequential={r['speedup_vs_sequential']:.2f}  "
              f"(wall incl. startup {r['wall_incl_startup_mean_s']:.2f}s)")
        for line in r["bindings"]:
            print("    " + line)
    if not args.no_save:
        write_result("stage3_mpi", res, seed=None, subdir="06_nyc_taxi_pipeline")
    return res


if __name__ == "__main__":
    main()
