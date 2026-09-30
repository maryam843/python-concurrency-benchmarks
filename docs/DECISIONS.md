# Design decisions

One line of "why" per choice. Numbers quoted here come from `results/` or from the 2026 audit re-run cited in the 2026 report.

## Repository and history

- **One repo with six numbered folders.** The story is one question ("when does parallel Python help?"), and each lab answers a piece of it; one CI and one results folder keep the evidence in one place.
- **Import commits keep the 2025 code as submitted (personal data removed), fixes come after.** Anyone can `git diff` a 2025 import against today and see exactly what I changed and why.
- **Per-folder `src/<package>/` with unique package names, installed with `pip install -e .`.** Several folders had a `src` package in 2025; unique names avoid clashes, and an installed package is what spawned worker processes and `mpiexec` ranks need to import the same code.
- **Regression tests read the 2025 code from the import commits (`git show`).** The bug stays reproducible without keeping broken copies in the working tree; each regression check is applied to both versions: it must fail on 2025 and pass on 2026.
- **Tests are skipped, not faked, when history or MPI is missing.** A shallow clone cannot run the 2025 checks and Windows CI has no MPI; the skip reason says so.
- **Notebook outputs are not committed.** Timings belong in `results/` with machine info; the notebook is executed headless as a test instead.
- **Figures are SVG generated from `results/` by `tools/make_figures.py`.** Text-based, small, reproducible from the JSON, and no screenshots.

## Measurement

- **Every benchmark checks the answer before it reports a time.** A fast wrong answer (the 2025 int32 sum) is the failure this project is about.
- **`time.perf_counter`, several repeats, mean and sample standard deviation.** Single runs were a 2025 weakness; the spread shows how much a difference can be trusted.
- **Pool start-up is inside the timed region.** That cost is real for anyone who writes `with Pool() as p: p.map(...)` once, and it is the reason small inputs get slower.
- **Efficiency divides by the number of workers that actually ran.** The 2025 notebook divided by 4 when 2 workers ran.
- **One untimed warm-up where lazy initialisation would distort the first run** (NumPy in 02, first-touch memory in 05). Not used in 01 and 03, where no such effect showed up.
- **Seeds everywhere randomness is used** (01 workloads, 03 work durations, 04 random mode, fixtures). Same seed gives identical results (T8).
- **Results JSON records OS, CPU model, core count, memory, Python and package versions, never the hostname or paths.** Timings are machine specific, and the machine must be described without leaking personal data.

## 01 threads vs processes

- **Same total work in every configuration** (n iterations of each function; "2 per function" splits each into halves). The 2025 process cell ran a different workload, so its speedup meant nothing.
- **Executors (`ThreadPoolExecutor`, `ProcessPoolExecutor`) instead of raw `Thread`/`Process`.** They return the results so the combined answer can be compared with the sequential one.

## 02 parallel sum

- **Fix the overflow with `Array('q')` and also keep a `typecode` argument.** Passing `'i'` reproduces the 2025 value exactly, which proves the fix is the type and nothing else.
- **Rename `multiprocessing.py`/`threading.py`.** A file named like a stdlib module is imported instead of the stdlib when run as a script.
- **Drop the L3-P2 `sequential.py` and `threading.py`.** They duplicated the L3-P1 versions; one implementation per method.
- **NumPy is summed in blocks of 1e7.** The whole 1e8 array would need 800 MB; blocks keep memory flat at about 80 MB.
- **The closed form n(n+1)/2 is the test oracle, not a competitor.** It is O(1) and would make every benchmark pointless; it only checks answers.

## 03 connection pool

- **A `multiprocessing.Semaphore(size)` in front of the queue.** A permit guarantees a connection is waiting, so `get()` never blocks while holding nothing, and the semaphore is the thing the brief asked for.
- **Timeout is optional and `None` means wait.** The brief wants every process to eventually get a connection; a timeout is there for callers that prefer to give up.
- **Max concurrent holders is tracked in shared memory and also recomputed from the event log in tests.** Two independent checks of "never more than 2".
- **The Manager handle is left out when the pool is pickled.** It cannot be pickled, which only shows up under spawn (Windows).
- **apply_async per item is not run at 1e7.** At 1e6 it already takes minutes; at 1e7 the 2026 audit re-run was killed for memory. A chunked apply_async shows the fix instead.
- **`multiprocessing_squares` is kept as an alias of `pool_map`.** In 2025 they had identical bodies; benchmarking both would double-count one method.

## 04 sensor monitor

- **Keep my 2025 module layout and names** (`simulate_sensor`, `process_temperatures`, `initialize_display`, `update_display`, the global dicts) and fix them in place, as asked.
- **Readings and averages in separate dicts.** The 2025 crash came from storing both in one.
- **The processor drains the whole queue every interval.** One item per 5 s could never keep up with 3 readings per second.
- **`Condition` shares the `RLock`.** The display waits on the same lock that protects the data, so a redraw never sees half an update.
- **ANSI cursor-up plus clear-line instead of clearing the screen.** The brief forbids erasing the console, and it works on Linux, macOS and Windows 10+ terminals.
- **Replay one real station's temperature series as several sensors with different start rows.** The UCI file has one temperature column; different starting days give real, different streams, and the README says exactly that.
- **-200 readings are skipped and counted, not replaced.** Inventing a value would change the averages.
- **Synthetic air-quality fixture in the real file format.** CI must not download data, and the parser is tested on the exact quirks (semicolons, decimal commas, -200, empty trailing rows).

## 05 MPI

- **NumPy int64 arrays and `Gatherv` instead of lists and `gather`.** Buffers are copied, not pickled, which is what made 1e8 possible on one machine.
- **Two modes: gather everything, or reduce only (length, last square, checksum).** Shows what collecting the result costs in time and memory.
- **The work split is the course script's split, unchanged.** Only the data representation changed, so the comparison with 2025 is fair.
- **`mpi_program.py` sends to itself with one rank.** The example should not crash just because only one process was started.
- **`hostfile.example` with `node1`/`node2`.** The real lab IP addresses and hostnames never enter the repo.

## 06 NYC taxi pipeline

- **Latest complete year (2025), 12 monthly files.** A full year makes the summaries meaningful; the files are downloaded, never committed.
- **Read only the six columns the rules and summaries need.** Less I/O and memory for every method equally.
- **Cleaning rules applied in a fixed order, each removed row counted once.** The "share removed per month" answer is then well defined.
- **Missing passenger_count is kept.** About 15 % of trips lack it; it is unknown, not invalid.
- **Month summaries store sums and counts, not means.** Combining months (per rank, per worker) is then exact, so every method's yearly answer is identical, and the tests assert equality, not "close".
- **Stage 1 downloads into a fresh temp folder each run.** No run can be served from a local copy; the cached copy used by later stages is a separate download.
- **Stage 3 sends months round-robin and gathers small dicts.** A month is the natural unit (one file); the gathered data is kilobytes.
- **SQLite with the summaries, not the raw trips.** The five questions only need the summaries, and it keeps the database tiny.
- **SQL answers are tested against an independent pandas implementation of the rules** (written with `df.query`), not against the pipeline's own code.
- **Tests block every non-local URL.** A test that accidentally downloaded real data during development led to this guard.
