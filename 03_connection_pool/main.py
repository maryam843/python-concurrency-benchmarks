"""A1-P1 demo: 8 processes share a pool of 2 database connections guarded by a semaphore.

    python 03_connection_pool/main.py            # prints a summary, writes outputs/ (git-ignored)
    python 03_connection_pool/main.py --save     # writes results/03_connection_pool/ (used by tools/run_benchmarks.py)
"""

import argparse
from pathlib import Path

from bench_common import write_result
from connection_pool import utils
from connection_pool.connection_pool import run_connection_pool


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--processes", type=int, default=8)
    ap.add_argument("--connections", type=int, default=2)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--work", type=float, nargs=2, default=(1.0, 2.0), metavar=("MIN_S", "MAX_S"))
    ap.add_argument("--start-method", choices=["fork", "spawn", "forkserver"], default=None)
    where = ap.add_mutually_exclusive_group()
    where.add_argument("--save", action="store_true", help="write the summary to results/03_connection_pool/")
    where.add_argument("--no-save", action="store_true", help="do not write the summary at all")
    args = ap.parse_args(argv)

    summary = run_connection_pool(args.processes, args.connections, tuple(args.work), args.seed,
                                  start_method=args.start_method, log_file="parallel_logs.txt")
    for e in summary["log"]:
        print(f"t={e['t']:6.3f}s  {e['event']:8s} {e['conn']}  holders now {e['holders_after']}")
    print(f"{summary['acquired']} of {args.processes} processes got a connection; "
          f"max concurrent holders = {summary['max_concurrent_holders']} (pool size {args.connections})")
    if args.save:
        write_result("connection_pool_run", summary, seed=args.seed, subdir="03_connection_pool")
    elif not args.no_save:
        path = write_result("connection_pool_run", summary, seed=args.seed, subdir="",
                            results_dir=Path(utils.OUTPUT_PATH))
        print(f"summary written to {path} (add --save to write results/03_connection_pool/)")
    return summary


if __name__ == "__main__":
    main()
