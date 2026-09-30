# 04 Temperature monitor with threads (from Lab 4 part 1)

Originally Lab 4 Part 1 of DSAI3202 (UDST, Spring 2025). Fixed in 2026, keeping my 2025 structure and names (`main.py`, `sensor.py`, `display.py`, `simulate_sensor`, `process_temperatures`, `initialize_display`, `update_display`). The real-data replay mode was **added in 2026**.

## What it is

A producer/consumer program with threads:

- `num_sensors` sensor threads each put one reading per second on a `queue.Queue`;
- one processor thread takes everything off the queue every 5 seconds, updates each sensor's running average, and signals the display with a `threading.Condition`;
- a display thread redraws the latest readings and averages **in place** (cursor moves up with ANSI codes; the console is never cleared).

This is waiting work, not number crunching: threads spend almost all their time sleeping or blocked on the queue, which is exactly what threads are good for in Python.

Two modes:

- `--mode random` (the 2025 behaviour): random integer temperatures from 15 to 40 °C. Used by the tests.
- `--mode data` (added in 2026): replays real hourly temperatures (column `T`) from the UCI Air Quality dataset. The file has one temperature series from one station, so sensor i replays that series starting one week (168 rows) later than sensor i - 1. Readings marked -200 (missing) are skipped and counted, never replaced.

Dataset: De Vito, S. (2008). Air Quality [Dataset]. UCI Machine Learning Repository. https://doi.org/10.24432/C59K5F. Licence CC BY 4.0. It is downloaded by `download_air_quality.py` into `data/air_quality/` and never committed.

## Result (real data, 3 sensors, `--headless --duration 12`, default intervals: a reading every second, averages every five seconds)

<!-- table: t04 -->
Run: 12 s, 3 sensors, 3 average updates, processor alive: yes, largest queue 15, queue at the end 0.

| Sensor | Rows replayed | Missing (-200) skipped | Average (°C) |
|---|---|---|---|
| Sensor 0 | 12 | 0 | 11.36 |
| Sensor 1 | 12 | 0 | 16.93 |
| Sensor 2 | 12 | 0 | 10.17 |
<!-- /table -->

The tests run the same threads for 3 seconds on a synthetic fixture in the dataset's exact format, compare every average with a plain pandas mean of the same rows, check that the processor thread is still alive and that the queue stays bounded.

## What was wrong in 2025 and how I fixed it

- **Processor thread crashed on each sensor's second reading.** `temperature_averages[id]` held the list of readings and was then overwritten with the average (a float), so the next `.append` raised `AttributeError: 'float' object has no attribute 'append'` and the thread died. Readings now live in `sensor_readings`; `temperature_averages` only holds floats.
- **Queue grew without bound.** The processor took one reading and slept 5 seconds while 3 sensors added 3 readings per second (5 → 16 → 30 → 47 items in the 2026 re-run). It now drains the whole queue every interval.
- **No Condition.** The lab asked for one; it was only a comment. `condition` now wakes the display when new averages are ready.
- **`os.system('clear')`** erased the console (the brief said not to) and does not exist in Windows `cmd`. The display now rewrites its lines in place.
- **Hard-coded 3 sensors** in the display, **wrong imports** (`ModuleNotFoundError: sensor` from the repo root) and a **missing `import time`** (NameError after 1 second).

The regression tests run the 2025 `sensor.py` (with its sleeps scaled down) and the 2025 `main.py`, and show each fails the same check the 2026 code passes.

## How to run

```bash
python 04_sensor_monitor/main.py                                   # random mode, live display, Ctrl+C to stop
python 04_sensor_monitor/download_air_quality.py                   # once, about 1.5 MB
python 04_sensor_monitor/main.py --mode data --duration 30         # live display with real readings
python 04_sensor_monitor/main.py --mode data --headless --duration 12 --save   # the table above
python -m pytest 04_sensor_monitor
```
