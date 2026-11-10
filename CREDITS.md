# Credits

## Supplied material

`05_mpi_multi_node/calculate_squares.py` and the mpi4py send/recv example in `05_mpi_multi_node/mpi_program.py` were supplied with the original exercise and are modified here:

| File | Changes |
|---|---|
| `05_mpi_multi_node/calculate_squares.py` | n from the command line, NumPy int64 arrays instead of Python lists, `Gatherv`/`reduce` instead of `gather`, prints length, last square and time, optional JSON output; the work split between ranks is unchanged |
| `05_mpi_multi_node/mpi_program.py` | also works with a single rank (it sends to itself) |

The section headings of the threads-vs-processes notebook (`01_threads_vs_processes/threads_vs_processes.ipynb`) come from the original exercise; its code cells are mine. Everything else in this repository is my own work.

## Data (downloaded by scripts, never committed)

- **NYC Taxi and Limousine Commission (TLC) Trip Record Data**, yellow taxi trips, January to December 2025, and the taxi zone lookup table. Source: https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page. The data is published by the City of New York; use is subject to the NYC.gov terms of use (https://www.nyc.gov/home/terms-of-use.page). The files in this repo's `tests/fixtures/taxi/` are synthetic and only copy the column layout.
- **Air Quality** dataset: De Vito, S. (2008). Air Quality [Dataset]. UCI Machine Learning Repository. https://doi.org/10.24432/C59K5F. Licence: Creative Commons Attribution 4.0 International (CC BY 4.0). `tests/fixtures/air_quality_tiny.csv` is synthetic and only copies the file format.

## Software

Python 3.12, NumPy, pandas, PyArrow, mpi4py with Open MPI, matplotlib, SQLite (Python `sqlite3`), pytest, Hypothesis, coverage.py, Ruff, nbclient/nbconvert.
