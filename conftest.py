"""Repo-wide pytest setup.

PCB_START_METHOD=spawn forces the multiprocessing start method for the whole run, so a Linux
machine can check the code behaves the way it will on Windows and macOS (spawn is their default).
"""

import multiprocessing as mp
import os
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent


def pytest_configure(config):
    method = os.environ.get("PCB_START_METHOD")
    if method:
        mp.set_start_method(method, force=True)


def git_show(commit: str, path: str) -> str | None:
    """Return a file's content at a given commit, or None if history is not available (shallow clone)."""
    try:
        out = subprocess.run(["git", "-C", str(REPO), "show", f"{commit}:{path}"],
                             capture_output=True, check=True, text=True, encoding="utf-8")  # 2025 files hold emojis
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    return out.stdout


def original_2025(branch: str, path: str) -> str:
    """Content of `path` as imported from a 2025 branch; skips the test when history is missing."""
    try:
        sha = subprocess.run(
            ["git", "-C", str(REPO), "log", "--format=%H", "-1", "--fixed-strings",
             f"--grep=Original {branch} coursework"],
            capture_output=True, check=True, text=True).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        sha = ""
    content = git_show(sha, path) if sha else None
    if content is None:
        pytest.skip(f"2025 import commit for {branch} not available (needs full git history)")
    return content


@pytest.fixture
def load_2025():
    return original_2025


@pytest.fixture(autouse=True)
def _no_internet(monkeypatch):
    """Tests may only talk to 127.0.0.1: CI must never download the real datasets."""
    import urllib.parse
    import urllib.request

    real_urlopen = urllib.request.urlopen

    def guarded(url, *args, **kwargs):
        target = url if isinstance(url, str) else url.full_url
        host = urllib.parse.urlparse(target).hostname
        if host not in ("127.0.0.1", "localhost"):
            raise RuntimeError(f"test tried to reach {host}; use a local fixture instead")
        return real_urlopen(url, *args, **kwargs)

    monkeypatch.setattr(urllib.request, "urlopen", guarded)
