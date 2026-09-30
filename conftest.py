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
                             capture_output=True, check=True, text=True)
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
