"""Sensor threads and the processing thread (Lab 4, 2025; fixed in 2026).

2025 bugs fixed here:
- Averages: temperature_averages held a list of readings and was then overwritten with a float, so the
  processor thread crashed on each sensor's second reading ("'float' object has no attribute
  'append'"). Readings now live in sensor_readings; temperature_averages only holds floats.
- Queue growth: the processor took one item and then slept 5 s while sensors added 3 items per second, so
  the queue grew without bound. It now drains the whole queue every interval and then updates
  the averages.
- The Condition the lab asked for existed only as a comment. `condition` now tells the display
  thread that new averages are ready.
"""

import queue as queue_module
import random
import threading
import time
from collections.abc import Iterator

# Global dictionaries to hold the latest and average temperatures
latest_temperatures = {}
temperature_averages = {}
# Every reading the processor has taken off the queue, per sensor
sensor_readings = {}

# RLock and Condition for synchronization (the Condition shares the lock)
lock = threading.RLock()
condition = threading.Condition(lock)
stop_event = threading.Event()
# Incremented each time the processor publishes new averages
update_count = 0
# Sensor rows skipped because the dataset marks them missing (-200)
missing_counts = {}
rows_consumed = {}


def reset_state():
    """Clear all shared state (used between runs and by the tests)."""
    global update_count
    with lock:
        latest_temperatures.clear()
        temperature_averages.clear()
        sensor_readings.clear()
        missing_counts.clear()
        rows_consumed.clear()
        update_count = 0
    stop_event.clear()


def random_source(seed=None) -> Iterator[float]:
    """Random mode from 2025: integer temperatures between 15 and 40 degrees C."""
    rng = random.Random(seed)
    while True:
        yield rng.randint(15, 40)


def simulate_sensor(sensor_id, queue, interval=1.0, source=None):
    """Put one reading per `interval` seconds on the queue until stop_event is set.

    `source` yields floats, or None for a missing reading (skipped). Random mode if None.
    The sensor stops by itself when a finite source runs out.
    """
    source = source if source is not None else random_source()
    for temperature in source:
        if stop_event.is_set():
            break
        with lock:
            rows_consumed[sensor_id] = rows_consumed.get(sensor_id, 0) + 1
            if temperature is None:
                missing_counts[sensor_id] = missing_counts.get(sensor_id, 0) + 1
            else:
                latest_temperatures[sensor_id] = temperature
                # Put the reading in the queue for processing
                queue.put((sensor_id, temperature))
        if stop_event.wait(interval):  # Simulate sensor reading every interval
            break


def drain_and_update(queue):
    """Take every waiting reading off the queue, then recompute the averages. Returns items drained."""
    global update_count
    drained = []
    while True:
        try:
            drained.append(queue.get_nowait())
        except queue_module.Empty:
            break
    with condition:
        for sensor_id, temperature in drained:
            sensor_readings.setdefault(sensor_id, []).append(temperature)
        for sensor_id, readings in sensor_readings.items():
            temperature_averages[sensor_id] = sum(readings) / len(readings)
        update_count += 1
        condition.notify_all()
    return len(drained)


def process_temperatures(queue, interval=5.0):
    """Update the averages every `interval` seconds until stop_event is set."""
    while not stop_event.wait(interval):
        drain_and_update(queue)
    drain_and_update(queue)  # final pass so nothing already queued is lost


def start_threads(num_sensors, queue, sensor_interval=1.0, process_interval=5.0, sources=None):
    """Start num_sensors sensor threads plus the processor thread; returns (sensor_threads, processor)."""
    sensor_threads = []
    for i in range(num_sensors):
        src = sources[i] if sources is not None else None
        thread = threading.Thread(target=simulate_sensor, args=(i, queue, sensor_interval, src),
                                  name=f"sensor-{i}", daemon=True)
        sensor_threads.append(thread)
        thread.start()
    processor_thread = threading.Thread(target=process_temperatures, args=(queue, process_interval),
                                        name="processor", daemon=True)
    processor_thread.start()
    return sensor_threads, processor_thread


def wait_for_update(last_seen, timeout):
    """Block until the processor publishes an update newer than `last_seen` (or timeout). Returns the count."""
    with condition:
        condition.wait_for(lambda: update_count > last_seen or stop_event.is_set(), timeout=timeout)
        return update_count


def snapshot(num_sensors):
    """Copy the latest and average values under the lock."""
    with lock:
        latest = [latest_temperatures.get(i) for i in range(num_sensors)]
        averages = [temperature_averages.get(i) for i in range(num_sensors)]
    return latest, averages


def run_monitor(num_sensors, duration_s, sensor_interval=1.0, process_interval=5.0, sources=None):
    """Run sensors and processor for duration_s seconds; return a summary (used by tests and --headless)."""
    reset_state()
    q = queue_module.Queue()
    sensors, processor = start_threads(num_sensors, q, sensor_interval, process_interval, sources)
    sizes = []
    t_end = time.monotonic() + duration_s
    while time.monotonic() < t_end:
        time.sleep(min(0.05, max(0.0, t_end - time.monotonic())))
        sizes.append(q.qsize())
    processor_alive = processor.is_alive()
    stop_event.set()
    for t in sensors:
        t.join(timeout=5)
    processor.join(timeout=5)
    latest, averages = snapshot(num_sensors)
    with lock:
        readings = {k: list(v) for k, v in sensor_readings.items()}
        summary = {
            "num_sensors": num_sensors,
            "duration_s": duration_s,
            "processor_alive_before_stop": processor_alive,
            "max_queue_size": max(sizes) if sizes else 0,
            "final_queue_size": q.qsize(),
            "updates": update_count,
            "latest": latest,
            "averages": averages,
            "readings": readings,
            "rows_consumed": dict(rows_consumed),
            "missing": dict(missing_counts),
        }
    return summary
