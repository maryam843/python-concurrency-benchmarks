"""Squares of 1..n spread over MPI ranks, with NumPy arrays instead of Python lists.

2025 (course script): every rank built a Python list of NumPy scalars and rank 0 gathered them with
comm.gather (pickled objects). At n = 1e7 rank 0 used about 3 GB and at n = 1e8 the run was killed
for running out of memory (15 GB machine, 2026 audit re-run).

Now each rank fills one int64 array (8 bytes per square) and rank 0 receives the pieces straight into
one preallocated array with comm.Gatherv (a buffer copy, no pickling). With gather=False the squares
are never collected: comm.reduce/allreduce only combine the length, the last square and a checksum.
int64 is exact for squares up to n = 3,037,000,499.
"""

from __future__ import annotations

import resource
import sys

import numpy as np

MAX_N = 3_037_000_499  # largest n whose square fits in int64


def chunk_counts(n: int, size: int) -> tuple[list[int], list[int]]:
    """Counts and start offsets per rank; the first n % size ranks get one extra item (as in the lab script)."""
    if size < 1:
        raise ValueError("size must be >= 1")
    if not 0 <= n <= MAX_N:
        raise ValueError(f"n must be between 0 and {MAX_N}")
    base, remainder = divmod(n, size)
    counts = [base + (1 if r < remainder else 0) for r in range(size)]
    displs = [sum(counts[:r]) for r in range(size)]
    return counts, displs


def local_squares(start: int, count: int) -> np.ndarray:
    """Squares of start+1 .. start+count as int64."""
    x = np.arange(start + 1, start + count + 1, dtype=np.int64)
    return x * x


def peak_rss_mb() -> float:
    """Peak resident memory of this process in MB (Linux reports KB, macOS bytes)."""
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return rss / (1024 * 1024) if sys.platform == "darwin" else rss / 1024


def squares_checksum(arr: np.ndarray) -> int:
    """Sum of squares modulo 2**64 (uint64 wrap-around is well defined), used to compare runs."""
    return int(arr.astype(np.uint64).sum(dtype=np.uint64))


def run(comm, n: int, gather: bool = True) -> dict | None:
    """Compute on every rank; return a summary on rank 0 (None elsewhere). Needs an mpi4py communicator."""
    from mpi4py import MPI

    rank, size = comm.Get_rank(), comm.Get_size()
    counts, displs = chunk_counts(n, size)
    comm.Barrier()
    t0 = MPI.Wtime()
    local = local_squares(displs[rank], counts[rank])
    t_compute = MPI.Wtime() - t0

    result = None
    if gather:
        if rank == 0:
            result = np.empty(n, dtype=np.int64)
        comm.Gatherv(local, [result, counts, displs, MPI.INT64_T] if rank == 0 else None, root=0)
    length = comm.reduce(int(local.size), op=MPI.SUM, root=0)
    last = comm.reduce(int(local[-1]) if local.size else 0, op=MPI.MAX, root=0)
    checksum = comm.reduce(squares_checksum(local), op=MPI.SUM, root=0)
    comm.Barrier()
    t_total = MPI.Wtime() - t0
    t_compute_max = comm.reduce(t_compute, op=MPI.MAX, root=0)
    rss = comm.gather(peak_rss_mb(), root=0)

    if rank != 0:
        return None
    summary = {
        "n": n, "ranks": size, "gather": gather,
        "length": length, "last_square": last, "checksum_mod_2_64": checksum % 2**64,
        "time_s": t_total, "compute_time_max_s": t_compute_max,
        "peak_rss_mb_per_rank": rss, "peak_rss_mb_rank0": rss[0],
    }
    if gather:
        assert result is not None
        summary["gathered_length"] = int(result.size)
        summary["gathered_last"] = int(result[-1]) if result.size else 0
        summary["first_squares"] = [int(v) for v in result[:5]]
        summary["_result"] = result
    return summary
