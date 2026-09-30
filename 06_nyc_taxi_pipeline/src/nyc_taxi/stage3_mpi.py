"""Stage 3 (MPI): months are dealt round-robin to the ranks; rank 0 gathers the month summaries.

Run one job (from the repo root):
    mpiexec -n 4 python 06_nyc_taxi_pipeline/stage3_mpi.py --json out.json

Scaling table with 1/2/4 ranks, 3 runs each, checked against a sequential run:
    python -m nyc_taxi.stage3_mpi --ranks 1 2 4 --repeats 3
"""

from __future__ import annotations

import argparse
import json
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from bench_common import write_result
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


def run_job(ranks: int, months: list[str], data_dir: Path, timeout: float = 1800) -> tuple[dict, float]:
    mpiexec = shutil.which("mpiexec")
    if mpiexec is None:
        raise RuntimeError("mpiexec not found; install an MPI runtime (e.g. apt install openmpi-bin)")
    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / "s.json"
        cmd = [mpiexec, "-n", str(ranks), sys.executable, str(SCRIPT), "--json", str(out),
               "--data-dir", str(data_dir), "--months", *months]
        t0 = time.perf_counter()
        subprocess.run(cmd, check=True, capture_output=True, text=True, env=mpi_env(), timeout=timeout)
        wall = time.perf_counter() - t0
        doc = json.loads(out.read_text())
    doc["month_summaries"] = summary_key(doc["month_summaries"])
    return doc, wall


def scaling(months: list[str], data_dir: Path, ranks_list: list[int], repeats: int) -> dict:
    paths = [data_dir / file_name(m) for m in months]
    reference = summary_key([summarise_month(p) for p in paths])  # sequential, untimed
    rows = []
    for ranks in ranks_list:
        times, walls = [], []
        for _ in range(repeats):
            doc, wall = run_job(ranks, months, data_dir)
            if doc["month_summaries"] != reference:
                raise AssertionError(f"{ranks} ranks produced different summaries from the sequential run")
            times.append(doc["time_s"])
            walls.append(wall)
        rows.append({"ranks": ranks, "runs_s": times, "mean_s": statistics.fmean(times),
                     "sd_s": statistics.stdev(times) if len(times) > 1 else 0.0,
                     "wall_incl_startup_mean_s": statistics.fmean(walls), "identical_to_sequential": True})
    base = rows[0]["mean_s"]
    for r in rows:
        r["speedup_vs_1_rank"] = base / r["mean_s"]
        r["efficiency"] = r["speedup_vs_1_rank"] / (r["ranks"] / rows[0]["ranks"])
    return {"months": months, "repeats": repeats, "rows": rows, "yearly": combine(reference)}


def main(argv=None) -> dict:
    ap = argparse.ArgumentParser(description="Stage 3 MPI scaling runner")
    ap.add_argument("--months", nargs="+", default=MONTHS)
    ap.add_argument("--data-dir", type=Path, default=DATA_DIR)
    ap.add_argument("--ranks", nargs="+", type=int, default=[1, 2, 4])
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--no-save", action="store_true")
    args = ap.parse_args(argv)
    res = scaling(args.months, args.data_dir, args.ranks, args.repeats)
    for r in res["rows"]:
        print(f"ranks={r['ranks']}  mean={r['mean_s']:.2f}s  sd={r['sd_s']:.2f}  "
              f"speedup={r['speedup_vs_1_rank']:.2f}  (wall incl. startup {r['wall_incl_startup_mean_s']:.2f}s)")
    if not args.no_save:
        write_result("stage3_mpi", res, seed=None, subdir="06_nyc_taxi_pipeline")
    return res


if __name__ == "__main__":
    main()
