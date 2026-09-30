"""Process sum with a result Queue (from my L3-P1 code).

2025 bug: `worker` was defined inside calculate_sum_multiprocessing. A nested function cannot be
pickled, so under the "spawn" start method (the default on Windows and macOS) it failed with
"Can't pickle local object". The worker now lives at module level.
"""

import multiprocessing
import time

from parallel_sum.partition import chunk_bounds


def worker(start, end, queue):
    queue.put(sum(range(start, end + 1)))


def calculate_sum_multiprocessing(n, num_processes, start_method=None):
    ctx = multiprocessing.get_context(start_method)
    processes = []
    queue = ctx.Queue()

    start_time = time.perf_counter()

    for start, end in chunk_bounds(n, num_processes):
        process = ctx.Process(target=worker, args=(start, end, queue))
        processes.append(process)
        process.start()

    total_sum = sum(queue.get() for _ in processes)

    for process in processes:
        process.join()

    end_time = time.perf_counter()
    execution_time = end_time - start_time
    return total_sum, execution_time
