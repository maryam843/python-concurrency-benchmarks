"""Thread sum (from my L3-P1 code). The worker is module level, like the other versions."""

import threading
import time

from parallel_sum.partition import chunk_bounds


def worker(start, end, result, index):
    result[index] = sum(range(start, end + 1))


def calculate_sum_parallel(n, num_threads):
    threads = []
    result = [0] * num_threads

    start_time = time.perf_counter()

    for i, (start, end) in enumerate(chunk_bounds(n, num_threads)):
        thread = threading.Thread(target=worker, args=(start, end, result, i))
        threads.append(thread)
        thread.start()

    for thread in threads:
        thread.join()

    total_sum = sum(result)
    end_time = time.perf_counter()
    execution_time = end_time - start_time
    return total_sum, execution_time
