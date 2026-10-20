import subprocess
import sys
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from parallel_sum import benchmark as bm
from parallel_sum.functions import calculate_sum_sequential
from parallel_sum.laws import amdahl_speedup, gustafson_speedup
from parallel_sum.numpy_sum import numpy_sum
from parallel_sum.partition import chunk_bounds
from parallel_sum.pool_sum import calculate_sum_pool
from parallel_sum.processing import calculate_sum_multiprocessing
from parallel_sum.shared_array import parallel_process_sum
from parallel_sum.threads import calculate_sum_parallel

REPO = Path(__file__).resolve().parents[2]
FOLDER = REPO / "02_parallel_sum"


def closed_form(n):
    return n * (n + 1) // 2


# ---------- T1 unit ----------
def test_chunk_bounds_cover_range_without_gaps():
    assert chunk_bounds(10, 3) == [(1, 3), (4, 6), (7, 10)]
    with pytest.raises(ValueError):
        chunk_bounds(10, 0)
    with pytest.raises(ValueError):
        chunk_bounds(-1, 2)


def test_laws_known_values():
    assert amdahl_speedup(0.9, 4) == pytest.approx(1 / (0.1 + 0.225))
    assert gustafson_speedup(0.9, 4) == pytest.approx(3.7)
    assert gustafson_speedup(0.9, 1) == pytest.approx(1.0)
    with pytest.raises(ValueError):
        amdahl_speedup(1.5, 4)
    with pytest.raises(ValueError):
        gustafson_speedup(0.5, 0)


def test_numpy_sum_limits():
    assert numpy_sum(0) == 0
    with pytest.raises(ValueError):
        numpy_sum(-1)
    with pytest.raises(ValueError):
        numpy_sum(5_000_000_000)


@pytest.mark.parametrize("n", [0, 1, 2, 3, 10, 1000])
def test_small_n_including_fewer_items_than_workers(n):
    assert calculate_sum_parallel(n, 4)[0] == closed_form(n)
    assert calculate_sum_multiprocessing(n, 4)[0] == closed_form(n)
    assert parallel_process_sum(n, 4) == closed_form(n)
    assert calculate_sum_pool(n, 4) == closed_form(n)


# ---------- T3 property tests: every method equals n(n+1)/2 ----------
@given(n=st.integers(0, 200_000), p=st.integers(1, 64))
def test_chunks_partition_1_to_n(n, p):
    bounds = chunk_bounds(n, p)
    assert len(bounds) == p
    assert sum(max(0, e - s + 1) for s, e in bounds) == n
    assert sum(sum(range(s, e + 1)) for s, e in bounds) == closed_form(n)


@given(n=st.integers(0, 300_000))
def test_sequential_threads_numpy_property(n):
    assert calculate_sum_sequential(n)[0] == closed_form(n)
    assert calculate_sum_parallel(n, 4)[0] == closed_form(n)
    assert numpy_sum(n) == closed_form(n)


@given(n=st.integers(0, 100_000), block=st.integers(1, 5000))
def test_numpy_blocking_property(n, block):
    assert numpy_sum(n, block=block) == closed_form(n)


@settings(max_examples=10, deadline=None)
@given(n=st.integers(0, 100_000), p=st.integers(1, 4))
def test_process_methods_property(n, p):
    assert calculate_sum_multiprocessing(n, p)[0] == closed_form(n)
    assert parallel_process_sum(n, p) == closed_form(n)
    assert calculate_sum_pool(n, p) == closed_form(n)


# ---------- T4 integration ----------
def test_all_methods_at_1e6_and_under_spawn():
    n = 10**6
    for fn, _ in bm.methods(4, "spawn").values():
        assert fn(n) == closed_form(n)


def test_benchmark_rows(monkeypatch, tmp_path):
    monkeypatch.setattr(bm, "write_result", lambda *a, **k: tmp_path / "x.json")
    res = bm.main(["--sizes", "2e4", "--repeats", "1"])
    assert {r["method"] for r in res["rows"]} == set(bm.methods(4, None))
    for r in res["rows"]:
        assert r["correct"] and r["sum"] == closed_form(20_000)
        assert r["efficiency"] == pytest.approx(r["speedup"] / r["workers"])
    assert "numpy_vectorised" in bm.format_table(res)


def test_benchmark_rejects_wrong_sum(monkeypatch):
    real = bm.methods

    def broken(workers, start_method):
        m = dict(real(workers, start_method))
        m["threads"] = (lambda n: -1, workers)
        return m

    monkeypatch.setattr(bm, "methods", broken)
    with pytest.raises(AssertionError, match="threads gave -1"):
        bm.benchmark([100], 2, 1)


def test_main_script_prints_correct_sums_and_gustafson():
    out = subprocess.run([sys.executable, str(FOLDER / "main.py"), "1e5", "4"],
                         capture_output=True, text=True, check=True).stdout
    assert out.count(f"Sum: {closed_form(10**5)}") == 3
    assert "Gustafson's Speedup (Process): 3.70" in out


# ---------- T2 regression tests: each check guards a bug the 2025 code had ----------


def check_sum_correct_at_1e6(fn):
    assert fn(10**6, 4) == 500_000_500_000


def test_regression_int32_overflow_passes_on_2026_code():
    check_sum_correct_at_1e6(parallel_process_sum)
    # the same code with the 2025 typecode reproduces the bug, so the fix is exactly 'i' -> 'q'
    assert parallel_process_sum(10**6, 4, typecode="i") == 1_784_293_664


def check_no_stdlib_shadowing(py_paths):
    shadowing = [p for p in py_paths if Path(p).stem in sys.stdlib_module_names]
    assert not shadowing, shadowing


def test_regression_stdlib_shadowing_passes_on_2026_code():
    files = [str(p.relative_to(REPO)) for p in REPO.rglob("*.py") if ".venv" not in p.parts]
    check_no_stdlib_shadowing(files)


def check_spawn_safe(calc):
    assert calc(1000, 2) == closed_form(1000)


def test_regression_nested_worker_passes_under_spawn_on_2026_code():
    check_spawn_safe(lambda n, p: calculate_sum_multiprocessing(n, p, "spawn")[0])


def check_gustafson(gustafson_n4_p09):
    assert gustafson_n4_p09() == pytest.approx(3.70, abs=0.005)


def test_regression_gustafson_passes_on_2026_code():
    check_gustafson(lambda: gustafson_speedup(0.9, 4))
