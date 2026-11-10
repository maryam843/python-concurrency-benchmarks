import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from bench_common import efficiency
from threads_vs_processes import benchmark as bm
from threads_vs_processes.workloads import generate_and_add_numbers, generate_and_join_letters, run_task


# unit tests
def test_workloads_are_deterministic_with_seed():
    assert generate_and_add_numbers(1000, seed=7) == generate_and_add_numbers(1000, seed=7)
    assert generate_and_join_letters(1000, seed=7) == generate_and_join_letters(1000, seed=7)


def test_letters_are_printable_ascii():
    s = generate_and_join_letters(500, seed=1)
    assert len(s) == 500
    assert all(33 <= ord(c) <= 126 for c in s)


def test_numbers_within_range():
    assert 0 <= generate_and_add_numbers(10, seed=3) <= 10 * 1_000_000
    assert generate_and_add_numbers(0, seed=3) == 0


def test_config_workers():
    workers = {c.name: c.workers for c in bm.CONFIGS}
    assert workers == {
        "sequential": 1,
        "threads_1_per_function": 2,
        "processes_1_per_function": 2,
        "threads_2_per_function": 4,
        "processes_2_per_function": 4,
    }


def test_run_task_dispatch():
    assert run_task(("numbers", 5, 1)) == generate_and_add_numbers(5, 1)
    assert run_task(("letters", 5, 1)) == generate_and_join_letters(5, 1)


# property: splitting never changes the total amount of work
@given(n=st.integers(min_value=0, max_value=10**8), k=st.integers(min_value=1, max_value=16))
def test_make_tasks_preserves_total_work(n, k):
    tasks = bm.make_tasks(n, k, seed=0)
    assert len(tasks) == 2 * k
    for name in ("numbers", "letters"):
        assert sum(t[1] for t in tasks if t[0] == name) == n


@settings(max_examples=25, deadline=None)
@given(t_seq=st.floats(0.01, 100), t_par=st.floats(0.01, 100), p=st.integers(1, 64))
def test_efficiency_is_speedup_over_p(t_seq, t_par, p):
    assert efficiency(t_seq, t_par, p) == pytest.approx((t_seq / t_par) / p)


# integration: every config returns exactly the sequential answer for the same task list
@pytest.mark.parametrize("cfg", bm.CONFIGS, ids=lambda c: c.name)
def test_every_config_matches_sequential(cfg):
    tasks = bm.make_tasks(3001, cfg.per_function, seed=11)
    assert bm.run_config(cfg, tasks) == bm.run_sequential(tasks)


def test_processes_work_under_spawn():
    cfg = bm.CONFIGS[2]
    tasks = bm.make_tasks(500, 1, seed=5)
    assert bm.run_config(cfg, tasks, start_method="spawn") == bm.run_sequential(tasks)


def test_benchmark_rows_and_efficiency_use_real_p(tmp_path, monkeypatch):
    monkeypatch.setattr(bm, "write_result", lambda *a, **k: tmp_path / "x.json")
    res = bm.main(["--n", "2000", "--repeats", "2", "--seed", "1"])
    rows = {r["config"]: r for r in res["rows"]}
    assert rows["sequential"]["speedup"] == pytest.approx(1.0)
    for r in res["rows"]:
        assert r["efficiency"] == pytest.approx(r["speedup"] / r["workers"])
        assert r["result_matches_sequential"]
    assert "| sequential | 1 |" in bm.format_table(res)


def test_benchmark_warms_up_each_config_and_uses_medians(monkeypatch):
    calls = {}
    real = bm.run_config

    def counting(cfg, tasks, start_method=None):
        calls[cfg.name] = calls.get(cfg.name, 0) + 1
        return real(cfg, tasks, start_method)

    monkeypatch.setattr(bm, "run_config", counting)
    res = bm.benchmark(500, 3, seed=1)
    assert calls == {c.name: 1 + 3 for c in bm.CONFIGS}  # one untimed warm-up + 3 timed runs each
    seq = res["rows"][0]
    assert res["speedup_from"] == "median"
    for r in res["rows"]:
        assert len(r["runs_s"]) == 3
        assert r["speedup"] == pytest.approx(seq["median_s"] / r["median_s"])
        assert r["speedup_of_means"] == pytest.approx(seq["mean_s"] / r["mean_s"])


def test_benchmark_detects_wrong_result(monkeypatch):
    real = bm.run_config

    def broken(cfg, tasks, start_method=None):
        total, letters = real(cfg, tasks, start_method)
        return (total + 1, letters) if cfg.kind == "threads" else (total, letters)

    monkeypatch.setattr(bm, "run_config", broken)
    with pytest.raises(AssertionError, match="different result"):
        bm.benchmark(200, 1, seed=0)


# reproducibility: same seed -> identical results
def test_same_seed_same_results():
    a = bm.run_sequential(bm.make_tasks(2000, 2, seed=42))
    b = bm.run_sequential(bm.make_tasks(2000, 2, seed=42))
    c = bm.run_sequential(bm.make_tasks(2000, 2, seed=43))
    assert a == b
    assert a != c


# regression: the 2025 notebook divided by np = 4 although only 2 workers ran
def check_efficiency_uses_real_p(efficiency_fn):
    """Regression check: 1 process per function = 2 workers, so efficiency must be S/2."""
    t_seq, t_par = 1.8, 1.0
    assert efficiency_fn(t_seq, t_par, 2) == pytest.approx((t_seq / t_par) / 2)


def test_regression_efficiency_passes_on_2026_code():
    check_efficiency_uses_real_p(efficiency)
