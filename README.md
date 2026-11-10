# python-concurrency-benchmarks

Originally built for DSAI3202 Parallel & Distributed Computing, UDST, Spring 2025. Fixed and extended in 2026.

## In plain English

1. **What it is:** my measured guide to when threads, processes and MPI actually make Python faster, built from five of my DSAI3202 labs plus one new real-data pipeline.
2. **Problem and who it helps:** people add threads or processes to slow Python code and get no speedup, a slowdown, or a wrong answer; this shows which tool fits which kind of work, with the numbers.
3. **How it works:** a job (sums, squares, sensor readings, NYC taxi trips) goes in; it is split into pieces and run sequentially, with threads, with processes and with MPI; every version must give the same answer before its time counts; the output is a results file per experiment and tables and charts made from those files.
4. **2025 vs 2026:** in 2025 I wrote the labs (threads vs processes, parallel sum, connection pool, sensor monitor, MPI on two university VMs). In 2026 I fixed the bugs an audit found (a 32-bit overflow, a missing semaphore, a crashing thread, wrong formulas), wrote tests for all of it, and **added** the NYC taxi pipeline and a replay of real air-quality readings.
5. **Main honest result:** processes gave up to 3.77x<!-- claim: 02_parallel_sum/parallel_sum.json | rows[n=100000000,method=processes_shared_array_int64].speedup | {:.2f}x --> on pure-Python CPU work where threads gave 0.96x<!-- claim: 02_parallel_sum/parallel_sum.json | rows[n=100000000,method=threads].speedup | {:.2f}x -->, and threads gave 3.71x<!-- claim: 06_nyc_taxi_pipeline/stage1_download.json | rows[workers=4].speedup_vs_first | {:.2f}x --> on downloads. Caveat: all 2026 runs are on one 4-core cloud machine, so the timings are specific to it.
6. **Why it matters for jobs in Qatar:** data teams in energy, banking, aviation and government process large files every day; choosing the right kind of parallelism, and proving the answer is still correct, saves compute time and avoids silent errors.

**30-second version:** I took my parallel-computing labs, reproduced and fixed their bugs, and turned them into a tested, measured guide. Threads help when the program waits (downloads) or when the library does the work in C (PyArrow, pandas); processes help for pure-Python number crunching; vectorising with NumPy can be as fast as four processes; MPI is for when one machine is not enough.

> Demo video: placeholder. I will record a short screen capture of the live sensor monitor and the pipeline myself and link it here.

## The problem

Python has a global interpreter lock (GIL): only one thread runs Python bytecode at a time. So "add threads" does not speed up a Python loop, "add processes" costs start-up time and data copying, and a parallel version can be fast and wrong (my 2025 parallel sum returned 1,784,293,664 instead of 500,000,500,000 without any error). I wanted answers I could defend with my own measurements, not rules copied from a blog.

## Data

- **Synthetic workloads** (random numbers, ranges, squares) for folders 01 to 03 and 05, seeded so every run is reproducible.
- **UCI Air Quality** (De Vito, 2008, CC BY 4.0): hourly temperatures from one station, replayed as live sensor readings in folder 04 (added in 2026).
- **NYC TLC yellow taxi trips, all of 2025**: 12 monthly Parquet files, 48,722,602<!-- claim: 06_nyc_taxi_pipeline/stage2_cpu.json | yearly.rows_raw | {:,} --> trips (folder 06, added in 2026).

Datasets are downloaded by scripts and never committed. The tests and CI use small synthetic fixtures in the same formats (`tests/fixtures/`), and a guard stops any test from reaching the internet.

## Method

Every experiment checks correctness before timing (closed form n(n+1)/2, sequential result, or a separate pandas implementation), repeats each measurement (3, 5 or 10 runs), reports mean and standard deviation, and computes efficiency with the number of workers that really ran. Results are JSON files in `results/` with the OS, CPU, core count, memory, Python and package versions, timestamp and seed. The tables in the READMEs are generated from those files, and `tools/check_readme_claims.py` fails if any number in a README does not match them.

## Results

| Folder | Question | Key result (4-core machine) |
|---|---|---|
| [01 threads vs processes](01_threads_vs_processes/) (Lab 2) | Do threads speed up pure-Python CPU work? | threads 0.95x<!-- claim: 01_threads_vs_processes/threads_vs_processes_n10000000.json | rows[config=threads_2_per_function].speedup | {:.2f}x -->, processes 3.86x<!-- claim: 01_threads_vs_processes/threads_vs_processes_n10000000.json | rows[config=processes_2_per_function].speedup | {:.2f}x --> with 4 workers |
| [02 parallel sum](02_parallel_sum/) (Lab 3) | When do processes pay off, and what about NumPy? | n = 1e6: best process version 1.44x<!-- claim: 02_parallel_sum/parallel_sum.json | rows[n=1000000,method=processes_shared_array_int64].speedup | {:.2f}x -->; n = 1e8: 3.77x<!-- claim: 02_parallel_sum/parallel_sum.json | rows[n=100000000,method=processes_shared_array_int64].speedup | {:.2f}x -->; NumPy on one core 4.33x<!-- claim: 02_parallel_sum/parallel_sum.json | rows[n=100000000,method=numpy_vectorised].speedup | {:.2f}x --> |
| [03 connection pool](03_connection_pool/) (Assignment 1) | Semaphore-guarded pool; pool overhead | 8<!-- claim: 03_connection_pool/connection_pool_run.json | acquired | {} --> of 8 processes served, never more than 2<!-- claim: 03_connection_pool/connection_pool_run.json | max_concurrent_holders | {} --> at once; squaring 1e6 numbers with `Pool.map` ran at 0.352x<!-- claim: 03_connection_pool/pool_squares.json | rows[n=1000000,method=pool_map].speedup | {:.3f}x --> |
| [04 sensor monitor](04_sensor_monitor/) (Lab 4) | Producer/consumer threads with a Condition | processor survives, queue drained every interval, averages match pandas; real UCI readings (added in 2026) |
| [05 MPI](05_mpi_multi_node/) (Lab 6) | Can n = 1e8 run on one machine? | 2025 code at n = 1e7: 2969 MB<!-- claim: 05_mpi_multi_node/earlier_calculate_squares.json | rows[n=10000000,ranks=1].peak_rss_mb_rank0 | {:.0f} MB --> on rank 0; 2026 at n = 1e8: 1573 MB<!-- claim: 05_mpi_multi_node/mpi_squares_scaling_gatherv.json | rows[n=100000000,ranks=1].peak_rss_mb_rank0_max | {:.0f} MB --> (gather all) or 238 MB<!-- claim: 05_mpi_multi_node/mpi_squares_scaling_reduce_only.json | rows[n=100000000,ranks=4].peak_rss_mb_rank0_max | {:.0f} MB --> per rank (reduce only, 4 ranks) |
| [06 NYC taxi pipeline](06_nyc_taxi_pipeline/) (added in 2026) | The rule of thumb on real data | downloads: 4 threads 3.71x<!-- claim: 06_nyc_taxi_pipeline/stage1_download.json | rows[workers=4].speedup_vs_first | {:.2f}x -->; cleaning: 4 threads 2.14x<!-- claim: 06_nyc_taxi_pipeline/stage2_cpu.json | rows[method=threads,workers=4].speedup | {:.2f}x -->, 4 processes 2.26x<!-- claim: 06_nyc_taxi_pipeline/stage2_cpu.json | rows[method=processes,workers=4].speedup | {:.2f}x -->; MPI 4 ranks 3.41x<!-- claim: 06_nyc_taxi_pipeline/stage3_mpi.json | rows[ranks=4].speedup_vs_1_rank | {:.2f}x --> |

![Speedup by stage, NYC taxi pipeline](figures/06_speedup_by_stage.svg)

### The rule of thumb, and the numbers behind it

- **Threads for waiting.** Downloading 12 files: 3.71x<!-- claim: 06_nyc_taxi_pipeline/stage1_download.json | rows[workers=4].speedup_vs_first | {:.2f}x --> with 4 threads (folder 06). A thread waiting on the network releases the GIL.
- **Threads also work when a C library does the work.** PyArrow and pandas release the GIL, so cleaning a year of taxi trips got 2.14x<!-- claim: 06_nyc_taxi_pipeline/stage2_cpu.json | rows[method=threads,workers=4].speedup | {:.2f}x --> from 4 threads, a bit more than 4 processes (2.26x<!-- claim: 06_nyc_taxi_pipeline/stage2_cpu.json | rows[method=processes,workers=4].speedup | {:.2f}x -->). With PyArrow's own threading turned off, processes won instead (3.59x<!-- claim: 06_nyc_taxi_pipeline/stage2_cpu_arrow_1_thread.json | rows[method=processes,workers=4].speedup | {:.2f}x --> against 1.92x<!-- claim: 06_nyc_taxi_pipeline/stage2_cpu_arrow_1_thread.json | rows[method=threads,workers=4].speedup | {:.2f}x -->), so check what the library already does before adding workers.
- **Processes for pure-Python CPU work, when each task is big.** 3.86x<!-- claim: 01_threads_vs_processes/threads_vs_processes_n10000000.json | rows[config=processes_2_per_function].speedup | {:.2f}x --> (01) and 3.77x<!-- claim: 02_parallel_sum/parallel_sum.json | rows[n=100000000,method=processes_shared_array_int64].speedup | {:.2f}x --> (02) on 4 cores, but a loss on small tasks: 0.352x<!-- claim: 03_connection_pool/pool_squares.json | rows[n=1000000,method=pool_map].speedup | {:.3f}x --> for `Pool.map` over a million tiny squares (03), where sending data between processes costs more than the work.
- **Vectorise first.** One NumPy process summed 1..1e8 at 4.33x<!-- claim: 02_parallel_sum/parallel_sum.json | rows[n=100000000,method=numpy_vectorised].speedup | {:.2f}x -->, level with four processes (with a large spread between its runs; see 02).
- **MPI to scale out, not to speed up a light job on one machine.** Its biggest win here was memory (05); for the taxi months, 4 ranks took about as long as 4 threads (06). In 2025 I ran MPI across two university Linux VMs; in 2026 everything ran on one machine.

## What went wrong in 2025 and how I fixed it

| Bug (2025) | What happened | Fix (2026) | Where |
|---|---|---|---|
| int32 overflow | `multiprocessing.Array('i')` wrapped each partial sum: 1,784,293,664 instead of 500,000,500,000 at n = 1e6, no error | `Array('q')` (64-bit); regression test runs the 2025 file | 02 |
| stdlib shadowing | files named `multiprocessing.py` and `threading.py` were imported instead of the real modules | renamed into a package; a test fails on any stdlib-named file | 02 |
| missing semaphore | README described one, code had none: 2 of 8 processes got a connection, 6 gave up | `multiprocessing.Semaphore` with blocking acquire and timeout | 03 |
| sensor thread crash | averages dict held a list, then a float: `'float' object has no attribute 'append'`, and the queue grew without bound | readings and averages kept apart, queue drained every interval, Condition added | 04 |
| wrong efficiency p | efficiency divided by 4 when 2 workers ran; the process cell also ran a different workload | efficiency = speedup / real workers; same workload everywhere | 01 |
| wrong Gustafson | N - (1 - P)N (3.60) instead of N - (1 - P)(N - 1) (3.70) for N = 4, P = 0.9 | fixed formula in `laws.py` | 02 |

Also fixed: worker functions that could not be pickled under "spawn" (Windows), a notebook process cell that failed under spawn, tests that imported functions that did not exist, a test runner that ran zero tests and passed, `mpi_program.py` crashing with one rank, and n = 1e8 running out of memory in the MPI squares. Each bug has a regression test that runs the 2025 code from its import commit and shows it fails a check that the 2026 code passes.

## Limitations

- All 2026 measurements are from one 4-core cloud container. Timings depend on the machine; the ratios are more portable than the seconds, and even those vary (some standard deviations in 02 and 05 are large).
- No multi-machine run in 2026. The two-VM MPI run is 2025 evidence (a screenshot in my private coursework repo), not re-verified here.
- One year of taxi data (829,973,299<!-- claim: 06_nyc_taxi_pipeline/manifest.json | total_bytes | {:,} --> bytes of Parquet) is a real dataset, not "big data". The pipeline shows method differences, not scale.
- The sensor replay uses one station's temperature series for all sensors, offset by a week each.
- I did not test Python's free-threaded build (no GIL).

## What I learned

- A parallel version is only faster if it is also right; I now check the answer before I look at the time.
- The GIL is not "threads are useless": they were my best tool for downloads and for pandas/PyArrow work.
- Process start-up and pickling decide small jobs; the chunk size mattered more than the number of workers.
- Libraries already use threads inside, so adding workers on top can fight for the same cores; I only found this by testing my own explanation.
- Memory, not CPU, was the limit for the MPI squares, and a typed array fixed what more ranks could not.
- Tests that run my old code against my new code made every fix concrete and easy to explain.
- Downloads can end early without an error, so I check sizes and hashes now.

## How to run

```bash
python3.12 -m venv .venv && . .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt && pip install -e .
pip install -r requirements-mpi.txt                   # optional, needs an MPI runtime (Linux: apt install openmpi-bin libopenmpi-dev)

python -m pytest                                      # all tests (MPI tests skip without MPI)
PCB_START_METHOD=spawn python -m pytest               # force the Windows/macOS start method on Linux
python tools/check_readme_claims.py                   # every README number against results/
python tools/pii_scan.py --worktree                   # personal data and secrets, full git history

python tools/run_benchmarks.py                        # download the data and regenerate results/ and figures/
```

Each folder's README has its own commands. The folders:

- `01_threads_vs_processes/`, `02_parallel_sum/`, `03_connection_pool/`, `04_sensor_monitor/`, `05_mpi_multi_node/`: the 2025 labs, fixed.
- `06_nyc_taxi_pipeline/`: added in 2026.
- `results/` (JSON), `figures/` (SVG from results), `docs/DECISIONS.md` (why each design choice), `tools/`, `tests/`.

The git history starts with one import commit per 2025 branch, dated with that branch's last 2025 commit, followed by the 2026 fixes.

## Credits

See [CREDITS.md](CREDITS.md): course-provided files (the Lab 6 squares script, the mpi4py example, the Lab 2 notebook headings), the NYC TLC and UCI datasets and their terms, and the libraries used.

## Licence

MIT, see [LICENSE](LICENSE).
