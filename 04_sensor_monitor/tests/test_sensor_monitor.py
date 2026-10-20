import importlib
import io
import subprocess
import sys
import threading
import time
from pathlib import Path
from queue import Queue

import pandas as pd
import pytest
from hypothesis import given
from hypothesis import strategies as st

from sensor_monitor import airquality, display, sensor

REPO = Path(__file__).resolve().parents[2]
FIXTURE = REPO / "tests" / "fixtures" / "air_quality_tiny.csv"


@pytest.fixture(autouse=True)
def _clean_state():
    sensor.reset_state()
    yield
    sensor.stop_event.set()
    sensor.reset_state()


# ---------- T1 unit ----------
def test_drain_and_update_keeps_readings_and_float_averages_apart():
    q = Queue()
    for sid, t in [(0, 20), (0, 30), (1, 10), (0, 40)]:
        q.put((sid, t))
    assert sensor.drain_and_update(q) == 4
    assert q.empty()
    assert sensor.sensor_readings == {0: [20, 30, 40], 1: [10]}
    assert sensor.temperature_averages == {0: 30.0, 1: 10.0}
    q.put((1, 20))
    sensor.drain_and_update(q)
    assert sensor.temperature_averages[1] == 15.0
    assert sensor.update_count == 2


def test_random_source_is_reproducible_and_in_range():
    a = [next(g) for g in [sensor.random_source(5)] for _ in range(50)]
    g1, g2 = sensor.random_source(9), sensor.random_source(9)
    assert [next(g1) for _ in range(20)] == [next(g2) for _ in range(20)]
    assert all(15 <= x <= 40 for x in a)


def test_wait_for_update_times_out_and_wakes():
    assert sensor.wait_for_update(0, timeout=0.05) == 0
    q = Queue()
    threading.Timer(0.05, sensor.drain_and_update, args=(q,)).start()
    assert sensor.wait_for_update(0, timeout=2) == 1


def test_render_lines_use_num_sensors():
    lines = display.render_lines(5, [1.0, None, 3.0, None, 5.0], [None] * 5)
    assert len(lines) == 4 + 5
    assert "Sensor 4: 5.0°C" in lines[1]
    assert lines[-1] == "Sensor 4 Average: --°C"


def test_redraw_moves_cursor_up_and_never_clears_screen():
    out = io.StringIO()
    n_lines = display.initialize_display(4, out)
    sensor.latest_temperatures[3] = 22.5
    sensor.temperature_averages[3] = 21.25
    display.redraw(4, out)
    text = out.getvalue()
    assert f"\x1b[{n_lines}A" in text
    assert "\x1b[2J" not in text and "clear" not in text
    assert "Sensor 3 Average: 21.25°C" in text


def test_update_display_loop_redraws_and_stops():
    out = io.StringIO()
    display.initialize_display(2, out)
    t = threading.Thread(target=display.update_display, args=(2, out, 0.05), daemon=True)
    t.start()
    time.sleep(0.2)
    sensor.stop_event.set()
    t.join(timeout=2)
    assert not t.is_alive()
    assert out.getvalue().count("\x1b[6A") >= 2


def test_airquality_loader_handles_minus_200_and_empty_rows():
    temps = airquality.load_temperatures(FIXTURE)
    assert len(temps) == 300
    raw = pd.read_csv(FIXTURE, sep=";", decimal=",").dropna(subset=["Date"])
    assert temps.isna().sum() == (raw["T"] == -200).sum() > 0
    stream = list(airquality.sensor_stream(temps, 0))
    assert stream.count(None) == temps.isna().sum()
    assert all(isinstance(x, float) for x in stream if x is not None)


@given(sensor_id=st.integers(0, 50), offset=st.integers(1, 400))
def test_sensor_stream_starts_at_offset(sensor_id, offset):
    temps = pd.Series([float(i) for i in range(300)])
    first = next(airquality.sensor_stream(temps, sensor_id, offset))
    assert first == float((sensor_id * offset) % 300)


def test_finite_source_ends_sensor_thread():
    q = Queue()
    sensor.simulate_sensor(0, q, interval=0.0, source=iter([1.0, None, 3.0]))
    assert q.qsize() == 2
    assert sensor.missing_counts == {0: 1} and sensor.rows_consumed == {0: 3}


# ---------- T4 integration: ~3 s run on the fixture ----------
def test_three_second_run_with_fixture_data_matches_pandas():
    n = 3
    sources = airquality.make_sources(FIXTURE, n, offset_rows=50)
    s = sensor.run_monitor(n, 3.0, sensor_interval=0.02, process_interval=0.5, sources=sources)
    assert s["processor_alive_before_stop"]
    assert s["final_queue_size"] == 0
    # sensors add n readings per 0.02 s and the processor drains every 0.5 s: at most ~75 + slack waiting
    assert s["max_queue_size"] <= n * (0.5 / 0.02) * 1.6
    assert s["updates"] >= 5
    for i in range(n):
        consumed = s["rows_consumed"][i]
        assert consumed > 50
        expected = airquality.expected_average(FIXTURE, i, consumed, offset_rows=50)
        assert s["averages"][i] == pytest.approx(expected)
        assert len(s["readings"][i]) + s["missing"].get(i, 0) == consumed


def test_main_headless_data_mode_runs(capsys):
    ns = importlib.import_module("runpy").run_path(str(REPO / "04_sensor_monitor" / "main.py"))
    s = ns["main"](["--mode", "data", "--data", str(FIXTURE), "--headless", "--duration", "1",
                    "--sensor-interval", "0.02", "--process-interval", "0.2", "--num-sensors", "2"])
    assert s["num_sensors"] == 2 and s["processor_alive_before_stop"]
    assert '"mode": "data"' in capsys.readouterr().out


def test_main_live_display_random_mode(capsys):
    ns = importlib.import_module("runpy").run_path(str(REPO / "04_sensor_monitor" / "main.py"))
    ns["main"](["--duration", "0.6", "--sensor-interval", "0.05", "--process-interval", "0.2"])
    out = capsys.readouterr().out
    assert "\x1b[7A" in out and "Sensor 2 Average:" in out


# ---------- T2 regression tests: each check guards a bug the 2025 code had ----------


def _watch_thread_errors(monkeypatch):
    errors = []
    monkeypatch.setattr(threading, "excepthook", lambda a: errors.append(repr(a.exc_value)))
    return errors


def check_processor_survives_and_queue_stays_bounded(start, run_s=1.5, bound=40):
    """start() launches 3 sensors (1 reading per 20 ms) and the processor; returns (queue, processor)."""
    q, processor = start()
    time.sleep(run_s)
    assert processor.is_alive(), "processor thread died"
    assert q.qsize() <= bound, f"queue grew to {q.qsize()}"


def test_regression_processor_and_queue_pass_on_2026_code(monkeypatch):
    errors = _watch_thread_errors(monkeypatch)

    def start():
        q = Queue()
        _, p = sensor.start_threads(3, q, sensor_interval=0.02, process_interval=0.1)
        return q, p

    check_processor_survives_and_queue_stays_bounded(start)
    assert errors == []


def check_main_starts_from_repo_root(cmd, cwd):
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=30)
    assert proc.returncode == 0, proc.stderr[-300:]


def test_regression_main_imports_pass_on_2026_code():
    check_main_starts_from_repo_root(
        [sys.executable, "04_sensor_monitor/main.py", "--headless", "--duration", "1",
         "--sensor-interval", "0.05", "--process-interval", "0.2"], REPO)
