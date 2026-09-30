"""MPI entry point for stage 3 (run with mpiexec; see nyc_taxi/stage3_mpi.py)."""

import argparse
import json
from pathlib import Path

from mpi4py import MPI

from nyc_taxi.config import DATA_DIR, MONTHS, file_name
from nyc_taxi.stage3_mpi import run


def main(argv=None):
    ap = argparse.ArgumentParser(description="Stage 3: months shared across MPI ranks")
    ap.add_argument("--months", nargs="+", default=MONTHS)
    ap.add_argument("--data-dir", type=Path, default=DATA_DIR)
    ap.add_argument("--json", help="rank 0 writes the result here")
    args = ap.parse_args(argv)
    comm = MPI.COMM_WORLD
    res = run(comm, [args.data_dir / file_name(m) for m in args.months])
    if comm.Get_rank() == 0:
        y = res["yearly"]
        print(f"ranks={res['ranks']} months={len(y['months'])} clean trips={y['rows_clean']:,} "
              f"mean fare={y['mean_fare']:.2f} time={res['time_s']:.2f}s")
        if args.json:
            Path(args.json).write_text(json.dumps(res))


if __name__ == "__main__":
    main()
