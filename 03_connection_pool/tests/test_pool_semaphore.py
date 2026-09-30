import importlib
import runpy
import sys
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from connection_pool import benchmark as bm
from connection_pool import utils
from connection_pool.connection_pool import ConnectionPool, run_connection_pool
from connection_pool.square import concurrent_futures, pool_apply_async_chunked, pool_map, sequential_squares


@pytest.fixture(autouse=True)
def _outputs_in_tmp(tmp_path, monkeypatch):
    monkeypatch.setenv("PCB_OUTPUT_PATH", str(tmp_path / "outputs"))
    monkeypatch.setattr(utils, "OUTPUT_PATH", str(tmp_path / "outputs"))


def max_concurrency_from_log(log):
    """Replay the acquire/release events in time order and return the peak number of holders."""
    cur = peak = 0
    for e in sorted(log, key=lambda e: e["t"]):
        cur += 1 if e["event"] == "acquired" else -1
        peak = max(peak, cur)
    return peak


# ---------- T4 integration ----------
@pytest.mark.parametrize("start_method", [None, "spawn"])
def test_all_8_processes_get_a_connection_and_never_more_than_2(start_method):
    s = run_connection_pool(8, 2, work_s=(0.05, 0.15), seed=1, start_method=start_method, log_file="log.txt")
    assert s["acquired"] == s["released"] == 8
    assert s["max_concurrent_holders"] == 2
    assert max_concurrency_from_log(s["log"]) <= 2
    assert s["exit_codes"] == [0] * 8
    assert all(0 <= e["holders_after"] <= 2 for e in s["log"])
    lines = Path(utils.OUTPUT_PATH, "log.txt").read_text().splitlines()
    assert sum("Acquired" in line for line in lines) == 8


def test_timeout_returns_none_when_pool_stays_busy():
    pool = ConnectionPool(1)
    try:
        c = pool.get_connection()
        assert c == "DB_Conn_0"
        assert pool.get_connection(timeout=0.05) is None
        pool.release_connection(c)
        assert pool.get_connection(timeout=0.05) == "DB_Conn_0"
    finally:
        pool.shutdown()


def test_access_database_timeout_path():
    s = run_connection_pool(3, 1, work_s=(0.5, 0.5), seed=0, timeout=0.05, log_file="log.txt")
    assert 1 <= s["acquired"] < 3  # at least one gave up after waiting 0.05 s
    log = open(f"{utils.OUTPUT_PATH}/log.txt").read()
    assert "Timed out" in log


def test_invalid_pool_size():
    with pytest.raises(ValueError):
        ConnectionPool(0)


def test_utils_save_json(tmp_path):
    utils.save_json("x.json", {"a": 1})
    assert open(f"{utils.OUTPUT_PATH}/x.json").read().strip().startswith("{")


# ---------- T3 property ----------
@settings(max_examples=15, deadline=None)
@given(nums=st.lists(st.integers(-10**9, 10**9), max_size=300), workers=st.integers(1, 3))
def test_all_square_methods_agree(nums, workers):
    expected = sequential_squares(nums)
    assert pool_apply_async_chunked(nums, workers) == expected
    assert concurrent_futures(nums, workers) == expected


def test_pool_map_under_spawn():
    assert pool_map(list(range(50)), 2, "spawn") == [x * x for x in range(50)]


def test_benchmark_small(monkeypatch, tmp_path):
    monkeypatch.setattr(bm, "write_result", lambda *a, **k: tmp_path / "x.json")
    res = bm.main(["--sizes", "2000", "--repeats", "1", "--workers", "2"])
    assert {r["method"] for r in res["rows"]} == set(bm.methods(2, None))
    assert all(r["correct"] for r in res["rows"])
    assert "apply_async_per_item" in bm.format_table(res)


def test_benchmark_skips_apply_async_per_item_above_1e6(monkeypatch):
    monkeypatch.setattr(bm, "APPLY_ASYNC_PER_ITEM_MAX_N", 100)
    res = bm.benchmark([200], 2, 1, 1)
    assert res["skipped"] == [{"n": 200, "method": "apply_async_per_item",
                               "reason": "one task per item does not scale; see docstring"}]


def test_benchmark_rejects_wrong_output(monkeypatch):
    real = bm.methods
    monkeypatch.setattr(bm, "methods", lambda w, s: {**real(w, s), "pool_map": lambda xs: []})
    with pytest.raises(AssertionError, match="pool_map"):
        bm.benchmark([10], 2, 1, 1)


def test_main_demo_runs():
    ns = runpy.run_path(str(Path(__file__).resolve().parents[1] / "main.py"))
    s = ns["main"](["--work", "0.01", "0.02", "--no-save", "--processes", "4"])
    assert s["acquired"] == 4


# ---------- T2 regression: every process must eventually get a connection ----------
def check_every_process_gets_a_connection(acquired_count, num_processes=8):
    assert acquired_count == num_processes


def _run_2025_pool(load_2025, tmp_path, monkeypatch):
    pkg = tmp_path / "legacy" / "src"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    (pkg / "utils.py").write_text(load_2025("A1-P1", "03_connection_pool/src/utils.py"))
    (pkg / "connection_pool.py").write_text(load_2025("A1-P1", "03_connection_pool/src/connection_pool.py"))
    monkeypatch.syspath_prepend(str(tmp_path / "legacy"))
    monkeypatch.chdir(tmp_path)
    for mod in [m for m in sys.modules if m == "src" or m.startswith("src.")]:
        monkeypatch.delitem(sys.modules, mod)
    old = importlib.import_module("src.connection_pool")
    import multiprocessing as mp

    pool = old.ConnectionPool(size=2)
    procs = [mp.Process(target=old.access_database, args=(pool, i)) for i in range(8)]
    for p in procs:
        p.start()
    for p in procs:
        p.join()
    return sum(1 for e in pool.usage_log if e.startswith("Acquired"))


@pytest.mark.slow
def test_regression_semaphore_fails_on_2025_code(load_2025, tmp_path, monkeypatch):
    acquired = _run_2025_pool(load_2025, tmp_path, monkeypatch)
    assert acquired == 2  # what the audit and Phase 0 saw
    with pytest.raises(AssertionError):
        check_every_process_gets_a_connection(acquired)


def test_regression_semaphore_passes_on_2026_code():
    s = run_connection_pool(8, 2, work_s=(0.05, 0.1), seed=0)
    check_every_process_gets_a_connection(s["acquired"])
