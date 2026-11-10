"""Replay real temperature readings from the UCI Air Quality dataset.

Dataset: De Vito, S. (2008). Air Quality [Dataset]. UCI Machine Learning Repository.
https://doi.org/10.24432/C59K5F, licence CC BY 4.0. Hourly averages from a gas multisensor device
in an Italian city, March 2004 to February 2005. The file is downloaded by download_air_quality.py
and never committed.

Format: semicolon separated, decimal comma, and -200 marks a missing value. Column T is the
temperature in degrees C.

There is one temperature series (one station). For num_sensors streams, sensor i replays that
series starting at row i * offset_rows, so the streams are real readings from different days.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pandas as pd

MISSING = -200
DEFAULT_PATH = Path(__file__).resolve().parents[3] / "data" / "air_quality" / "AirQualityUCI.csv"


def load_temperatures(path: str | Path = DEFAULT_PATH) -> pd.Series:
    """Hourly temperature (degrees C) with -200 turned into NaN; trailing empty rows dropped."""
    df = pd.read_csv(path, sep=";", decimal=",", usecols=["Date", "Time", "T"])
    df = df.dropna(subset=["Date"])
    t = pd.to_numeric(df["T"], errors="coerce")
    t = t.mask(t == MISSING)
    return t.reset_index(drop=True).rename("T")


def sensor_stream(temps: pd.Series, sensor_id: int, offset_rows: int = 24 * 7) -> Iterator[float | None]:
    """Yield readings for one sensor: float for a valid reading, None for a missing one (-200)."""
    start = (sensor_id * offset_rows) % max(len(temps), 1)
    for value in temps.iloc[start:]:
        yield None if pd.isna(value) else float(value)


def make_sources(path: str | Path, num_sensors: int, offset_rows: int = 24 * 7) -> list[Iterator[float | None]]:
    temps = load_temperatures(path)
    return [sensor_stream(temps, i, offset_rows) for i in range(num_sensors)]


def expected_average(path: str | Path, sensor_id: int, rows_consumed: int, offset_rows: int = 24 * 7) -> float:
    """Reference answer with plain pandas: mean of the first rows_consumed rows of that sensor, NaN skipped."""
    temps = load_temperatures(path)
    start = (sensor_id * offset_rows) % max(len(temps), 1)
    return float(temps.iloc[start:start + rows_consumed].mean(skipna=True))
