import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st

from mpi_squares import scaling
from mpi_squares.core import MAX_N, chunk_counts, local_squares, peak_rss_mb, squares_checksum

FOLDER = Path(__file__).resolve().parents[1]
HAVE_MPI = shutil.which("mpiexec") is not None and importlib.util.find_spec("mpi4py") is not None
needs_mpi = pytest.mark.skipif(
    not HAVE_MPI or scaling.root_needs_permission(),
    reason="no MPI runtime or mpi4py (MPI tests run on Linux CI), or running as root without PCB_ALLOW_ROOT=1",
)


def mpirun(ranks, script, *args, timeout=120):
    cmd = [shutil.which("mpiexec"), "-n", str(ranks), sys.executable, str(script), *map(str, args)]
    return subprocess.run(cmd, capture_output=True, text=True, env=scaling.mpi_env(), timeout=timeout)


# ---------- T1 unit ----------
def test_chunk_counts_match_lab_split():
    assert chunk_counts(10, 4) == ([3, 3, 2, 2], [0, 3, 6, 8])
    assert chunk_counts(0, 3) == ([0, 0, 0], [0, 0, 0])
    with pytest.raises(ValueError):
        chunk_counts(10, 0)
    with pytest.raises(ValueError):
        chunk_counts(MAX_N + 1, 2)


def test_local_squares_and_checksum():
    assert local_squares(3, 3).tolist() == [16, 25, 36]
    assert local_squares(0, 0).size == 0
    big = np.array([MAX_N], dtype=np.int64)
    assert int(big[0]) ** 2 < 2**63  # int64 is exact up to MAX_N
    assert squares_checksum(np.array([1, 4, 9])) == 14
    rss = peak_rss_mb()
    assert rss > 0 or rss != rss  # NaN on Windows


# ---------- T3 property ----------
@given(n=st.integers(0, 10**7), size=st.integers(1, 256))
def test_chunks_are_contiguous_and_balanced(n, size):
    counts, displs = chunk_counts(n, size)
    assert sum(counts) == n
    assert max(counts) - min(counts) <= 1
    assert displs == [sum(counts[:r]) for r in range(size)]


@given(n=st.integers(0, 3000), size=st.integers(1, 16))
def test_pieces_concatenate_to_all_squares(n, size):
    counts, displs = chunk_counts(n, size)
    pieces = np.concatenate([local_squares(d, c) for c, d in zip(counts, displs, strict=True)] or [[]])
    assert pieces.tolist() == [i * i for i in range(1, n + 1)]


# ---------- T4 integration (real mpiexec) ----------
@needs_mpi
@pytest.mark.mpi
@pytest.mark.parametrize("ranks", [1, 2, 4])
@pytest.mark.parametrize("gather", [True, False])
def test_calculate_squares_ranks(tmp_path, ranks, gather):
    n = 12_345
    out = tmp_path / "s.json"
    args = [n, "--json", out] + ([] if gather else ["--no-gather"])
    proc = mpirun(ranks, FOLDER / "calculate_squares.py", *args)
    assert proc.returncode == 0, proc.stderr
    s = json.loads(out.read_text())
    expected = np.arange(1, n + 1, dtype=np.int64) ** 2
    assert s["ranks"] == ranks and s["length"] == n and s["last_square"] == n * n
    assert s["checksum_mod_2_64"] == squares_checksum(expected)
    assert len(s["peak_rss_mb_per_rank"]) == ranks
    if gather:
        assert s["gathered_length"] == n and s["first_squares"] == [1, 4, 9, 16, 25]
    assert f"length={n:,}" in proc.stdout


@needs_mpi
@pytest.mark.mpi
def test_small_n_prints_plain_list():
    proc = mpirun(2, FOLDER / "calculate_squares.py", 10)
    assert "Squared numbers: [1, 4, 9, 16, 25, 36, 49, 64, 81, 100]" in proc.stdout


@needs_mpi
@pytest.mark.mpi
def test_scaling_runner_small():
    res = scaling.scaling([1, 2], [5000], repeats=1)
    assert [r["ranks"] for r in res["rows"]] == [1, 2]
    assert res["rows"][0]["speedup_vs_1_rank"] == pytest.approx(1.0)
    assert "| 5e+03 | 2 |" in scaling.format_table(res)


@needs_mpi
@pytest.mark.mpi
def test_mpi_test_script_runs():
    proc = mpirun(2, FOLDER / "mpi_test.py")
    assert proc.returncode == 0
    assert proc.stdout.count("running on") == 2


# ---------- T2 regression: fail on 2025 code, pass on 2026 code ----------
def check_runs_with_one_rank(script: Path):
    proc = mpirun(1, script)
    errors = [line for line in proc.stderr.splitlines() if "Error" in line or "Exception" in line]
    assert proc.returncode == 0, errors


@needs_mpi
@pytest.mark.mpi
def test_regression_one_rank_fails_on_2025_code(load_2025, tmp_path):
    script = tmp_path / "mpi_program_2025.py"
    script.write_text(load_2025("L6", "05_mpi_multi_node/mpi_program.py"), encoding="utf-8")
    with pytest.raises(AssertionError, match="MPI_ERR_RANK"):
        check_runs_with_one_rank(script)


@needs_mpi
@pytest.mark.mpi
def test_regression_one_rank_passes_on_2026_code():
    check_runs_with_one_rank(FOLDER / "mpi_program.py")


def check_prints_plain_numbers(stdout: str):
    assert "np.int64" not in stdout and "[1, 4, 9" in stdout


@needs_mpi
@pytest.mark.mpi
def test_regression_numpy_scalars_printed_on_2025_code(load_2025, tmp_path):
    script = tmp_path / "calculate_squares_2025.py"
    script.write_text(load_2025("L6", "05_mpi_multi_node/calculate_squares.py"), encoding="utf-8")
    with pytest.raises(AssertionError):
        check_prints_plain_numbers(mpirun(2, script).stdout)


@needs_mpi
@pytest.mark.mpi
def test_regression_plain_numbers_on_2026_code():
    check_prints_plain_numbers(mpirun(2, FOLDER / "calculate_squares.py", 10).stdout)


def test_mpi_env_allows_root_only_when_asked(monkeypatch):
    for name in ("OMPI_ALLOW_RUN_AS_ROOT", "OMPI_ALLOW_RUN_AS_ROOT_CONFIRM", "PCB_ALLOW_ROOT"):
        monkeypatch.delenv(name, raising=False)
    env = scaling.mpi_env()
    assert "OMPI_ALLOW_RUN_AS_ROOT" not in env and "OMPI_ALLOW_RUN_AS_ROOT_CONFIRM" not in env
    monkeypatch.setenv("PCB_ALLOW_ROOT", "1")
    env = scaling.mpi_env()
    assert env["OMPI_ALLOW_RUN_AS_ROOT"] == "1" and env["OMPI_ALLOW_RUN_AS_ROOT_CONFIRM"] == "1"
    assert not scaling.root_needs_permission()


def test_scaling_requires_mpiexec(monkeypatch):
    monkeypatch.setattr(scaling.shutil, "which", lambda name: None)
    with pytest.raises(RuntimeError, match="mpiexec not found"):
        scaling.run_once(1, 10)
