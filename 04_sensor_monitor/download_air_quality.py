"""Download the UCI Air Quality dataset into data/air_quality/ (not committed).

    python 04_sensor_monitor/download_air_quality.py

Source: https://archive.ics.uci.edu/dataset/360/air+quality (De Vito, 2008), licence CC BY 4.0.
"""

import hashlib
import json
import sys
import urllib.request
import zipfile
from pathlib import Path

URL = "https://archive.ics.uci.edu/static/public/360/air+quality.zip"
DEST = Path(__file__).resolve().parents[1] / "data" / "air_quality"


def main(dest: Path = DEST) -> Path:
    dest.mkdir(parents=True, exist_ok=True)
    zip_path = dest / "air_quality.zip"
    if not zip_path.exists():
        print(f"downloading {URL}")
        urllib.request.urlretrieve(URL, zip_path)
    sha = hashlib.sha256(zip_path.read_bytes()).hexdigest()
    with zipfile.ZipFile(zip_path) as z:
        z.extract("AirQualityUCI.csv", dest)
    csv_path = dest / "AirQualityUCI.csv"
    manifest = {"url": URL, "zip_sha256": sha, "zip_bytes": zip_path.stat().st_size,
                "csv": csv_path.name, "csv_sha256": hashlib.sha256(csv_path.read_bytes()).hexdigest()}
    (dest / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))
    return csv_path


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else DEST)
