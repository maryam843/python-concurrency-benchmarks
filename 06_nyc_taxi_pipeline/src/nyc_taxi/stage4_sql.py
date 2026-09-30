"""Stage 4 (SQL): load the monthly summaries into SQLite and answer five questions with the files in sql/.

    python -m nyc_taxi.stage4_sql            # uses results/06_nyc_taxi_pipeline/stage2_cpu.json

Tables: monthly(one row per month), hourly(month, hour, trips), zone_trips(month, zone_id, trips),
zones(zone_id, borough, zone, service_zone) from the TLC zone lookup.
"""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
from pathlib import Path

from bench_common import write_result
from bench_common.results import RESULTS_DIR
from nyc_taxi.cleaning import RULES
from nyc_taxi.config import DATA_DIR

SQL_DIR = Path(__file__).resolve().parents[2] / "sql"

SCHEMA = f"""
CREATE TABLE monthly (
    month TEXT PRIMARY KEY, rows_raw INTEGER NOT NULL, rows_clean INTEGER NOT NULL,
    {", ".join(f"removed_{r} INTEGER NOT NULL" for r in RULES)},
    fare_sum REAL NOT NULL, distance_sum REAL NOT NULL, duration_min_sum REAL NOT NULL
);
CREATE TABLE hourly (month TEXT NOT NULL, hour INTEGER NOT NULL, trips INTEGER NOT NULL,
                     PRIMARY KEY (month, hour));
CREATE TABLE zone_trips (month TEXT NOT NULL, zone_id INTEGER NOT NULL, trips INTEGER NOT NULL,
                         PRIMARY KEY (month, zone_id));
CREATE TABLE zones (zone_id INTEGER PRIMARY KEY, borough TEXT, zone TEXT, service_zone TEXT);
"""


def build_db(month_summaries: list[dict], zone_csv: Path | None, db_path: Path | str = ":memory:"):
    if db_path != ":memory:":
        Path(db_path).unlink(missing_ok=True)
    con = sqlite3.connect(db_path)
    con.executescript(SCHEMA)
    for m in month_summaries:
        con.execute(f"INSERT INTO monthly VALUES ({', '.join(['?'] * (6 + len(RULES)))})",
                    [m["month"], m["rows_raw"], m["rows_clean"], *[m["removed"][r] for r in RULES],
                     m["fare_sum"], m["distance_sum"], m["duration_min_sum"]])
        con.executemany("INSERT INTO hourly VALUES (?, ?, ?)", [(m["month"], h, c) for h, c in enumerate(m["hourly"])])
        con.executemany("INSERT INTO zone_trips VALUES (?, ?, ?)",
                        [(m["month"], int(z), c) for z, c in m["zones"].items()])
    if zone_csv is not None and Path(zone_csv).exists():
        with open(zone_csv, newline="", encoding="utf-8") as f:
            rows = [(int(r["LocationID"]), r["Borough"], r["Zone"], r["service_zone"]) for r in csv.DictReader(f)]
        con.executemany("INSERT INTO zones VALUES (?, ?, ?, ?)", rows)
    con.commit()
    return con


def run_queries(con) -> dict[str, list[dict]]:
    answers = {}
    for sql_file in sorted(SQL_DIR.glob("q*.sql")):
        cur = con.execute(sql_file.read_text(encoding="utf-8"))
        cols = [c[0] for c in cur.description]
        answers[sql_file.stem] = [dict(zip(cols, row, strict=True)) for row in cur.fetchall()]
    return answers


def main(argv=None) -> dict:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--summaries", type=Path, default=RESULTS_DIR / "06_nyc_taxi_pipeline" / "stage2_cpu.json")
    ap.add_argument("--zones", type=Path, default=DATA_DIR / "taxi_zone_lookup.csv")
    ap.add_argument("--db", type=Path, default=DATA_DIR / "summaries.sqlite")
    ap.add_argument("--no-save", action="store_true")
    args = ap.parse_args(argv)
    months = json.loads(args.summaries.read_text())["month_summaries"]
    args.db.parent.mkdir(parents=True, exist_ok=True)
    con = build_db(months, args.zones, args.db)
    answers = run_queries(con)
    con.close()
    for name, rows in answers.items():
        print(f"-- {name}")
        for r in rows:
            print("   ", r)
    if not args.no_save:
        write_result("stage4_sql", {"source": args.summaries.name, "answers": answers}, seed=None,
                     subdir="06_nyc_taxi_pipeline")
    return answers


if __name__ == "__main__":
    main()
