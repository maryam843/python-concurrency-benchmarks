"""Download the monthly yellow taxi Parquet files (never committed) and write a manifest.

    python -m nyc_taxi.download                 # 12 months of 2025 into data/nyc_taxi/, 8 threads
    python -m nyc_taxi.download --workers 1

The manifest (file name, bytes, rows, SHA-256) goes to results/06_nyc_taxi_pipeline/manifest.json.
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pyarrow.parquet as pq

from bench_common import write_result
from nyc_taxi.config import DATA_DIR, MONTHS, ZONE_LOOKUP_URL, file_name, url

CHUNK = 1 << 20


def download_file(src_url: str, dest: Path, timeout: float = 120) -> dict:
    """Stream src_url to dest (via a .part file), hashing while writing."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    h = hashlib.sha256()
    size = 0
    with urllib.request.urlopen(src_url, timeout=timeout) as resp, open(part, "wb") as f:
        while chunk := resp.read(CHUNK):
            h.update(chunk)
            f.write(chunk)
            size += len(chunk)
    part.replace(dest)
    return {"file": dest.name, "bytes": size, "sha256": h.hexdigest()}


def download_months(months: list[str], dest_dir: Path, workers: int, url_for=None) -> list[dict]:
    """Download several months; workers = 1 is plain sequential (no pool)."""
    url_for = url_for or url  # looked up at call time, so tests can point it at a local server
    jobs = [(url_for(m), dest_dir / file_name(m)) for m in months]
    if workers == 1:
        return [download_file(u, d) for u, d in jobs]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(lambda job: download_file(*job), jobs))


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(CHUNK):
            h.update(chunk)
    return h.hexdigest()


def manifest(dest_dir: Path, months: list[str]) -> list[dict]:
    rows = []
    for m in months:
        p = dest_dir / file_name(m)
        rows.append({"file": p.name, "month": m, "bytes": p.stat().st_size,
                     "rows": pq.ParquetFile(p).metadata.num_rows, "sha256": sha256_file(p)})
    return rows


def ensure_zone_lookup(dest_dir: Path = DATA_DIR) -> Path:
    p = dest_dir / "taxi_zone_lookup.csv"
    if not p.exists():
        dest_dir.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(ZONE_LOOKUP_URL, timeout=60) as resp, open(p, "wb") as f:
            shutil.copyfileobj(resp, f)
    return p


def main(argv: list[str] | None = None) -> list[dict]:
    ap = argparse.ArgumentParser(description="Download NYC TLC yellow taxi trip files")
    ap.add_argument("--months", nargs="+", default=MONTHS)
    ap.add_argument("--dest", type=Path, default=DATA_DIR)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--no-save", action="store_true")
    args = ap.parse_args(argv)
    missing = [m for m in args.months if not (args.dest / file_name(m)).exists()]
    if missing:
        download_months(missing, args.dest, args.workers)
    ensure_zone_lookup(args.dest)
    rows = manifest(args.dest, args.months)
    for r in rows:
        print(f"{r['file']}  {r['bytes']:>11,} bytes  {r['rows']:>10,} rows  {r['sha256'][:16]}")
    if not args.no_save:
        write_result("manifest", {"source": "NYC TLC Trip Record Data", "files": rows,
                                  "total_bytes": sum(r["bytes"] for r in rows),
                                  "total_rows": sum(r["rows"] for r in rows)},
                     seed=None, subdir="06_nyc_taxi_pipeline")
    return rows


if __name__ == "__main__":
    main()
