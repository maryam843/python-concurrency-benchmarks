"""Per-month summaries and their exact combination into a yearly summary.

A month summary stores sums and counts (not means), so combining months in any grouping gives
exactly the yearly numbers: every method (sequential, threads, processes, MPI) calls the same
summarise_month() per file and then combine() in month order.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from nyc_taxi.cleaning import MAX_ZONE_ID, RULES, clean
from nyc_taxi.config import COLUMNS, month_from_path


def read_month(path: str | Path) -> pd.DataFrame:
    return pd.read_parquet(path, columns=COLUMNS, engine="pyarrow")


def summarise_frame(df: pd.DataFrame, month: str) -> dict:
    rows_raw = len(df)
    good, removed = clean(df, month)
    duration_min = (good["tpep_dropoff_datetime"] - good["tpep_pickup_datetime"]).dt.total_seconds() / 60
    hourly = good["tpep_pickup_datetime"].dt.hour.value_counts().reindex(range(24), fill_value=0)
    zones = good["PULocationID"].value_counts()
    return {
        "month": month,
        "rows_raw": rows_raw,
        "rows_clean": len(good),
        "removed": removed,
        "passenger_count_missing_raw": int(df["passenger_count"].isna().sum()),
        "fare_sum": float(good["fare_amount"].sum()),
        "distance_sum": float(good["trip_distance"].sum()),
        "duration_min_sum": float(duration_min.sum()),
        "hourly": [int(v) for v in hourly.tolist()],
        "zones": {int(k): int(v) for k, v in sorted(zones.items())},
    }


def summarise_month(path: str | Path) -> dict:
    """Read one monthly Parquet file, clean it and summarise it."""
    return summarise_frame(read_month(path), month_from_path(path))


def combine(months: list[dict]) -> dict:
    """Combine month summaries (in month order) into a yearly summary with derived means and top zones."""
    months = sorted(months, key=lambda m: m["month"])
    hourly = [0] * 24
    zones: dict[int, int] = {}
    removed = dict.fromkeys(RULES, 0)
    fare = dist = dur = 0.0
    for m in months:
        hourly = [a + b for a, b in zip(hourly, m["hourly"], strict=True)]
        for z, c in m["zones"].items():
            zones[int(z)] = zones.get(int(z), 0) + c
        for r in RULES:
            removed[r] += m["removed"][r]
        fare += m["fare_sum"]
        dist += m["distance_sum"]
        dur += m["duration_min_sum"]
    rows_raw = sum(m["rows_raw"] for m in months)
    pax_missing = sum(m["passenger_count_missing_raw"] for m in months)
    rows_clean = sum(m["rows_clean"] for m in months)
    top10 = sorted(zones.items(), key=lambda kv: (-kv[1], kv[0]))[:10]
    return {
        "months": [m["month"] for m in months],
        "rows_raw": rows_raw,
        "rows_clean": rows_clean,
        "removed": removed,
        "removed_share": (rows_raw - rows_clean) / rows_raw if rows_raw else 0.0,
        "passenger_count_missing_raw": pax_missing,
        "passenger_count_missing_share": pax_missing / rows_raw if rows_raw else 0.0,
        "mean_fare": fare / rows_clean if rows_clean else 0.0,
        "mean_distance_mi": dist / rows_clean if rows_clean else 0.0,
        "mean_duration_min": dur / rows_clean if rows_clean else 0.0,
        "hourly": hourly,
        "busiest_hour": max(range(24), key=lambda h: (hourly[h], -h)),
        "top10_pickup_zones": [{"zone_id": z, "trips": c} for z, c in top10],
        "zones_seen": len(zones),
        "max_zone_id": MAX_ZONE_ID,
    }


def summary_key(month_summaries: list[dict]) -> list[dict]:
    """Normalised form used to assert that two methods produced identical summaries."""
    out = []
    for m in sorted(month_summaries, key=lambda m: m["month"]):
        m2 = dict(m)
        m2["zones"] = {int(k): v for k, v in m["zones"].items()}
        out.append(m2)
    return out
