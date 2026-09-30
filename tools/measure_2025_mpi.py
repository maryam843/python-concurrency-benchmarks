"""Measure the 2025 calculate_squares.py (from its import commit) at larger n, for comparison with 2026.

Only `n = 10` is changed; everything else is the 2025 code. Each rank reports its peak memory.

    python tools/measure_2025_mpi.py --sizes 1e6 1e7 --ranks 1 4
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "05_mpi_multi_node" / "src"))

from bench_common import write_result  # noqa: E402
from mpi_squares.scaling import mpi_env  # noqa: E402

WRAPPER = """
import io, json, resource, runpy, sys, contextlib
from mpi4py import MPI
buf = io.StringIO()
with contextlib.redirect_stdout(buf):          # the 2025 script prints the whole list
    runpy.run_path(sys.argv[1], run_name="__main__")
rss_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
out = MPI.COMM_WORLD.gather(rss_mb, root=0)
if MPI.COMM_WORLD.Get_rank() == 0:
    print(json.dumps({"peak_rss_mb_per_rank": out, "printed_chars": len(buf.getvalue())}))
"""


def git_show(path: str) -> str:
    sha = subprocess.run(["git", "-C", str(REPO), "log", "--format=%H", "-1", "--fixed-strings",
                          "--grep=Original L6 coursework"], capture_output=True, text=True, check=True).stdout.strip()
    return subprocess.run(["git", "-C", str(REPO), "show", f"{sha}:{path}"], capture_output=True, text=True,
                          check=True).stdout


def main(argv=None) -> dict:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--sizes", nargs="+", type=float, default=[1e6, 1e7])
    ap.add_argument("--ranks", nargs="+", type=int, default=[1, 4])
    args = ap.parse_args(argv)
    src = git_show("05_mpi_multi_node/calculate_squares.py")
    assert "n = 10  # Change this as needed" in src
    rows = []
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "wrap.py").write_text(WRAPPER)
        for n in [int(s) for s in args.sizes]:
            script = Path(d) / f"calculate_squares_2025_n{n}.py"
            script.write_text(src.replace("n = 10  # Change this as needed", f"n = {n}"))
            for ranks in args.ranks:
                t0 = time.perf_counter()
                proc = subprocess.run([shutil.which("mpiexec"), "-n", str(ranks), sys.executable,
                                       str(Path(d) / "wrap.py"), str(script)],
                                      capture_output=True, text=True, env=mpi_env(), timeout=1800)
                wall = time.perf_counter() - t0
                if proc.returncode != 0:
                    rows.append({"n": n, "ranks": ranks, "ok": False, "wall_s": wall,
                                 "error": proc.stderr.strip().splitlines()[-1:] if proc.stderr else []})
                    continue
                info = json.loads(proc.stdout.strip().splitlines()[-1])
                rows.append({"n": n, "ranks": ranks, "ok": True, "wall_s_incl_startup": wall,
                             "peak_rss_mb_rank0": info["peak_rss_mb_per_rank"][0], **info})
                print(rows[-1])
    res = {"what": "2025 calculate_squares.py with only n changed", "rows": rows}
    write_result("legacy_2025_calculate_squares", res, seed=None, subdir="05_mpi_multi_node")
    return res


if __name__ == "__main__":
    main()
