"""Draw the README figures (SVG) from the JSON files in results/. Missing results are skipped.

    python tools/make_figures.py
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
RES = REPO / "results"
OUT = REPO / "figures"

SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a"]  # validated categorical slots 1-3 (light)
IDEAL = "#9a9994"

plt.rcParams.update({
    "svg.hashsalt": "pcb", "svg.fonttype": "none", "font.size": 10, "font.family": "DejaVu Sans",
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "axes.edgecolor": GRID, "axes.labelcolor": INK2,
    "xtick.color": INK2, "ytick.color": INK2, "text.color": INK, "axes.grid": True, "grid.color": GRID,
    "grid.linewidth": 0.8, "axes.spines.top": False, "axes.spines.right": False, "legend.frameon": False,
})


def _load(rel: str) -> dict | None:
    p = RES / rel
    return json.loads(p.read_text()) if p.exists() else None


def _save(fig, name: str) -> Path:
    OUT.mkdir(exist_ok=True)
    path = OUT / name
    fig.savefig(path, format="svg", metadata={"Date": None}, bbox_inches="tight")
    plt.close(fig)
    print("wrote", path.relative_to(REPO))
    return path


def _line(ax, xs, ys, i, label, dy=0):
    ax.plot(xs, ys, color=SERIES[i], lw=2, marker="o", ms=8, mec=SURFACE, mew=2, label=label, zorder=3)
    ax.annotate(label, (xs[-1], ys[-1]), xytext=(8, dy), textcoords="offset points", va="center",
                color=INK2, fontsize=9)
    ax.set_xlim(right=xs[-1] * 1.35)  # room for the end label


def _ideal(ax, xs):
    ax.plot(xs, [x / xs[0] for x in xs], color=IDEAL, lw=1.2, ls="--", label="ideal (linear)", zorder=1)


def fig_taxi_speedup() -> Path | None:
    s1, s2, s3 = (_load(f"06_nyc_taxi_pipeline/{n}.json") for n in ("stage1_download", "stage2_cpu", "stage3_mpi"))
    if not (s1 and s2 and s3):
        return None
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.6), sharey=True)
    ax = axes[0]
    xs = [r["workers"] for r in s1["rows"]]
    _ideal(ax, xs)
    _line(ax, xs, [r["speedup_vs_first"] for r in s1["rows"]], 0, "threads")
    ax.set_title("Stage 1: download 12 files (I/O)", loc="left", fontsize=10)
    ax.set_xlabel("threads")
    ax.set_ylabel("speedup vs sequential")
    ax = axes[1]
    ends = {}
    for method in ("threads", "processes"):
        ends[method] = [r["speedup"] for r in s2["rows"] if r["method"] == method][-1]
    for i, method in enumerate(("threads", "processes")):
        rows = [r for r in s2["rows"] if r["method"] == method]
        xs = [r["workers"] for r in rows]
        if i == 0:
            _ideal(ax, xs)
        other = ends["processes" if method == "threads" else "threads"]
        dy = 0 if abs(ends[method] - other) > 0.4 else (7 if ends[method] >= other else -7)
        _line(ax, xs, [r["speedup"] for r in rows], i, method, dy)
    ax.set_title("Stage 2: clean + summarise (CPU)", loc="left", fontsize=10)
    ax.set_xlabel("workers")
    ax = axes[2]
    xs = [r["ranks"] for r in s3["rows"]]
    _ideal(ax, xs)
    _line(ax, xs, [r["speedup_vs_1_rank"] for r in s3["rows"]], 2, "MPI ranks")
    ax.set_title("Stage 3: MPI, months per rank", loc="left", fontsize=10)
    ax.set_xlabel("ranks")
    for a in axes:
        a.set_xticks(sorted({1, 2, 4, 8} & set(a.get_xticks().astype(int)) | set(xs)))
        a.set_ylim(bottom=0)
    handles, labels = [], []
    for a in axes:
        for h, lab in zip(*a.get_legend_handles_labels(), strict=True):
            if lab not in labels:
                handles.append(h)
                labels.append(lab)
    fig.legend(handles, labels, loc="upper center", ncol=len(labels), bbox_to_anchor=(0.5, 1.06))
    return _save(fig, "06_speedup_by_stage.svg")


def fig_trips_by_hour() -> Path | None:
    s2 = _load("06_nyc_taxi_pipeline/stage2_cpu.json")
    if not s2:
        return None
    hourly = s2["yearly"]["hourly"]
    fig, ax = plt.subplots(figsize=(8, 3.2))
    ax.bar(range(24), [h / 1e6 for h in hourly], color=SERIES[0], width=0.8, edgecolor=SURFACE, linewidth=2)
    best = s2["yearly"]["busiest_hour"]
    ax.annotate(f"busiest: {best}:00 ({hourly[best] / 1e6:.2f} M)", (best, hourly[best] / 1e6),
                xytext=(0, 6), textcoords="offset points", ha="center", color=INK2, fontsize=9)
    ax.set_xticks(range(0, 24, 2))
    ax.set_xlabel("pickup hour of day")
    ax.set_ylabel("clean trips (millions)")
    ax.set_title(f"NYC yellow taxi trips by pickup hour, {s2['yearly']['months'][0][:4]}", loc="left", fontsize=10)
    ax.grid(axis="x", visible=False)
    return _save(fig, "06_trips_by_hour.svg")


def fig_speedup_bars(rel: str, name: str, title: str, pick) -> Path | None:
    doc = _load(rel)
    if not doc:
        return None
    rows = pick(doc)
    fig, ax = plt.subplots(figsize=(8, 0.45 * len(rows) + 1.2))
    labels = [r[0] for r in rows][::-1]
    vals = [r[1] for r in rows][::-1]
    ax.barh(labels, vals, color=SERIES[0], height=0.6, edgecolor=SURFACE, linewidth=2)
    ax.axvline(1.0, color=IDEAL, lw=1.2, ls="--")
    for y, v in enumerate(vals):
        ax.annotate(f"{v:.2f}x", (v, y), xytext=(4, 0), textcoords="offset points", va="center",
                    color=INK2, fontsize=9)
    ax.set_xlabel("speedup vs sequential (dashed line = no gain)")
    ax.set_title(title, loc="left", fontsize=10)
    ax.grid(axis="y", visible=False)
    ax.set_xlim(0, max(vals) * 1.2)
    return _save(fig, name)


def fig_mpi_scaling() -> Path | None:
    doc = _load("05_mpi_multi_node/mpi_squares_scaling_gatherv.json")
    if not doc:
        return None
    fig, ax = plt.subplots(figsize=(5.5, 3.4))
    sizes = sorted({r["n"] for r in doc["rows"]})
    for i, n in enumerate(sizes):
        rows = [r for r in doc["rows"] if r["n"] == n]
        xs = [r["ranks"] for r in rows]
        if i == 0:
            _ideal(ax, xs)
        _line(ax, xs, [r["speedup_vs_1_rank"] for r in rows], i, f"n = {n:.0e}")
    ax.set_xticks(xs)
    ax.set_ylim(bottom=0)
    ax.set_xlabel("MPI ranks (one machine)")
    ax.set_ylabel("speedup vs 1 rank")
    ax.set_title("Squares with NumPy + Gatherv", loc="left", fontsize=10)
    ax.legend(loc="upper left")
    return _save(fig, "05_mpi_scaling.svg")


def main() -> list[Path]:
    made = [
        fig_taxi_speedup(),
        fig_trips_by_hour(),
        fig_speedup_bars("01_threads_vs_processes/threads_vs_processes_n10000000.json", "01_threads_vs_processes.svg",
                         "Lab 2 workloads, n = 1e7 (mean of 5 runs)",
                         lambda d: [(f"{r['config']} (p={r['workers']})", r["speedup"]) for r in d["rows"]]),
        fig_speedup_bars("02_parallel_sum/parallel_sum.json", "02_parallel_sum_1e8.svg",
                         "Sum of 1..n, n = 1e8 (mean of 3 runs)",
                         lambda d: [(f"{r['method']} (p={r['workers']})", r["speedup"])
                                    for r in d["rows"] if r["n"] == max(d["sizes"])]),
        fig_mpi_scaling(),
    ]
    return [m for m in made if m]


if __name__ == "__main__":
    main()
