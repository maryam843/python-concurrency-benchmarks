"""Small file helpers for the connection pool demo.

2025: log_timing() appended to outputs/timing_results.csv on every run, so the file grew with
unlabelled duplicate rows (18 -> 34 -> 50). Timings now go to one JSON file per benchmark run
under results/ (see benchmark.py), and this module only keeps the log helpers.
"""

import json
import os

# Outputs folder for the demo log (relative to where the program is run)
OUTPUT_PATH = os.environ.get("PCB_OUTPUT_PATH", "outputs")


def ensure_output_folder():
    """Ensure the outputs/ folder exists."""
    os.makedirs(OUTPUT_PATH, exist_ok=True)


def log_path(filename):
    """Full path of a log file in the outputs folder (made here, in the parent, before workers start)."""
    ensure_output_folder()
    return os.path.abspath(os.path.join(OUTPUT_PATH, filename))


def append_line(filepath, content, lock=None):
    """Append one line to a file. Pass a multiprocessing Lock when several processes write to it."""
    if lock is None:
        with open(filepath, "a", encoding="utf-8") as f:
            f.write(content + "\n")
        return
    with lock:
        with open(filepath, "a", encoding="utf-8") as f:
            f.write(content + "\n")


def save_output(filename, content):
    """Append one line to a file in the outputs folder."""
    append_line(log_path(filename), content)


def save_json(filename, data):
    """Save data as JSON file."""
    ensure_output_folder()
    filepath = os.path.join(OUTPUT_PATH, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
