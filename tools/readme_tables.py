"""Markdown tables for the READMEs, rendered only from results/ (used by check_readme_claims.py)."""

from __future__ import annotations


def _ms(r, k="mean_s", sd="sd_s", nd=3):
    return f"{r[k]:.{nd}f} ± {r[sd]:.{nd}f}"


def _table(header: list[str], rows: list[list[str]]) -> str:
    out = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    out += ["| " + " | ".join(r) + " |" for r in rows]
    return "\n".join(out)


def t01(load):
    d = load("01_threads_vs_processes/threads_vs_processes_n10000000.json")
    return _table(["Configuration", "Workers p", f"Median time (s) of {d['repeats']}", "Mean ± sd (s)",
                   "Speedup (medians)", "Efficiency S/p"],
                  [[r["config"], str(r["workers"]), f"{r['median_s']:.2f}", _ms(r, nd=2), f"{r['speedup']:.2f}x",
                    f"{r['efficiency']:.2f}"] for r in d["rows"]])


def t02(load):
    d = load("02_parallel_sum/parallel_sum.json")
    return _table(["n", "Method", "p", f"Median time (s) of {d['repeats']}", "Mean ± sd (s)", "Speedup (medians)",
                   "Efficiency", "Sum correct"],
                  [[f"{r['n']:.0e}", r["method"], str(r["workers"]), f"{r['median_s']:.4f}", _ms(r, nd=4),
                    f"{r['speedup']:.2f}x", f"{r['efficiency']:.2f}", "yes" if r["correct"] else "NO"]
                   for r in d["rows"]])


def t03_pool(load):
    d = load("03_connection_pool/pool_squares.json")
    rows = [[f"{r['n']:.0e}", r["method"], str(r["repeats"]), f"{r['median_s']:.4f}", _ms(r, nd=4),
             f"{r['speedup']:.3f}x"] for r in d["rows"]]
    rows += [[f"{s['n']:.0e}", s["method"], "0", "not run", "-", "-"] for s in d["skipped"]]
    return _table(["n", "Method", "Timed runs", "Median time (s)", "Mean ± sd (s)", "Speedup vs sequential (medians)"],
                  rows)


def t03_semaphore(load):
    d = load("03_connection_pool/connection_pool_run.json")
    return _table(["Processes", "Pool size", "Got a connection", "Max holders at once", "Exit codes", "Total time (s)"],
                  [[str(d["num_processes"]), str(d["pool_size"]), str(d["acquired"]), str(d["max_concurrent_holders"]),
                    ", ".join(map(str, d["exit_codes"])), f"{d['elapsed_s']:.2f}"]])


def t04(load):
    d = load("04_sensor_monitor/sensor_monitor_data.json")
    rows = [[f"Sensor {i}", str(d["rows_consumed"][str(i)]), str(d["missing"].get(str(i), 0)),
             f"{d['averages'][i]:.2f}"] for i in range(d["num_sensors"])]
    head = (f"Run: {d['duration_s']:.0f} s, {d['num_sensors']} sensors, {d['updates']} average updates, "
            f"processor alive: {'yes' if d['processor_alive_before_stop'] else 'NO'}, largest queue "
            f"{d['max_queue_size']}, queue at the end {d['final_queue_size']}.\n\n")
    return head + _table(["Sensor", "Rows replayed", "Missing (-200) skipped", "Average (°C)"], rows)


def _t05(load, name):
    d = load(f"05_mpi_multi_node/{name}.json")
    return _table(["n", "Ranks", f"Median time (s) of {d['repeats']}", "Mean ± sd (s)", "Speedup vs 1 rank (medians)",
                   "Efficiency", "Peak memory rank 0 (MB)"],
                  [[f"{r['n']:.0e}", str(r["ranks"]), f"{r['median_s']:.3f}", _ms(r), f"{r['speedup_vs_1_rank']:.2f}x",
                    f"{r['efficiency']:.2f}", f"{r['peak_rss_mb_rank0_max']:.0f}"] for r in d["rows"]])


def t05_gatherv(load):
    return _t05(load, "mpi_squares_scaling_gatherv")


def t05_reduce(load):
    return _t05(load, "mpi_squares_scaling_reduce_only")


def t06_stage1(load):
    d = load("06_nyc_taxi_pipeline/stage1_download.json")
    return _table(["Threads", f"Median time for 12 files (s) of {d['repeats']}", "Mean ± sd (s)",
                   "Speedup (medians)", "Throughput (MB/s)", "Short transfers retried"],
                  [[str(r["workers"]), f"{r['median_s']:.2f}", _ms(r, nd=2), f"{r['speedup_vs_first']:.2f}x",
                    f"{r['throughput_mb_s']:.0f}", str(r["retried_files"])] for r in d["rows"]])


def t06_stage2(load, name="stage2_cpu"):
    d = load(f"06_nyc_taxi_pipeline/{name}.json")
    return _table(["Method", "Workers", f"Median time (s) of {d['repeats']}", "Mean ± sd (s)", "Speedup (medians)",
                   "Efficiency", "Identical summaries"],
                  [[r["method"], str(r["workers"]), f"{r['median_s']:.2f}", _ms(r, nd=2), f"{r['speedup']:.2f}x",
                    f"{r['efficiency']:.2f}", "yes" if r["identical_to_sequential"] else "NO"] for r in d["rows"]])


def t06_stage2_arrow1(load):
    return t06_stage2(load, "stage2_cpu_arrow_1_thread")


def t06_stage3(load):
    d = load("06_nyc_taxi_pipeline/stage3_mpi.json")
    rows = d["rows"] + ([d["bind_to_none"]] if d.get("bind_to_none") else [])
    binding = {"default": "Open MPI default", "none": "`--bind-to none` (extra run)"}
    return _table(["Ranks", "Binding", f"Median time (s) of {d['repeats']}", "Mean ± sd (s)", "Speedup vs 1 rank",
                   "Speedup vs sequential", "Efficiency", "Wall time incl. start-up (s)", "Identical summaries"],
                  [[str(r["ranks"]), binding[r["binding"]], f"{r['median_s']:.2f}", _ms(r, nd=2),
                    f"{r['speedup_vs_1_rank']:.2f}x", f"{r['speedup_vs_sequential']:.2f}x", f"{r['efficiency']:.2f}",
                    f"{r['wall_incl_startup_mean_s']:.2f}", "yes" if r["identical_to_sequential"] else "NO"]
                   for r in rows])


def t06_manifest(load):
    d = load("06_nyc_taxi_pipeline/manifest.json")
    rows = [[f["file"], f"{f['bytes']:,}", f"{f['rows']:,}", f"`{f['sha256'][:16]}…`"] for f in d["files"]]
    rows.append(["**total**", f"{d['total_bytes']:,}", f"{d['total_rows']:,}", ""])
    return _table(["File", "Bytes", "Rows", "SHA-256 (first 16 hex)"], rows)


def t06_cleaning(load):
    d = load("06_nyc_taxi_pipeline/stage2_cpu.json")["yearly"]
    rows = [[k, f"{v:,}", f"{v / d['rows_raw']:.2%}"] for k, v in d["removed"].items()]
    rows.append(["**kept**", f"{d['rows_clean']:,}", f"{d['rows_clean'] / d['rows_raw']:.2%}"])
    return _table(["Rule (applied in order)", "Trips", "Share of all trips"], rows)


def t06_sql(load):
    a = load("06_nyc_taxi_pipeline/stage4_sql.json")["answers"]
    q1 = a["q1_busiest_hour"][0]
    q4 = a["q4_longest_average_trip_month"][0]
    fares = a["q2_average_fare_by_month"]
    lo = min(fares, key=lambda r: r["avg_fare"])
    hi = max(fares, key=lambda r: r["avg_fare"])
    shares = a["q5_share_cleaned_out"]
    s_lo = min(shares, key=lambda r: r["share_removed"])
    s_hi = max(shares, key=lambda r: r["share_removed"])
    top = ", ".join(f"{r['zone']} ({r['trips']:,})" for r in a["q3_top10_pickup_zones"][:3])
    rows = [
        ["1. Busiest hour of day", f"{q1['hour']}:00 to {q1['hour']}:59, {q1['trips']:,} trips",
         "`q1_busiest_hour.sql`"],
        ["2. Average fare by month", f"lowest {lo['month']} ${lo['avg_fare']:.2f}, highest {hi['month']} "
         f"${hi['avg_fare']:.2f}", "`q2_average_fare_by_month.sql`"],
        ["3. Top 10 pickup zones", f"top 3: {top}", "`q3_top10_pickup_zones.sql`"],
        ["4. Month with the longest average trip", f"{q4['month']}: {q4['avg_distance_mi']:.2f} miles, "
         f"{q4['avg_duration_min']:.1f} minutes", "`q4_longest_average_trip_month.sql`"],
        ["5. Share of trips cleaned out", f"{s_lo['share_removed']:.1%} ({s_lo['month']}) to "
         f"{s_hi['share_removed']:.1%} ({s_hi['month']})", "`q5_share_cleaned_out.sql`"],
    ]
    return _table(["Question", "Answer (TLC data for 2025)", "SQL file"], rows)


def t06_top10(load):
    a = load("06_nyc_taxi_pipeline/stage4_sql.json")["answers"]["q3_top10_pickup_zones"]
    return _table(["#", "Zone", "Borough", "Clean trips"],
                  [[str(i), r["zone"], r["borough"], f"{r['trips']:,}"] for i, r in enumerate(a, 1)])


TABLES = {name: fn for name, fn in globals().items() if name.startswith("t0") and callable(fn)}


def render(name: str, load) -> str:
    if name not in TABLES:
        raise KeyError(f"unknown table {name!r}")
    return TABLES[name](load)
