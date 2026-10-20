"""Repo-wide pytest setup.

PCB_START_METHOD=spawn forces the multiprocessing start method for the whole run, so a Linux
machine can check the code behaves the way it will on Windows and macOS (spawn is their default).
Without it, Linux runs use forkserver: plain fork after threads have started can deadlock, and
Python 3.14 makes forkserver the Linux default anyway.
"""

import multiprocessing as mp
import os
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent


def pytest_configure(config):
    method = os.environ.get("PCB_START_METHOD")
    if not method and sys.platform.startswith("linux"):
        method = "forkserver"
    if method:
        mp.set_start_method(method, force=True)


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
