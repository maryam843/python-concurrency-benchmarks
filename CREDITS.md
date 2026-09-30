# Credits

## Course

Originally built for DSAI3202 Parallel & Distributed Computing, University of Doha for Science and Technology (UDST), Spring 2025. The lab and assignment briefs were written by the course staff; they are not included in this repository.

Course-provided material that appears here:

| File | Provided | Modified by me |
|---|---|---|
| `05_mpi_multi_node/calculate_squares.py` | DSAI3202 course staff, Lab 6 brief | yes, 2026: n from the command line, NumPy int64 arrays, Gatherv/Reduce, prints length, last square and time (see the header in the file) |
| `05_mpi_multi_node/mpi_program.py` | the standard mpi4py send/recv example used in the Lab 6 brief | yes, 2026: works with one rank |
| `01_threads_vs_processes/First_trials_with_threads_and_processes_with_performance_metrics.ipynb` | the notebook headings ("Add your interpretations and conclusions here" and the section titles) came from the Lab 2 template | the code cells are mine; fixed in 2026 |

Everything else (the 2025 code in folders 01 to 05 and all 2026 code) is my own work.

## Data (downloaded by scripts, never committed)

- **NYC Taxi and Limousine Commission (TLC) Trip Record Data**, yellow taxi trips, January to December 2025, and the taxi zone lookup table. Source: https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page. The data is published by the City of New York; use is subject to the NYC.gov terms of use (https://www.nyc.gov/home/terms-of-use.page). The files in this repo's `tests/fixtures/taxi/` are synthetic and only copy the column layout.
- **Air Quality** dataset: De Vito, S. (2008). Air Quality [Dataset]. UCI Machine Learning Repository. https://doi.org/10.24432/C59K5F. Licence: Creative Commons Attribution 4.0 International (CC BY 4.0). `tests/fixtures/air_quality_tiny.csv` is synthetic and only copies the file format.

## Software

Python 3.12, NumPy, pandas, PyArrow, mpi4py with Open MPI, matplotlib, SQLite (Python `sqlite3`), pytest, Hypothesis, coverage.py, Ruff, nbclient/nbconvert.
