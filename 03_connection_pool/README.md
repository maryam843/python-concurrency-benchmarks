# 03 Connection pool and pool benchmarks (from A1-P1)

Originally Assignment 1 Part 1 of DSAI3202 (UDST, Spring 2025). Fixed in 2026.

## What it is

Two parts:

1. A database connection pool shared by 8 processes but holding only 2 connections. Every process must eventually get a connection, and no more than 2 may hold one at the same time.
2. The same "square every number" job done five ways (sequential, `Pool.map`, `apply_async` per item, `apply_async` on chunks, `ProcessPoolExecutor.map` with a chunk size) at n = 1e5 and 1e6, to show what process overhead costs.

## What was wrong in 2025

- My README described a semaphore, but the code had none. `get_connection()` returned `None` when the queue was empty, so 6 of the 8 processes printed "Waiting..." and quit. Only 2 of 8 ever got a connection (reproduced 3 times in the 2026 audit re-run and again in Phase 0).
- `tests/test_square.py` imported `pool_apply`, which did not exist (the whole file failed to import), and `test_release_connection` expected the queue to return the connection it had just been given, but a FIFO queue hands out the other free one first.
- `tests/__main__.py` discovered the tests but never ran them, so `python -m tests` exited 0 having run nothing.
- Every call appended its time to `outputs/timing_results.csv` with no run label, so the file kept growing with duplicate rows.

## The fix

`ConnectionPool` now takes a `multiprocessing.Semaphore(size)` permit before it takes a connection. `acquire()` blocks until another process releases one (or until an optional timeout), so waiting processes get their turn instead of giving up. The pool also counts the maximum number of holders at the same time, and the tests recompute that maximum from the timestamped event log.

## Result

<!-- table: t03_semaphore -->
| Processes | Pool size | Got a connection | Max holders at once | Exit codes | Total time (s) |
|---|---|---|---|---|---|
| 8 | 2 | 8 | 2 | 0, 0, 0, 0, 0, 0, 0, 0 | 6.61 |
<!-- /table -->

Pool benchmarks (4 workers):

<!-- table: t03_pool -->
| n | Method | Runs | Time (s), mean ± sd | Speedup vs sequential |
|---|---|---|---|---|
| 1e+05 | sequential | 3 | 0.0065 ± 0.0006 | 1.000x |
| 1e+05 | pool_map | 3 | 0.0272 ± 0.0046 | 0.238x |
| 1e+05 | apply_async_per_item | 3 | 11.5268 ± 0.7177 | 0.001x |
| 1e+05 | apply_async_chunked | 3 | 0.0470 ± 0.0045 | 0.138x |
| 1e+05 | process_pool_executor_chunksize | 3 | 0.0641 ± 0.0018 | 0.101x |
| 1e+06 | sequential | 3 | 0.0719 ± 0.0047 | 1.000x |
| 1e+06 | pool_map | 3 | 0.1815 ± 0.0071 | 0.396x |
| 1e+06 | apply_async_per_item | 1 | 123.3911 ± 0.0000 | 0.001x |
| 1e+06 | apply_async_chunked | 3 | 0.3539 ± 0.0153 | 0.203x |
| 1e+06 | process_pool_executor_chunksize | 3 | 0.5843 ± 0.0416 | 0.123x |
<!-- /table -->

The pool fix works: 8<!-- claim: 03_connection_pool/connection_pool_run.json | acquired | {} --> of 8 processes got a connection, and the most holding one at the same time was 2<!-- claim: 03_connection_pool/connection_pool_run.json | max_concurrent_holders | {} -->.

For the squares, **every parallel version was slower than the plain loop**, at both sizes. At n = 1e6 the sequential list comprehension took 0.0719 s<!-- claim: 03_connection_pool/pool_squares.json | rows[n=1000000,method=sequential].mean_s | {:.4f} s -->; `Pool.map` ran at 0.396x<!-- claim: 03_connection_pool/pool_squares.json | rows[n=1000000,method=pool_map].speedup | {:.3f}x -->, chunked `apply_async` at 0.203x<!-- claim: 03_connection_pool/pool_squares.json | rows[n=1000000,method=apply_async_chunked].speedup | {:.3f}x -->, `ProcessPoolExecutor` at 0.123x<!-- claim: 03_connection_pool/pool_squares.json | rows[n=1000000,method=process_pool_executor_chunksize].speedup | {:.3f}x -->, and `apply_async` with one task per number took 123.3911 s<!-- claim: 03_connection_pool/pool_squares.json | rows[n=1000000,method=apply_async_per_item].mean_s | {:.4f} s --> (one run). Squaring an int costs tens of nanoseconds; sending it to another process means pickling it, writing it to a pipe, unpickling it, and doing the same for the answer, which costs far more than the multiplication. Starting the pool costs more again. The chunk size is what separates slow from absurd: per-item tasks pay that overhead a million times. The lesson for real work: processes pay off only when each task carries much more computation than data (compare 02, where each process gets one big range and sends back one number).

`apply_async` with one task per item is not run at n = 1e7. At 1e6 it already creates a million tasks, a million result objects and two million pickled messages, and took about two minutes; at 1e7 all ten million result objects would be pending at once. The time grows with the number of tasks, so I stopped at 1e6 instead of risking the machine's memory.

## How to run

```bash
python 03_connection_pool/main.py                  # 8 processes, 2 connections, prints the event log
python -m connection_pool.benchmark                # n = 1e5 and 1e6 (apply_async per item at 1e6 takes minutes)
python -m pytest 03_connection_pool
```

The 2025 outputs (`timing_results.csv`, `parallel_logs.txt`, `pool_usage.json`) are kept unchanged in `results/03_connection_pool/saved_2025/`.
