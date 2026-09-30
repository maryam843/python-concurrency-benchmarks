"""Process sum with multiprocessing.Pool: each worker returns its partial sum (a Python int, no overflow)."""

import multiprocessing

from parallel_sum.partition import chunk_bounds


def range_sum(bounds):
    start, end = bounds
    return sum(range(start, end + 1))


def calculate_sum_pool(n, num_processes, start_method=None):
    ctx = multiprocessing.get_context(start_method)
    with ctx.Pool(processes=num_processes) as pool:
        return sum(pool.map(range_sum, chunk_bounds(n, num_processes)))
