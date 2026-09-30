"""Temperature monitor: sensor threads -> queue -> processor thread -> in-place console display.

    python 04_sensor_monitor/main.py                       # random mode, 3 sensors, Ctrl+C to stop
    python 04_sensor_monitor/main.py --mode data --duration 30
    python 04_sensor_monitor/main.py --mode data --headless --duration 12 --save

2025 bugs fixed here: imports failed from the repo root (ModuleNotFoundError: sensor) and
`time` was never imported (NameError after 1 s).
"""

import argparse
import json
import threading
import time
from queue import Queue

from bench_common import write_result
from sensor_monitor import sensor
from sensor_monitor.airquality import DEFAULT_PATH, make_sources
from sensor_monitor.display import enable_ansi_on_windows, initialize_display, update_display


def main(argv=None):
    ap = argparse.ArgumentParser(description="Threaded temperature monitor")
    ap.add_argument("--num-sensors", type=int, default=3)
    ap.add_argument("--mode", choices=["random", "data"], default="random")
    ap.add_argument("--data", default=str(DEFAULT_PATH), help="AirQualityUCI.csv (data mode)")
    ap.add_argument("--duration", type=float, default=0, help="seconds to run (0 = until Ctrl+C)")
    ap.add_argument("--sensor-interval", type=float, default=1.0)
    ap.add_argument("--process-interval", type=float, default=5.0)
    ap.add_argument("--headless", action="store_true", help="no live display; print a JSON summary")
    ap.add_argument("--save", action="store_true", help="write the summary to results/04_sensor_monitor/")
    args = ap.parse_args(argv)
    num_sensors = args.num_sensors
    sources = make_sources(args.data, num_sensors) if args.mode == "data" else None

    if args.headless:
        summary = sensor.run_monitor(num_sensors, args.duration or 12, args.sensor_interval,
                                     args.process_interval, sources)
        summary["mode"] = args.mode
        brief = {k: v for k, v in summary.items() if k != "readings"}
        print(json.dumps(brief, indent=2))
        if args.save:
            write_result(f"sensor_monitor_{args.mode}", summary, seed=None, subdir="04_sensor_monitor")
        return summary

    # Create a queue to pass sensor data between threads
    queue = Queue()
    sensor.reset_state()
    enable_ansi_on_windows()
    initialize_display(num_sensors)
    sensor.start_threads(num_sensors, queue, args.sensor_interval, args.process_interval, sources)

    # Start the display thread
    display_thread = threading.Thread(target=update_display, args=(num_sensors,), daemon=True)
    display_thread.start()

    # Keep the main program running
    t_end = time.monotonic() + args.duration if args.duration else None
    try:
        while t_end is None or time.monotonic() < t_end:
            time.sleep(0.2)
    except KeyboardInterrupt:
        pass
    sensor.stop_event.set()
    display_thread.join(timeout=2)
    return None


if __name__ == "__main__":
    main()
