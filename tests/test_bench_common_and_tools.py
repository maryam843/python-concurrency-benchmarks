import importlib.util
import json
import os
import subprocess
from pathlib import Path

import pytest

from bench_common import TimingStats, efficiency, machine_info, speedup, time_repeats, write_result

REPO = Path(__file__).resolve().parents[1]


def _load_tool(name):
    spec = importlib.util.spec_from_file_location(name, REPO / "tools" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_timing_stats():
    s = TimingStats((1.0, 2.0, 3.0))
    assert s.mean == 2.0 and s.sd == pytest.approx(1.0)
    assert TimingStats((5.0,)).sd == 0.0
    assert s.to_dict()["runs"] == [1.0, 2.0, 3.0]


def test_time_repeats_and_errors():
    calls = []
    stats, value = time_repeats(lambda: calls.append(1) or len(calls), 3)
    assert value == 3 and len(stats.runs) == 3
    with pytest.raises(ValueError):
        time_repeats(lambda: None, 0)
    with pytest.raises(ValueError):
        speedup(1.0, 0.0)
    with pytest.raises(ValueError):
        efficiency(1.0, 1.0, 0)


def test_machine_info_has_no_hostname_or_paths():
    info = machine_info()
    assert {"os", "cpu_model", "logical_cpus", "python", "packages"} <= set(info)
    import platform
    assert platform.node() not in json.dumps(info) or platform.node() == ""
    assert HOME not in json.dumps(info)


def test_write_result(tmp_path):
    p = write_result("demo", {"rows": [1]}, seed=7, subdir="x", results_dir=tmp_path)
    doc = json.loads(p.read_text())
    assert p == tmp_path / "x" / "demo.json"
    assert doc["seed"] == 7 and doc["rows"] == [1] and "timestamp_utc" in doc and "machine" in doc


# ---------- T12 scanner logic ----------
# Test inputs are assembled at runtime so this file itself never contains an address or a user path.
AT, HOME = "@", "/" + "home" + "/"
EMAIL = "someone" + AT + "example.com"
IP = ".".join(["192", "168", "1", "20"])


def test_pii_scan_patterns():
    scan = _load_tool("pii_scan")
    assert scan.scan_text("contact " + EMAIL, "f")
    assert scan.scan_text(f"host {IP} ready", "f")
    assert scan.scan_text("path " + HOME + "alice/project", "f")
    assert scan.scan_text("key AKIA" + "ABCDEFGHIJKLMNOP", "f")
    assert scan.scan_text("-----BEGIN RSA " + "PRIVATE KEY-----", "f")
    assert not scan.scan_text("numpy 2.5.3 and OpenMPI 4.1.6 on 127.0.0.1", "f")
    assert not scan.scan_text("185722545+maryam843@users.noreply.github.com", "f")


def test_pii_scan_history_of_this_repo_is_clean():
    scan = _load_tool("pii_scan")
    if subprocess.run(["git", "-C", str(REPO), "rev-parse"], capture_output=True).returncode != 0:
        pytest.skip("not a git checkout")
    assert scan.scan_history(REPO) == []


def test_pii_scan_finds_hits_in_a_new_repo(tmp_path):
    scan = _load_tool("pii_scan")
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / "a.txt").write_text(f"server at {IP}\n")
    env = {**os.environ, "GIT_AUTHOR_NAME": "x", "GIT_AUTHOR_EMAIL": EMAIL,
           "GIT_COMMITTER_NAME": "x", "GIT_COMMITTER_EMAIL": EMAIL}
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "-c", "commit.gpgsign=false", "commit", "-q", "-m", "m"],
                   check=True, env=env)
    hits = scan.scan_history(tmp_path)
    assert any("IPv4" in h for h in hits) and any("e-mail not allowed" in h for h in hits)
    (tmp_path / "b.txt").write_text(EMAIL + "\n")
    assert any("b.txt" in h for h in scan.scan_worktree(tmp_path))
    assert scan.main(["--repo", str(tmp_path), "--worktree"]) == 1


def test_fixture_generator_is_reproducible(tmp_path):
    mk = _load_tool("make_fixtures")
    a = mk.make_air_quality(tmp_path / "a.csv")
    b = mk.make_air_quality(tmp_path / "b.csv")
    assert a.read_text() == b.read_text() == (REPO / "tests/fixtures/air_quality_tiny.csv").read_text()
