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


def save_output(filename, content):
    """Append one line to a file in the outputs folder."""
    ensure_output_folder()
    filepath = os.path.join(OUTPUT_PATH, filename)
    with open(filepath, "a", encoding="utf-8") as f:
        f.write(content + "\n")


def log_to_file(filename, content):
    """Log parallel output to a file."""
    save_output(filename, content)


def save_json(filename, data):
    """Save data as JSON file."""
    ensure_output_folder()
    filepath = os.path.join(OUTPUT_PATH, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
