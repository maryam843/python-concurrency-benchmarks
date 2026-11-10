"""Squares of a list of numbers, computed five ways.

The per-call timing that the earlier version wrote into a CSV is gone; benchmark.py times these from outside.
"""

import concurrent.futures
import multiprocessing


def square(num: int) -> int:
    """Returns the square of a given number."""
    return num * num


def square_chunk(nums: list) -> list:
    return [n * n for n in nums]


def default_workers() -> int:
    return min(8, multiprocessing.cpu_count())


def sequential_squares(numbers: list) -> list:
    """Calculates squares sequentially."""
    return [square(num) for num in numbers]


def pool_map(numbers: list, workers: int | None = None, start_method: str | None = None) -> list:
    """Calculates squares using Pool.map() (Python picks the chunk size)."""
    ctx = multiprocessing.get_context(start_method)
    with ctx.Pool(processes=workers or default_workers()) as pool:
        return pool.map(square, numbers)


# In the earlier version multiprocessing_squares() had exactly the same body as pool_map(); kept as an alias.
multiprocessing_squares = pool_map


def pool_apply_async(numbers: list, workers: int | None = None, start_method: str | None = None) -> list:
    """One apply_async task per number: one pickled message each way per item (the slow way)."""
    ctx = multiprocessing.get_context(start_method)
    with ctx.Pool(processes=workers or default_workers()) as pool:
        results = [pool.apply_async(square, (num,)) for num in numbers]
        return [res.get() for res in results]


def pool_apply_async_chunked(numbers: list, workers: int | None = None, chunks_per_worker: int = 4,
                             start_method: str | None = None) -> list:
    """apply_async over a few large chunks instead of one task per item."""
    workers = workers or default_workers()
    n_chunks = max(1, workers * chunks_per_worker)
    size = max(1, -(-len(numbers) // n_chunks))
    chunks = [numbers[i:i + size] for i in range(0, len(numbers), size)]
    ctx = multiprocessing.get_context(start_method)
    with ctx.Pool(processes=workers) as pool:
        results = [pool.apply_async(square_chunk, (c,)) for c in chunks]
        return [x for res in results for x in res.get()]


def concurrent_futures(numbers: list, workers: int | None = None, start_method: str | None = None) -> list:
    """ProcessPoolExecutor.map with an explicit chunksize (about 4 chunks per worker)."""
    workers = workers or default_workers()
    chunksize = max(len(numbers) // (workers * 4), 100)
    ctx = multiprocessing.get_context(start_method)
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers, mp_context=ctx) as executor:
        return list(executor.map(square, numbers, chunksize=chunksize))
