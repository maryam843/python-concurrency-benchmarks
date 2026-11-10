# Design decisions

One line of "why" per choice. Numbers quoted here come from `results/`.

## Repository and history

- **One repo with six numbered folders.** The story is one question ("when does parallel Python help?"), and each folder answers a piece of it; one CI and one results folder keep the evidence in one place.
- **Per-folder `src/<package>/` with unique package names, installed with `pip install -e .`.** A plain `src` package in several folders would clash; unique names avoid that, and an installed package is what spawned worker processes and `mpiexec` ranks need to import the same code.
- **Each bug that was fixed keeps a regression test on the current code.** The test checks the behaviour the earlier version got wrong (for example, typecode `'i'` still reproduces the wrong 32-bit sum), so the fix cannot quietly come back.
- **MPI tests are skipped, not faked, when MPI is missing.** Windows CI has no MPI; the skip reason says so.
- **Notebook outputs are not committed.** Timings belong in `results/` with machine info; the notebook is executed headless as a test instead.
- **Figures are SVG generated from `results/` by `tools/make_figures.py`.** Text-based, small, reproducible from the JSON, and no screenshots.

## Measurement

- **Every benchmark checks the answer before it reports a time.** A fast wrong answer (the earlier int32 sum) is the failure this project is about.
- **One method for every timing: one untimed warm-up run, then several timed runs with `time.perf_counter`, and speedups from the medians.** The warm-up pays for one-off costs (imports, first-touch memory, a cold disk or network cache), and the median is not pulled by one slow run, which a mean of 3 to 5 runs is. Means, sample standard deviations and every run are saved too (`bench_common.timing.time_with_warmup`).
- **Pool start-up is inside the timed region.** That cost is real for anyone who writes `with Pool() as p: p.map(...)` once, and it is the reason small inputs get slower.
- **Efficiency divides by the number of workers that actually ran.** An earlier version of the notebook divided by 4 when 2 workers ran.
- **05 also pauses 2 s before each MPI run and needs at least 5 runs.** Back-to-back MPI runs alternated fast and slow on one virtual machine; the memory figures are the reliable result there.
- **A first timed run more than 3x the median is flagged** (information only). It shows a cold start the warm-up did not cover.
- **Seeds everywhere randomness is used** (01 workloads, 03 work durations, 04 random mode, fixtures). Same seed gives identical results (a test checks it).
- **Results JSON records OS, CPU model, core count, memory, Python and package versions, never the hostname or paths.** Timings are machine specific, and the machine must be described without leaking personal data.

## 01 threads vs processes

- **Same total work in every configuration** (n iterations of each function; "2 per function" splits each into halves). An earlier process cell ran a different workload, so its speedup meant nothing.
- **Executors (`ThreadPoolExecutor`, `ProcessPoolExecutor`) instead of raw `Thread`/`Process`.** They return the results so the combined answer can be compared with the sequential one.

## 02 parallel sum

- **Fix the overflow with `Array('q')` and also keep a `typecode` argument.** Passing `'i'` reproduces the earlier wrong value exactly, which proves the fix is the type and nothing else.
- **Rename `multiprocessing.py`/`threading.py`.** A file named like a stdlib module is imported instead of the stdlib when run as a script.
- **One implementation per method.** Duplicate sequential and thread versions were dropped.
- **NumPy is summed in blocks of 1e7.** The whole 1e8 array would need 800 MB; blocks keep memory flat at about 80 MB.
- **The closed form n(n+1)/2 is the test oracle, not a competitor.** It is O(1) and would make every benchmark pointless; it only checks answers.

## 03 connection pool

- **A `multiprocessing.Semaphore(size)` in front of the queue.** A permit guarantees a connection is waiting, so `get()` never blocks while holding nothing, and the semaphore is what limits the number of holders.
- **Timeout is optional and `None` means wait.** Every process must eventually get a connection; a timeout is there for callers that prefer to give up.
- **Max concurrent holders is tracked in shared memory and also recomputed from the event log in tests.** Two independent checks of "never more than 2".
- **The Manager handle is left out when the pool is pickled.** It cannot be pickled, which only shows up under spawn (Windows).
- **apply_async per item is not run at 1e7.** At 1e6 it already took about two minutes (`results/03_connection_pool/pool_squares.json`), and at 1e7 it would hold ten million pending result objects at once. A chunked apply_async shows the fix instead.
- **`multiprocessing_squares` is kept as an alias of `pool_map`.** They had identical bodies; benchmarking both would double-count one method.

## 04 sensor monitor

- **Keep the original module layout and names** (`simulate_sensor`, `process_temperatures`, `initialize_display`, `update_display`, the global dicts) and fix them in place, so the fixes are easy to compare.
- **Readings and averages in separate dicts.** The earlier crash came from storing both in one.
- **The processor drains the whole queue every interval.** One item per 5 s could never keep up with 3 readings per second.
- **`Condition` shares the `RLock`.** The display waits on the same lock that protects the data, so a redraw never sees half an update.
- **ANSI cursor-up plus clear-line instead of clearing the screen.** The console must not be erased, and it works on Linux, macOS and Windows 10+ terminals.
- **Replay one real station's temperature series as several sensors with different start rows.** The UCI file has one temperature column; different starting days give real, different streams, and the README says exactly that.
- **-200 readings are skipped and counted, not replaced.** Inventing a value would change the averages.
- **Synthetic air-quality fixture in the real file format.** CI must not download data, and the parser is tested on the exact quirks (semicolons, decimal commas, -200, empty trailing rows).

## 05 MPI

- **NumPy int64 arrays and `Gatherv` instead of lists and `gather`.** Buffers are copied, not pickled, which is what made 1e8 possible on one machine.
- **Two modes: gather everything, or reduce only (length, last square, checksum).** Shows what collecting the result costs in time and memory.
- **The work split is the supplied script's split, unchanged.** Only the data representation changed, so the memory comparison with the earlier version is fair.
- **`mpi_program.py` sends to itself with one rank.** The example should not crash just because only one process was started.
- **`hostfile.example` with `node1`/`node2`.** Real IP addresses and hostnames never enter the repo. Every MPI result here was measured on one machine; the hostfile only shows how to run on several.

## 06 NYC taxi pipeline

- **Latest complete year of TLC data (2025), 12 monthly files.** A full year makes the summaries meaningful; the files are downloaded, never committed.
- **Read only the six columns the rules and summaries need.** Less I/O and memory for every method equally.
- **Cleaning rules applied in a fixed order, each removed row counted once.** The "share removed per month" answer is then well defined.
- **Missing passenger_count is kept.** It is missing for 23.8 % of the year's trips (`passenger_count_missing_share` in `results/06_nyc_taxi_pipeline/stage2_cpu.json`); it is unknown, not invalid, and dropping it would remove a quarter of the year.
- **Month summaries store sums and counts, not means.** Combining months (per rank, per worker) is then exact, so every method's yearly answer is identical, and the tests assert equality, not "close".
- **Stage 1 downloads into a fresh temp folder each run.** No run can be served from a local copy; the cached copy used by later stages is a separate download.
- **Stage 3 sends months round-robin and gathers small dicts.** A month is the natural unit (one file); the gathered data is kilobytes.
- **SQLite with the summaries, not the raw trips.** The five questions only need the summaries, and it keeps the database tiny.
- **SQL answers are tested against an independent pandas implementation of the rules** (written with `df.query`), not against the pipeline's own code.
- **Tests block every non-local URL.** A test that accidentally downloaded real data during development led to this guard.
