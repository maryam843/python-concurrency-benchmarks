# 05 MPI squares

`calculate_squares.py` was supplied with the original exercise and is modified here so that n = 1e8 runs on one machine (see its header and `CREDITS.md`).

## What it is

Compute the squares of 1..n spread over MPI ranks, collect them at rank 0, and print the length, the last square and the time. `mpi_program.py` is the standard mpi4py send/recv example.

**All runs below are on a single machine** (4 cores). Nothing here was measured across machines.

## Bugs fixed in the earlier version

- **n = 1e8 ran out of memory.** Each rank built a Python list of NumPy scalars and rank 0 collected them with `comm.gather` (pickled objects). Measured with the earlier script (below), n = 1e7 already needed about 3 GB on rank 0, too much to reach 1e8 on a 15 GB machine. Now each rank fills one int64 array and rank 0 receives the pieces straight into one preallocated array with `comm.Gatherv` (a buffer copy, no pickling). `--no-gather` goes further: only the length, the last square and a checksum are combined with `comm.reduce`, and no rank ever holds all the squares.
- **n was hard-coded to 10, and the script printed the whole list** (as `np.int64(1)`, ... with NumPy 2) instead of the length, last square and time. n now comes from the command line.
- **`mpi_program.py` crashed with one rank** (`MPI_ERR_RANK: invalid rank`, it sent to rank 1 which did not exist). With one rank it now sends to itself.

## Result: single machine, n = 1e7 and 1e8, 1/2/4 ranks, 10 runs each (plus one untimed warm-up)

Gather everything at rank 0 (`Gatherv`):

<!-- table: t05_gatherv -->
| n | Ranks | Median time (s) of 10 | Mean ± sd (s) | Speedup vs 1 rank (medians) | Efficiency | Peak memory rank 0 (MB) |
|---|---|---|---|---|---|---|
| 1e+07 | 1 | 0.064 | 0.066 ± 0.007 | 1.00x | 1.00 | 200 |
| 1e+07 | 2 | 0.047 | 0.050 ± 0.011 | 1.37x | 0.69 | 162 |
| 1e+07 | 4 | 0.046 | 0.046 ± 0.005 | 1.40x | 0.35 | 143 |
| 1e+08 | 1 | 0.746 | 0.748 ± 0.049 | 1.00x | 1.00 | 1573 |
| 1e+08 | 2 | 0.567 | 0.567 ± 0.026 | 1.32x | 0.66 | 1192 |
| 1e+08 | 4 | 0.449 | 0.465 ± 0.049 | 1.66x | 0.42 | 1001 |
<!-- /table -->

Reduce only (`--no-gather`):

<!-- table: t05_reduce -->
| n | Ranks | Median time (s) of 10 | Mean ± sd (s) | Speedup vs 1 rank (medians) | Efficiency | Peak memory rank 0 (MB) |
|---|---|---|---|---|---|---|
| 1e+07 | 1 | 0.040 | 0.042 ± 0.009 | 1.00x | 1.00 | 123 |
| 1e+07 | 2 | 0.019 | 0.020 ± 0.002 | 2.07x | 1.04 | 86 |
| 1e+07 | 4 | 0.011 | 0.012 ± 0.003 | 3.54x | 0.88 | 67 |
| 1e+08 | 1 | 0.427 | 0.421 ± 0.019 | 1.00x | 1.00 | 810 |
| 1e+08 | 2 | 0.223 | 0.226 ± 0.014 | 1.91x | 0.96 | 429 |
| 1e+08 | 4 | 0.114 | 0.114 ± 0.011 | 3.75x | 0.94 | 238 |
<!-- /table -->

![MPI scaling](../figures/05_mpi_scaling.svg)

**The reliable win is memory.** The earlier list-based script, measured with only n changed (`results/05_mpi_multi_node/earlier_calculate_squares.json`): at n = 1e7 its rank 0 peaked at 2969 MB<!-- claim: 05_mpi_multi_node/earlier_calculate_squares.json | rows[n=10000000,ranks=1].peak_rss_mb_rank0 | {:.0f} MB --> with 1 rank and the run took 49.3 s<!-- claim: 05_mpi_multi_node/earlier_calculate_squares.json | rows[n=10000000,ranks=1].wall_s_incl_startup | {:.1f} s -->. Memory grows linearly with n, so 1e8 would need roughly ten times that, about 30 GB, which this 15 GB machine does not have; I did not run it. The current version handles n = 1e8 with 1573 MB<!-- claim: 05_mpi_multi_node/mpi_squares_scaling_gatherv.json | rows[n=100000000,ranks=1].peak_rss_mb_rank0_max | {:.0f} MB --> on rank 0 when it gathers everything (the 800 MB result plus its own 800 MB piece), and with 238 MB<!-- claim: 05_mpi_multi_node/mpi_squares_scaling_reduce_only.json | rows[n=100000000,ranks=4].peak_rss_mb_rank0_max | {:.0f} MB --> per rank in reduce-only mode with 4 ranks.

**The speedups are modest, so memory is the headline.** Squaring is one multiplication per 8 bytes of memory, so the run time is mostly allocating and touching memory, not computing; each timed run is well under 2 seconds. The spread is in the tables (mean ± sd over 10 runs, each after a short pause); it is largest for the shortest runs at n = 1e7. Where the work is not dominated by one big allocation it scales: reduce-only at n = 1e7 went from 0.042 s<!-- claim: 05_mpi_multi_node/mpi_squares_scaling_reduce_only.json | rows[n=10000000,ranks=1].mean_s | {:.3f} s --> on 1 rank to 3.54x<!-- claim: 05_mpi_multi_node/mpi_squares_scaling_reduce_only.json | rows[n=10000000,ranks=4].speedup_vs_1_rank | {:.2f}x --> on 4. With `Gatherv` all squares still have to be copied into one 800 MB array on rank 0, a single-machine memory copy that more ranks barely speed up: at n = 1e8, 4 ranks gained little over 2 (1.66x<!-- claim: 05_mpi_multi_node/mpi_squares_scaling_gatherv.json | rows[n=100000000,ranks=4].speedup_vs_1_rank | {:.2f}x --> vs 1.32x<!-- claim: 05_mpi_multi_node/mpi_squares_scaling_gatherv.json | rows[n=100000000,ranks=2].speedup_vs_1_rank | {:.2f}x -->). On one machine, MPI is the wrong tool for a job this light; it is the tool for when the data or the work does not fit on one machine, which was not tested here.

## How to run

```bash
# needs an MPI runtime (Linux: apt install openmpi-bin libopenmpi-dev) and pip install -r requirements-mpi.txt
mpiexec -n 4 python 05_mpi_multi_node/calculate_squares.py 1e8
mpiexec -n 4 python 05_mpi_multi_node/calculate_squares.py 1e8 --no-gather
mpiexec -n 1 python 05_mpi_multi_node/mpi_program.py
python -m mpi_squares.scaling                    # the tables above
python -m pytest 05_mpi_multi_node               # MPI tests are skipped when no MPI runtime is installed
```

Across machines (not tested here): copy `hostfile.example` to `hostfile`, put your machine names in it, set up passwordless SSH from the first machine to the others, install the same Python environment at the same path on every machine, then run `mpiexec -n 4 --hostfile hostfile python 05_mpi_multi_node/calculate_squares.py 1e8`.
