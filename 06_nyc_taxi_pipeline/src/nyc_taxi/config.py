"""Dataset locations. Data source: NYC Taxi and Limousine Commission (TLC) Trip Record Data,
https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page (files served from the TLC CloudFront bucket).
"""

from pathlib import Path

YEAR = 2025  # latest complete year when this was built (September 2026)
MONTHS = [f"{YEAR}-{m:02d}" for m in range(1, 13)]
URL_TEMPLATE = "https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_{month}.parquet"
ZONE_LOOKUP_URL = "https://d37ci6vzurychx.cloudfront.net/misc/taxi_zone_lookup.csv"
REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = REPO_ROOT / "data" / "nyc_taxi"
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "taxi"

COLUMNS = ["tpep_pickup_datetime", "tpep_dropoff_datetime", "passenger_count", "trip_distance",
           "fare_amount", "PULocationID"]


def file_name(month: str) -> str:
    return f"yellow_tripdata_{month}.parquet"


def url(month: str) -> str:
    return URL_TEMPLATE.format(month=month)


def month_from_path(path) -> str:
    """'.../yellow_tripdata_2025-03.parquet' -> '2025-03'."""
    stem = Path(path).stem
    return stem.rsplit("_", 1)[-1]
