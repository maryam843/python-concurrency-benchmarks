"""Write benchmark results as JSON with machine info, versions, seed and timestamp.

Hostnames, user names and absolute paths are never recorded.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import platform
import sys
from importlib import metadata
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
RESULTS_DIR = REPO_ROOT / "results"

_PACKAGES = ("numpy", "pandas", "pyarrow", "mpi4py", "matplotlib")


def _cpu_model() -> str:
    try:
        with open("/proc/cpuinfo", encoding="utf-8") as f:
            for line in f:
                if line.startswith("model name"):
                    return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor() or "unknown"


def _mem_gb() -> float | None:
    try:
        with open("/proc/meminfo", encoding="utf-8") as f:
            kb = int(f.readline().split()[1])
        return round(kb / 1024**2, 1)
    except (OSError, ValueError, IndexError):
        return None


def machine_info() -> dict[str, Any]:
    versions = {}
    for p in _PACKAGES:
        try:
            versions[p] = metadata.version(p)
        except metadata.PackageNotFoundError:
            versions[p] = None
    return {
        "os": f"{platform.system()} {platform.release()}",
        "machine": platform.machine(),
        "cpu_model": _cpu_model(),
        "logical_cpus": os.cpu_count(),
        "memory_gb": _mem_gb(),
        "python": sys.version.split()[0],
        "packages": versions,
    }


def write_result(name: str, payload: dict[str, Any], *, seed: int | None, subdir: str,
                 results_dir: Path | None = None) -> Path:
    """Write results/<subdir>/<name>.json and return its path."""
    out_dir = (results_dir or RESULTS_DIR) / subdir
    out_dir.mkdir(parents=True, exist_ok=True)
    doc = {
        "name": name,
        "timestamp_utc": _dt.datetime.now(_dt.UTC).isoformat(timespec="seconds"),
        "seed": seed,
        "machine": machine_info(),
        **payload,
    }
    path = out_dir / f"{name}.json"
    path.write_text(json.dumps(doc, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    return path
