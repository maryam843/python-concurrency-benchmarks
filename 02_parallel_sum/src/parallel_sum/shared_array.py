"""Process sum with a shared multiprocessing.Array.

Earlier bug: the array used typecode 'i' (signed 32-bit). Each partial sum above 2**31 - 1 wrapped
around, so n = 10**6 returned 1,784,293,664 instead of 500,000,500,000. The fix is typecode 'q'
(signed 64-bit), which holds partial sums up to about 9.2e18, i.e. n up to about 4.29e9.
"""

import multiprocessing
import time

from parallel_sum.partition import chunk_bounds


def process_sum(start, end, result, index):
    result[index] = sum(range(start, end + 1))


def parallel_process_sum(n, num_processes, typecode="q", start_method=None):
    ctx = multiprocessing.get_context(start_method)
    result = ctx.Array(typecode, num_processes)
    processes = []
    for i, (start, end) in enumerate(chunk_bounds(n, num_processes)):
        process = ctx.Process(target=process_sum, args=(start, end, result, i))
        processes.append(process)
        process.start()

    # Wait for all processes to complete
    for process in processes:
        process.join()

    return sum(result)


if __name__ == "__main__":
    n = 10**6
    num_processes = 4
    start_time = time.perf_counter()
    total_sum = parallel_process_sum(n, num_processes)
    end_time = time.perf_counter()
    print(f"Sum: {total_sum}")
    print(f"Execution Time: {end_time - start_time} seconds")
