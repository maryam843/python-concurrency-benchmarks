"""Download the UCI Air Quality dataset into data/air_quality/ (not committed).

    python 04_sensor_monitor/download_air_quality.py

Source: https://archive.ics.uci.edu/dataset/360/air+quality (De Vito, 2008), licence CC BY 4.0.
"""

import hashlib
import json
import sys
import zipfile
from pathlib import Path

from nyc_taxi.download import download_file, sha256_file

URL = "https://archive.ics.uci.edu/static/public/360/air+quality.zip"
ZIP_SHA256 = "d4a64013fb385288a8a48d9d193ca7079b2e1bbddf6f8d458feb8c08ab2b8a2a"  # 1,543,989 bytes, checked 2026-10
DEST = Path(__file__).resolve().parents[1] / "data" / "air_quality"


def main(dest: Path = DEST, url: str = URL, expected_sha256: str | None = ZIP_SHA256) -> Path:
    """Download (timeout, length check and retry from nyc_taxi.download), check the hash, extract the CSV."""
    dest.mkdir(parents=True, exist_ok=True)
    zip_path = dest / "air_quality.zip"
    if zip_path.exists() and expected_sha256 and sha256_file(zip_path) != expected_sha256:
        print(f"{zip_path.name} does not match the expected SHA-256, downloading it again")
        zip_path.unlink()
    if not zip_path.exists():
        print(f"downloading {url}")
        download_file(url, zip_path)  # writes a .part file first, so a broken transfer never looks complete
    sha = sha256_file(zip_path)
    if expected_sha256 and sha != expected_sha256:
        zip_path.unlink()
        raise ValueError(f"{url}: SHA-256 {sha} does not match the expected {expected_sha256}")
    with zipfile.ZipFile(zip_path) as z:
        z.extract("AirQualityUCI.csv", dest)
    csv_path = dest / "AirQualityUCI.csv"
    manifest = {"url": url, "zip_sha256": sha, "zip_bytes": zip_path.stat().st_size,
                "csv": csv_path.name, "csv_sha256": hashlib.sha256(csv_path.read_bytes()).hexdigest()}
    (dest / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))
    return csv_path


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else DEST)
