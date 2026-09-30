# 01 Threads vs processes (from Lab 2)

Originally Lab 2 of DSAI3202 (UDST, Spring 2025): my first threads-and-processes notebook. Fixed and turned into a script in 2026.

## What it is

Two CPU-bound pure-Python loops from the lab: add n random integers, and join n random characters into a string. I run them five ways and time each one 5 times:

- sequential (one after the other),
- one thread per function (2 threads), one process per function (2 processes),
- two threads per function (4 threads), two processes per function (4 processes), where each function's n is split in half.

Every configuration does exactly the same work as the sequential run, with the same seeds, and the combined result is compared with the sequential result before any time is reported.

## Result (n = 1e7 per function)

<!-- table: t01 -->
| Configuration | Workers p | Time (s), mean ± sd of 5 | Speedup | Efficiency S/p |
|---|---|---|---|---|
| sequential | 1 | 9.54 ± 0.24 | 1.00x | 1.00 |
| threads_1_per_function | 2 | 10.11 ± 0.34 | 0.94x | 0.47 |
| processes_1_per_function | 2 | 4.86 ± 0.12 | 1.96x | 0.98 |
| threads_2_per_function | 4 | 10.38 ± 0.53 | 0.92x | 0.23 |
| processes_2_per_function | 4 | 2.54 ± 0.11 | 3.76x | 0.94 |
<!-- /table -->

![Speedup per configuration](../figures/01_threads_vs_processes.svg)

## What it shows: the GIL

Threads made this work slower, not faster: 0.94x<!-- claim: 01_threads_vs_processes/threads_vs_processes_n10000000.json | rows[config=threads_1_per_function].speedup | {:.2f}x --> with 2 threads and 0.92x<!-- claim: 01_threads_vs_processes/threads_vs_processes_n10000000.json | rows[config=threads_2_per_function].speedup | {:.2f}x --> with 4. Both loops are pure Python, and CPython's global interpreter lock (GIL) lets only one thread run Python bytecode at a time, so the threads take turns on one core and pay for the switching. Processes each have their own interpreter and their own GIL, so they really run in parallel: 1.96x<!-- claim: 01_threads_vs_processes/threads_vs_processes_n10000000.json | rows[config=processes_1_per_function].speedup | {:.2f}x --> with 2 processes and 3.76x<!-- claim: 01_threads_vs_processes/threads_vs_processes_n10000000.json | rows[config=processes_2_per_function].speedup | {:.2f}x --> with 4 on this 4-core machine (efficiency 0.94<!-- claim: 01_threads_vs_processes/threads_vs_processes_n10000000.json | rows[config=processes_2_per_function].efficiency | {:.2f} -->).

Rule I take from this: for CPU-bound pure-Python code, threads do not help; use processes (or move the loop into a library that releases the GIL, see 02 and 06). Python 3.13 has an optional free-threaded build without the GIL; I did not test it here.

## What was wrong in 2025 and how I fixed it

- **Different workload in the process cell.** The notebook's "processes" cell ran the numbers function twice instead of numbers plus letters, so its speedup compared two different jobs. Now every configuration runs the same tasks and must return the same answer.
- **Wrong p in the efficiency.** Efficiency was divided by `np = 4` although only 2 workers ran. Efficiency is now speedup divided by the real number of workers (`bench_common.efficiency`); a regression test runs the 2025 notebook cell and shows it fails the check.
- **Windows (spawn) could not run the process cell,** because the worker functions were defined inside the notebook. They now live in `threads_vs_processes/workloads.py`, and the notebook imports them.
- Two identical "two threads" cells with different labels were removed, and Amdahl's law now uses the number of workers instead of infinitely many.

## How to run

```bash
python -m threads_vs_processes.benchmark                 # n = 1e7, 5 repeats, writes results/01_threads_vs_processes/
python -m threads_vs_processes.benchmark --n 1000000 --repeats 3 --no-save    # quick look
python -m pytest 01_threads_vs_processes
```

The notebook (`First_trials_with_threads_and_processes_with_performance_metrics.ipynb`) is the fixed 2025 notebook. It runs headless in the tests with `python tools/run_notebooks.py`.
