# Provided by DSAI3202 course staff (UDST, Spring 2025). Modified by me: yes (2026: n from the command
# line, NumPy int64 arrays instead of Python lists, Gatherv/Reduce instead of gather, prints length,
# last square and time, optional JSON output; the work split between ranks is unchanged).
"""Parallel squares with mpi4py.

    mpiexec -n 4 python 05_mpi_multi_node/calculate_squares.py 1e8
    mpiexec -n 4 python 05_mpi_multi_node/calculate_squares.py 1e8 --no-gather   # reduce only
"""

import argparse
import json
import sys

from mpi4py import MPI

from mpi_squares.core import run


def square(n):
    """Computes the square of a number."""
    return n * n


def main(argv=None):
    ap = argparse.ArgumentParser(description="Squares of 1..n over MPI ranks")
    ap.add_argument("n", nargs="?", type=float, default=10)
    ap.add_argument("--no-gather", action="store_true", help="only reduce length/last/checksum at rank 0")
    ap.add_argument("--json", help="rank 0 writes the summary to this file")
    args = ap.parse_args(argv)

    # Initialize MPI
    comm = MPI.COMM_WORLD
    summary = run(comm, int(args.n), gather=not args.no_gather)

    if comm.Get_rank() == 0:
        result = summary.pop("_result", None)
        if result is not None and result.size <= 20:
            print("Squared numbers:", result.tolist())
        print(f"ranks={summary['ranks']} n={summary['n']:,} length={summary['length']:,} "
              f"last square={summary['last_square']:,} time={summary['time_s']:.3f} s "
              f"peak RSS rank 0={summary['peak_rss_mb_rank0']:.0f} MB")
        if args.json:
            with open(args.json, "w", encoding="utf-8") as f:
                json.dump(summary, f, indent=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
