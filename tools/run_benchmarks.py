"""Run every benchmark in order and write results/ (about 45 minutes on a 4-core machine).

    python tools/run_benchmarks.py            # everything
    python tools/run_benchmarks.py --only 02 05

Network stages run first; CPU benchmarks then run one at a time so they do not disturb each other.
Needs the datasets (the script downloads them) and, for 05 and 06 stage 3, an MPI runtime.
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PY = sys.executable

STEPS = [
    ("06", "stage 1: downloads, sequential vs 4 and 8 threads", [PY, "-m", "nyc_taxi.stage1_io"]),
    ("06", "download and cache the year + manifest", [PY, "-m", "nyc_taxi.download"]),
    ("04", "download UCI Air Quality", [PY, "04_sensor_monitor/download_air_quality.py"]),
    ("01", "threads vs processes, n = 1e7, 5 repeats", [PY, "-m", "threads_vs_processes.benchmark"]),
    ("02", "parallel sum, n = 1e6/1e7/1e8", [PY, "-m", "parallel_sum.benchmark"]),
    ("03", "connection pool demo", [PY, "03_connection_pool/main.py"]),
    ("03", "pool benchmarks, n = 1e5/1e6", [PY, "-m", "connection_pool.benchmark"]),
    ("04", "sensor monitor, real data, 12 s headless", [PY, "04_sensor_monitor/main.py", "--mode", "data",
                                                         "--headless", "--duration", "12", "--save"]),
    ("05", "MPI squares scaling, Gatherv", [PY, "-m", "mpi_squares.scaling", "--repeats", "10"]),
    ("05", "MPI squares scaling, reduce only", [PY, "-m", "mpi_squares.scaling", "--no-gather", "--repeats", "10"]),
    ("06", "stage 2: sequential vs threads vs processes", [PY, "-m", "nyc_taxi.stage2_cpu"]),
    ("06", "stage 3: MPI 1/2/4 ranks", [PY, "-m", "nyc_taxi.stage3_mpi"]),
    ("06", "stage 4: SQLite questions", [PY, "-m", "nyc_taxi.stage4_sql"]),
    ("06", "figures", [PY, "tools/make_figures.py"]),
]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--only", nargs="+", help="folder numbers to run, e.g. 02 05")
    args = ap.parse_args(argv)
    for folder, label, cmd in STEPS:
        if args.only and folder not in args.only:
            continue
        print(f"\n=== [{folder}] {label}\n$ {' '.join(Path(c).name if c == PY else c for c in cmd)}", flush=True)
        t0 = time.perf_counter()
        subprocess.run(cmd, cwd=REPO, check=True)
        print(f"=== done in {time.perf_counter() - t0:.0f} s", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
