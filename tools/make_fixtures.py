"""Generate the small synthetic fixture files used by the tests and CI (no real data is committed).

    python tools/make_fixtures.py

- tests/fixtures/air_quality_tiny.csv: 300 hourly rows in the exact UCI Air Quality format
  (semicolon separator, decimal comma, -200 = missing, trailing empty rows).
- tests/fixtures/taxi/yellow_tripdata_2025-0{1,2,3}.parquet: 1,002 synthetic trips in total with the
  TLC column types, including every kind of row the cleaning rules remove.
- tests/fixtures/taxi/taxi_zone_lookup.csv: synthetic zone names for IDs 1-265.
"""

from __future__ import annotations

import math
import random
from pathlib import Path

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures"
AQ_HEADER = "Date;Time;CO(GT);PT08.S1(CO);NMHC(GT);C6H6(GT);PT08.S2(NMHC);NOx(GT);PT08.S3(NOx);NO2(GT);" \
            "PT08.S4(NO2);PT08.S5(O3);T;RH;AH;;"


def _comma(x: float, nd: int = 1) -> str:
    return f"{x:.{nd}f}".replace(".", ",")


def make_air_quality(path: Path = FIXTURES / "air_quality_tiny.csv", rows: int = 300, seed: int = 360) -> Path:
    rng = random.Random(seed)
    lines = [AQ_HEADER]
    for h in range(rows):
        day, hour = divmod(h + 18, 24)
        date = f"{10 + day:02d}/03/2004"
        t = 12 + 6 * math.sin((hour - 9) / 24 * 2 * math.pi) + rng.uniform(-1.5, 1.5)
        t_txt = "-200" if rng.random() < 0.06 else _comma(t)
        rh = _comma(rng.uniform(30, 70))
        vals = ["-200" if rng.random() < 0.05 else _comma(rng.uniform(0.5, 4)), str(rng.randint(900, 1500)),
                "-200", _comma(rng.uniform(2, 20)), str(rng.randint(700, 1200)), str(rng.randint(50, 300)),
                str(rng.randint(800, 1300)), str(rng.randint(40, 150)), str(rng.randint(1200, 1900)),
                str(rng.randint(700, 1400)), t_txt, rh, _comma(rng.uniform(0.5, 1.2), 4)]
        lines.append(";".join([date, f"{hour:02d}.00.00", *vals]) + ";;")
    lines += [";" * 16, ";" * 16]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


TAXI_MONTHS = ["2025-01", "2025-02", "2025-03"]


def _taxi_month(month: str, rows: int, rng: random.Random):
    import datetime as dt

    import pyarrow as pa

    y, m = map(int, month.split("-"))
    start = dt.datetime(y, m, 1)
    days = 28 if m == 2 else 31
    cols = {k: [] for k in ("VendorID", "tpep_pickup_datetime", "tpep_dropoff_datetime", "passenger_count",
                            "trip_distance", "PULocationID", "DOLocationID", "fare_amount", "total_amount")}
    kinds = ["ok"] * 80 + ["outside_month", "neg_duration", "short", "zero_dist", "huge_dist", "neg_fare",
                           "huge_fare", "zero_pax", "seven_pax", "null_pax", "zone_264", "zone_265", "null_dist"]
    for _ in range(rows):
        kind = rng.choice(kinds)
        pickup = start + dt.timedelta(seconds=rng.randrange(days * 86400))
        minutes = rng.uniform(3, 45)
        dist = round(rng.uniform(0.3, 18), 2)
        fare = round(3 + 2.8 * dist + rng.uniform(0, 5), 2)
        pax = rng.choice([1, 1, 1, 2, 2, 3, 4, 5, 6])
        zone = rng.choice([132, 138, 161, 162, 186, 230, 236, 237, 48, 142] + list(range(1, 264)))
        if kind == "outside_month":
            pickup = start - dt.timedelta(hours=rng.uniform(1, 48))
        elif kind == "neg_duration":
            minutes = -rng.uniform(1, 30)
        elif kind == "short":
            minutes = rng.uniform(0, 0.9)
        elif kind == "zero_dist":
            dist = 0.0
        elif kind == "huge_dist":
            dist = round(rng.uniform(150, 90000), 2)
        elif kind == "neg_fare":
            fare = -fare
        elif kind == "huge_fare":
            fare = round(rng.uniform(600, 900000), 2)
        elif kind == "zero_pax":
            pax = 0
        elif kind == "seven_pax":
            pax = 7
        elif kind == "null_pax":
            pax = None
        elif kind == "zone_264":
            zone = 264
        elif kind == "zone_265":
            zone = 265
        elif kind == "null_dist":
            dist = None
        pickup = pickup.replace(microsecond=0)
        cols["VendorID"].append(rng.choice([1, 2]))
        cols["tpep_pickup_datetime"].append(pickup)
        cols["tpep_dropoff_datetime"].append(pickup + dt.timedelta(minutes=minutes))
        cols["passenger_count"].append(pax)
        cols["trip_distance"].append(dist)
        cols["PULocationID"].append(zone)
        cols["DOLocationID"].append(rng.randint(1, 263))
        cols["fare_amount"].append(fare)
        cols["total_amount"].append(round(fare + 4.5, 2))
    schema = pa.schema([("VendorID", pa.int32()), ("tpep_pickup_datetime", pa.timestamp("us")),
                        ("tpep_dropoff_datetime", pa.timestamp("us")), ("passenger_count", pa.int64()),
                        ("trip_distance", pa.float64()), ("PULocationID", pa.int32()), ("DOLocationID", pa.int32()),
                        ("fare_amount", pa.float64()), ("total_amount", pa.float64())])
    return pa.table(cols, schema=schema)


def make_taxi(dest: Path = FIXTURES / "taxi", seed: int = 2025) -> list[Path]:
    import pyarrow.parquet as pq

    rng = random.Random(seed)
    dest.mkdir(parents=True, exist_ok=True)
    paths = []
    for month, rows in zip(TAXI_MONTHS, [340, 322, 340], strict=True):
        p = dest / f"yellow_tripdata_{month}.parquet"
        pq.write_table(_taxi_month(month, rows, rng), p, compression="snappy")
        paths.append(p)
    boroughs = ["Manhattan", "Queens", "Brooklyn", "Bronx", "Staten Island"]
    lines = ['"LocationID","Borough","Zone","service_zone"']
    for z in range(1, 266):
        b = "Unknown" if z >= 264 else boroughs[z % 5]
        lines.append(f'{z},"{b}","Synthetic zone {z}","{"N/A" if z >= 264 else "Boro Zone"}"')
    (dest / "taxi_zone_lookup.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return paths


if __name__ == "__main__":
    print(make_air_quality())
    for p in make_taxi():
        print(p)
