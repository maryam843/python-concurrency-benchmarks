"""Console display (Lab 4, 2025; fixed in 2026).

2025: update_display() called os.system('clear') every 5 s (the brief said not to erase the
console, and 'clear' does not exist in Windows cmd) and looped over range(3) instead of the real
number of sensors. Now the block of lines is printed once and then rewritten in place: the cursor
moves up with the ANSI sequence ESC[<n>A and each line is cleared with ESC[2K before it is redrawn.
Values are read under the lock, and the thread wakes when the processor signals the Condition.
"""

import os
import sys

from sensor_monitor import sensor

CURSOR_UP = "\x1b[{n}A"
CLEAR_LINE = "\x1b[2K"


def enable_ansi_on_windows():
    """Windows 10+ consoles understand ANSI codes once VT processing is on; os.system('') turns it on."""
    if os.name == "nt":  # pragma: no cover - only runs on Windows
        os.system("")


def _fmt(value, decimals):
    return "--" if value is None else f"{value:.{decimals}f}"


def render_lines(num_sensors, latest, averages):
    lines = ["Latest Temperatures: " + "  ".join(
        f"Sensor {i}: {_fmt(latest[i], 1)}°C" for i in range(num_sensors))]
    lines.append("")
    lines.append("Sensor Averages:")
    for i in range(num_sensors):
        lines.append(f"Sensor {i} Average: {_fmt(averages[i], 2)}°C")
    return lines


def initialize_display(num_sensors, out=None):
    out = out or sys.stdout
    lines = render_lines(num_sensors, [None] * num_sensors, [None] * num_sensors)
    out.write("\n".join(lines) + "\n")
    out.flush()
    return len(lines)


def redraw(num_sensors, out=None):
    """Move the cursor to the top of the block and rewrite every line in place."""
    out = out or sys.stdout
    latest, averages = sensor.snapshot(num_sensors)
    lines = render_lines(num_sensors, latest, averages)
    out.write(CURSOR_UP.format(n=len(lines)))
    for line in lines:
        out.write(CLEAR_LINE + line + "\n")
    out.flush()
    return lines


def update_display(num_sensors, out=None, timeout=1.0):
    """Redraw when the processor publishes new averages, and at least every `timeout` s for the latest values."""
    last = 0
    while not sensor.stop_event.is_set():
        new = sensor.wait_for_update(last, timeout)
        if sensor.stop_event.is_set():
            break
        redraw(num_sensors, out)
        last = new
