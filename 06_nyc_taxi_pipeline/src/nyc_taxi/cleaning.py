"""Cleaning rules for one month of yellow taxi trips.

Rules are applied in this order; a removed trip is counted once, under the first rule it fails.

1. pickup_outside_month: the pickup time is not inside the file's month (the files contain a few
   trips from other months and years).
2. bad_duration: dropoff minus pickup is under 1 minute or over 6 hours (this includes dropoffs
   before pickups).
3. bad_distance: trip_distance is missing, <= 0 miles or > 100 miles.
4. bad_fare: fare_amount is missing, <= 0 USD or > 500 USD (refunds, disputes and typos).
5. bad_passenger_count: passenger_count is 0 or more than 6. A missing passenger_count is kept:
   it is missing for 23.8 % of 2025 trips (results/06_nyc_taxi_pipeline/stage2_cpu.json) and says
   "unknown", not "wrong".
6. unknown_pickup_zone: PULocationID is not a known zone 1-263 (264 and 265 are "Unknown" / "Outside of NYC").
"""

from __future__ import annotations

import pandas as pd

MIN_DURATION_S = 60
MAX_DURATION_S = 6 * 3600
MAX_DISTANCE_MI = 100.0
MAX_FARE_USD = 500.0
MAX_PASSENGERS = 6
MAX_ZONE_ID = 263

RULES = ["pickup_outside_month", "bad_duration", "bad_distance", "bad_fare", "bad_passenger_count",
         "unknown_pickup_zone"]


def month_bounds(month: str) -> tuple[pd.Timestamp, pd.Timestamp]:
    start = pd.Timestamp(f"{month}-01")
    return start, start + pd.offsets.MonthBegin(1)


def rule_masks(df: pd.DataFrame, month: str) -> dict[str, pd.Series]:
    """True where the row FAILS the rule."""
    start, end = month_bounds(month)
    pickup, dropoff = df["tpep_pickup_datetime"], df["tpep_dropoff_datetime"]
    duration_s = (dropoff - pickup).dt.total_seconds()
    dist, fare, pax, zone = df["trip_distance"], df["fare_amount"], df["passenger_count"], df["PULocationID"]
    return {
        "pickup_outside_month": ~((pickup >= start) & (pickup < end)),
        "bad_duration": ~((duration_s >= MIN_DURATION_S) & (duration_s <= MAX_DURATION_S)),
        "bad_distance": ~((dist > 0) & (dist <= MAX_DISTANCE_MI)),
        "bad_fare": ~((fare > 0) & (fare <= MAX_FARE_USD)),
        "bad_passenger_count": pax.notna() & ((pax < 1) | (pax > MAX_PASSENGERS)),
        "unknown_pickup_zone": ~((zone >= 1) & (zone <= MAX_ZONE_ID)),
    }


def clean(df: pd.DataFrame, month: str) -> tuple[pd.DataFrame, dict[str, int]]:
    """Return the clean rows and how many rows each rule removed."""
    masks = rule_masks(df, month)
    removed_so_far = pd.Series(False, index=df.index)
    removed = {}
    for name in RULES:
        new = masks[name].fillna(True).astype(bool) & ~removed_so_far
        removed[name] = int(new.sum())
        removed_so_far |= new
    return df.loc[~removed_so_far], removed
