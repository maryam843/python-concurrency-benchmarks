import importlib
import re
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


# ---------- T2 regression tests: each check fails on the 2025 code and passes on the 2026 code ----------
def _import_2025(tmp_path, monkeypatch, source, module_name):
    (tmp_path / f"{module_name}.py").write_text(source)
    monkeypatch.syspath_prepend(str(tmp_path))  # spawned children inherit sys.path
    return importlib.import_module(module_name)


def check_sum_correct_at_1e6(fn):
    assert fn(10**6, 4) == 500_000_500_000


def test_regression_int32_overflow_fails_on_2025_code(load_2025, tmp_path, monkeypatch):
    src = load_2025("L3-P2", "02_parallel_sum/src/multiprocessing.py")
    old = _import_2025(tmp_path, monkeypatch, src, "mp_sum_2025")
    assert old.parallel_process_sum(10**6, 4) == 1_784_293_664  # the documented wrong value
    with pytest.raises(AssertionError):
        check_sum_correct_at_1e6(old.parallel_process_sum)


def test_regression_int32_overflow_passes_on_2026_code():
    check_sum_correct_at_1e6(parallel_process_sum)
    # the same code with the 2025 typecode reproduces the bug, so the fix is exactly 'i' -> 'q'
    assert parallel_process_sum(10**6, 4, typecode="i") == 1_784_293_664


def check_no_stdlib_shadowing(py_paths):
    shadowing = [p for p in py_paths if Path(p).stem in sys.stdlib_module_names]
    assert not shadowing, shadowing


def test_regression_stdlib_shadowing_fails_on_2025_code(load_2025):
    load_2025("L3-P2", "02_parallel_sum/src/multiprocessing.py")  # skips without history
    sha = subprocess.run(["git", "-C", str(REPO), "log", "--format=%H", "-1", "--fixed-strings",
                          "--grep=Original L3-P2 coursework"], capture_output=True, text=True).stdout.strip()
    files = subprocess.run(["git", "-C", str(REPO), "ls-tree", "-r", "--name-only", sha, "02_parallel_sum"],
                           capture_output=True, text=True, check=True).stdout.split()
    with pytest.raises(AssertionError):
        check_no_stdlib_shadowing([f for f in files if f.endswith(".py")])


def test_regression_stdlib_shadowing_passes_on_2026_code():
    files = [str(p.relative_to(REPO)) for p in REPO.rglob("*.py") if ".venv" not in p.parts]
    check_no_stdlib_shadowing(files)


def check_spawn_safe(calc):
    assert calc(1000, 2) == closed_form(1000)


def test_regression_nested_worker_fails_under_spawn_on_2025_code(load_2025, tmp_path, monkeypatch):
    import multiprocessing as mp

    src = load_2025("L3-P1", "02_parallel_sum/src/processing.py")
    old = _import_2025(tmp_path, monkeypatch, src, "processing_2025")
    monkeypatch.setattr(old, "multiprocessing", mp.get_context("spawn"))
    with pytest.raises((AttributeError, TypeError), match="local object"):
        check_spawn_safe(lambda n, p: old.calculate_sum_multiprocessing(n, p)[0])


def test_regression_nested_worker_passes_under_spawn_on_2026_code():
    check_spawn_safe(lambda n, p: calculate_sum_multiprocessing(n, p, "spawn")[0])


def check_gustafson(gustafson_n4_p09):
    assert gustafson_n4_p09() == pytest.approx(3.70, abs=0.005)


def _gustafson_printed_by_2025_main(load_2025, tmp_path):
    for rel in ("main.py", "src/functions.py", "src/threads.py", "src/processing.py"):
        dest = tmp_path / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(load_2025("L3-P1", f"02_parallel_sum/{rel}"))
    # Under spawn (Windows) the 2025 process sum crashes first (nested worker), so swap it for the
    # sequential sum: this test is only about the Gustafson line that main.py prints at the end.
    code = ("import main; main.calculate_sum_multiprocessing = lambda n, p: main.calculate_sum_sequential(n); "
            "main.evaluate_performance(10**5, 4, 4)")
    out = subprocess.run([sys.executable, "-c", code],
                         cwd=tmp_path, capture_output=True, text=True, check=True).stdout
    return float(re.search(r"Gustafson's Speedup \(Process\): ([\d.]+)", out).group(1))


def test_regression_gustafson_fails_on_2025_code(load_2025, tmp_path):
    value = _gustafson_printed_by_2025_main(load_2025, tmp_path)
    assert value == pytest.approx(3.60)
    with pytest.raises(AssertionError):
        check_gustafson(lambda: value)


def test_regression_gustafson_passes_on_2026_code():
    check_gustafson(lambda: gustafson_speedup(0.9, 4))
