"""Sequential vs threads vs processes on the Lab 2 workloads.

Every configuration does exactly the same total work as the sequential run: n iterations of the
numbers workload plus n iterations of the letters workload. "2 per function" splits each workload
into two halves, so it uses 4 workers in total.

    python -m threads_vs_processes.benchmark --n 10000000 --repeats 5
"""

from __future__ import annotations

import argparse
import multiprocessing as mp
from concurrent.futures import Executor, ProcessPoolExecutor, ThreadPoolExecutor
from dataclasses import dataclass

from bench_common import efficiency, speedup, time_repeats, write_result
from threads_vs_processes.workloads import run_task

Task = tuple[str, int, int]


@dataclass(frozen=True)
class Config:
    name: str
    kind: str  # "sequential", "threads" or "processes"
    per_function: int  # workers per workload

    @property
    def workers(self) -> int:
        return 1 if self.kind == "sequential" else 2 * self.per_function


CONFIGS = (
    Config("sequential", "sequential", 1),
    Config("threads_1_per_function", "threads", 1),
    Config("processes_1_per_function", "processes", 1),
    Config("threads_2_per_function", "threads", 2),
    Config("processes_2_per_function", "processes", 2),
)


def make_tasks(n: int, per_function: int, seed: int) -> list[Task]:
    """Split each workload into `per_function` chunks; chunk sizes add up to exactly n."""
    tasks = []
    for w_idx, name in enumerate(("numbers", "letters")):
        base, extra = divmod(n, per_function)
        for c in range(per_function):
            size = base + (1 if c < extra else 0)
            tasks.append((name, size, seed + 1000 * w_idx + c))
    return tasks


def combine(tasks: list[Task], outputs: list[int | str]) -> tuple[int, str]:
    total = sum(o for t, o in zip(tasks, outputs, strict=True) if t[0] == "numbers")
    letters = "".join(o for t, o in zip(tasks, outputs, strict=True) if t[0] == "letters")
    return total, letters


def run_sequential(tasks: list[Task]) -> tuple[int, str]:
    return combine(tasks, [run_task(t) for t in tasks])


def _run_with(executor: Executor, tasks: list[Task]) -> tuple[int, str]:
    with executor as ex:
        return combine(tasks, list(ex.map(run_task, tasks)))


def run_config(cfg: Config, tasks: list[Task], start_method: str | None = None) -> tuple[int, str]:
    if cfg.kind == "sequential":
        return run_sequential(tasks)
    if cfg.kind == "threads":
        return _run_with(ThreadPoolExecutor(max_workers=cfg.workers), tasks)
    ctx = mp.get_context(start_method)
    return _run_with(ProcessPoolExecutor(max_workers=cfg.workers, mp_context=ctx), tasks)


def benchmark(n: int, repeats: int, seed: int, start_method: str | None = None) -> dict:
    rows = []
    expected: dict[int, tuple[int, str]] = {}
    t_seq = None
    for cfg in CONFIGS:
        tasks = make_tasks(n, cfg.per_function, seed)
        def run(cfg=cfg, tasks=tasks):
            return run_config(cfg, tasks, start_method)

        stats, result = time_repeats(run, repeats)
        if cfg.per_function not in expected:
            # same task list, run sequentially (untimed when it is not the baseline itself)
            expected[cfg.per_function] = result if cfg.kind == "sequential" else run_sequential(tasks)
        if result != expected[cfg.per_function]:
            raise AssertionError(f"{cfg.name} returned a different result from the sequential run")
        if cfg.kind == "sequential":
            t_seq = stats.mean
        assert t_seq is not None
        s = speedup(t_seq, stats.mean)
        rows.append({
            "config": cfg.name,
            "workers": cfg.workers,
            "mean_s": stats.mean,
            "sd_s": stats.sd,
            "runs_s": list(stats.runs),
            "speedup": s,
            "efficiency": efficiency(t_seq, stats.mean, cfg.workers),
            "result_matches_sequential": True,
        })
    return {"n": n, "repeats": repeats, "start_method": start_method or mp.get_start_method(), "rows": rows}


def format_table(res: dict) -> str:
    lines = ["| Config | Workers p | Mean (s) | SD (s) | Speedup | Efficiency |", "|---|---|---|---|---|---|"]
    for r in res["rows"]:
        lines.append(f"| {r['config']} | {r['workers']} | {r['mean_s']:.3f} | {r['sd_s']:.3f} "
                     f"| {r['speedup']:.2f} | {r['efficiency']:.2f} |")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> dict:
    ap = argparse.ArgumentParser(description="Threads vs processes on CPU-bound pure-Python work")
    ap.add_argument("--n", type=int, default=10_000_000, help="iterations per workload (2025 lab: 1e7)")
    ap.add_argument("--repeats", type=int, default=5)
    ap.add_argument("--seed", type=int, default=2025)
    ap.add_argument("--start-method", choices=["fork", "spawn", "forkserver"], default=None)
    ap.add_argument("--no-save", action="store_true")
    args = ap.parse_args(argv)
    res = benchmark(args.n, args.repeats, args.seed, args.start_method)
    print(format_table(res))
    if not args.no_save:
        path = write_result(f"threads_vs_processes_n{args.n}", res, seed=args.seed,
                            subdir="01_threads_vs_processes")
        print(f"saved {path.name}")
    return res


if __name__ == "__main__":
    main()
