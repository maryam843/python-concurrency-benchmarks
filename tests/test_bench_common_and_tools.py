import importlib.util
import json
import os
import subprocess
from pathlib import Path

import pytest

from bench_common import (
    TimingStats,
    efficiency,
    first_run_outlier,
    machine_info,
    speedup,
    time_repeats,
    time_with_warmup,
    write_result,
)

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
    assert s.median == 2.0 and s.to_dict()["median"] == 2.0


def test_first_run_outlier_is_flagged():
    assert first_run_outlier([0.43, 0.022, 0.020, 0.021, 0.020])  # cold first run, about 20x the median
    assert not first_run_outlier([0.025, 0.022, 0.020, 0.021, 0.020])
    assert not first_run_outlier([0.43])  # one run: nothing to compare with
    assert TimingStats((9.0, 1.0, 1.0)).first_run_outlier
    assert not TimingStats((2.9, 1.0, 1.0)).first_run_outlier


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


def test_time_with_warmup_runs_once_before_timing():
    calls = []
    stats, value = time_with_warmup(lambda: calls.append(1) or len(calls), 3)
    assert len(calls) == 4 and len(stats.runs) == 3  # 1 untimed warm-up + 3 timed runs
    assert value == 4  # the value comes from the last timed run


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


# ---------- scanner logic ----------
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
    assert not scan.scan_text("terms at https://www.example.gov" + HOME + "terms-of-use.page", "f")
    assert not scan.scan_text("repo at https://github.com/someone/project", "f")  # generic domain, not personal
    assert not scan.scan_text("185722545+maryam843@users.noreply.github.com", "f")


def test_pii_scan_denylist_from_env(monkeypatch):
    scan = _load_tool("pii_scan")
    fake = "-".join(["zz", "test", "token", "123"])  # built at runtime, like the inputs above
    monkeypatch.delenv("PII_DENYLIST", raising=False)
    assert not scan.scan_text(f"note {fake} here", "f")
    monkeypatch.setenv("PII_DENYLIST", f" other-value , {fake.upper()} ")
    hits = scan.scan_text(f"note {fake} here", "f.txt")
    assert hits == ["f.txt: denylisted token"]
    assert fake not in hits[0]
    assert not scan.scan_text("nothing personal here", "f")


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


# ---------- claims checker logic ----------
def test_claims_checker(tmp_path, monkeypatch):
    chk = _load_tool("check_readme_claims")
    (tmp_path / "r").mkdir()
    (tmp_path / "r" / "x.json").write_text(json.dumps({"rows": [{"a": 1, "v": 4.2}, {"a": 2, "v": 9.0}], "t": 1.5}))
    monkeypatch.setattr(chk, "RESULTS", tmp_path / "r")
    good = tmp_path / "good.md"
    good.write_text("Speed **4.20x**<!-- claim: x.json | rows[a=1].v | {:.2f}x --> and "
                    "1.5 s<!-- claim: x.json | t | {:.1f} s -->.\n"
                    "Old 6.79 s from a saved file <!-- 2025 evidence -->\n")
    assert chk.check_file(good) == []
    bad = tmp_path / "bad.md"
    bad.write_text("Speed 4.30x<!-- claim: x.json | rows[a=1].v | {:.2f}x -->. Unbacked 3.3x here.\n"
                   "Broken <!-- claim: x.json | rows[a=7].v | {:.2f}x -->\n")
    errors = chk.check_file(bad)
    assert any("claim says '4.20x'" in e for e in errors)
    assert any("unclaimed number '3.3x'" in e for e in errors)
    assert any("matched 0 items" in e for e in errors)
    assert chk.select({"a": [{"k": 1, "v": [5, 6]}]}, "a[k=1].v.1") == 6
