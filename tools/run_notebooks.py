"""Execute every notebook in the repo headless (T13); outputs are not written back.

    python tools/run_notebooks.py              # lab size (N = 1e7 in the Lab 2 notebook)
    PCB_NOTEBOOK_N=200000 python tools/run_notebooks.py   # quick run (CI)
"""

import sys
import time
from pathlib import Path

import nbformat
from nbclient import NotebookClient

REPO = Path(__file__).resolve().parents[1]


def main() -> int:
    notebooks = sorted(p for p in REPO.rglob("*.ipynb") if ".ipynb_checkpoints" not in p.parts)
    for nb_path in notebooks:
        nb = nbformat.read(nb_path, as_version=4)
        t0 = time.perf_counter()
        client = NotebookClient(nb, timeout=900, kernel_name="python3",
                                resources={"metadata": {"path": str(nb_path.parent)}})
        client.execute()
        print(f"OK {nb_path.relative_to(REPO)} executed in {time.perf_counter() - t0:.1f} s")
        for cell in nb.cells:
            for out in cell.get("outputs", []):
                text = out.get("text", "")
                if "It took" in text or "speedup" in text or "efficiency" in text:
                    print("   ", text.strip().splitlines()[-1])
    print(f"{len(notebooks)} notebook(s) executed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
