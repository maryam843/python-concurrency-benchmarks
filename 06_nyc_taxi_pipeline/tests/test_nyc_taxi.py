import functools
import http.server
import importlib.util
import json
import shutil
import threading
from pathlib import Path

import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from nyc_taxi import download, stage1_io, stage2_cpu, stage3_mpi, stage4_sql
from nyc_taxi.cleaning import RULES, clean
from nyc_taxi.config import file_name, month_from_path, url
from nyc_taxi.summaries import combine, summarise_frame, summarise_month, summary_key

REPO = Path(__file__).resolve().parents[2]
FIX = REPO / "tests" / "fixtures" / "taxi"
MONTHS = ["2025-01", "2025-02", "2025-03"]
PATHS = [FIX / file_name(m) for m in MONTHS]
HAVE_MPI = shutil.which("mpiexec") is not None and importlib.util.find_spec("mpi4py") is not None


def independent_clean(df: pd.DataFrame, month: str) -> pd.DataFrame:
    """The cleaning rules re-written independently with df.query, used as the reference answer."""
    start = pd.Timestamp(month + "-01")
    end = start + pd.DateOffset(months=1)  # noqa: F841 (used inside the query string)
    d = df.assign(dur=(df.tpep_dropoff_datetime - df.tpep_pickup_datetime).dt.total_seconds())
    q = ("tpep_pickup_datetime >= @start and tpep_pickup_datetime < @end and dur >= 60 and dur <= 21600 "
         "and trip_distance > 0 and trip_distance <= 100 and fare_amount > 0 and fare_amount <= 500 "
         "and (passenger_count != passenger_count or (passenger_count >= 1 and passenger_count <= 6)) "
         "and PULocationID >= 1 and PULocationID <= 263")
    return d.query(q)


@pytest.fixture(scope="module")
def reference():
    frames = []
    for m, p in zip(MONTHS, PATHS, strict=True):
        raw = pd.read_parquet(p)
        good = independent_clean(raw, m)
        frames.append(good.assign(month=m, rows_raw=len(raw)))
    return pd.concat(frames), {m: len(pd.read_parquet(p)) for m, p in zip(MONTHS, PATHS, strict=True)}


# ---------- T1 unit: cleaning rules ----------
def _frame(**overrides):
    base = {"tpep_pickup_datetime": pd.Timestamp("2025-01-10 08:00"), "tpep_dropoff_datetime": pd.Timestamp(
        "2025-01-10 08:20"), "passenger_count": 1.0, "trip_distance": 3.0, "fare_amount": 15.0, "PULocationID": 161}
    base.update(overrides)
    return pd.DataFrame([base])


@pytest.mark.parametrize("override,rule", [
    ({"tpep_pickup_datetime": pd.Timestamp("2024-12-31 23:50")}, "pickup_outside_month"),
    ({"tpep_dropoff_datetime": pd.Timestamp("2025-01-10 07:00")}, "bad_duration"),
    ({"tpep_dropoff_datetime": pd.Timestamp("2025-01-10 08:00:30")}, "bad_duration"),
    ({"tpep_dropoff_datetime": pd.Timestamp("2025-01-10 15:00")}, "bad_duration"),
    ({"trip_distance": 0.0}, "bad_distance"),
    ({"trip_distance": float("nan")}, "bad_distance"),
    ({"trip_distance": 250.0}, "bad_distance"),
    ({"fare_amount": -5.0}, "bad_fare"),
    ({"fare_amount": 900.0}, "bad_fare"),
    ({"passenger_count": 0.0}, "bad_passenger_count"),
    ({"passenger_count": 7.0}, "bad_passenger_count"),
    ({"PULocationID": 264}, "unknown_pickup_zone"),
    ({"PULocationID": 265}, "unknown_pickup_zone"),
])
def test_each_rule_removes_its_row(override, rule):
    good, removed = clean(_frame(**override), "2025-01")
    assert len(good) == 0
    assert removed[rule] == 1 and sum(removed.values()) == 1


def test_valid_row_and_missing_passenger_count_are_kept():
    for df in (_frame(), _frame(passenger_count=float("nan"))):
        good, removed = clean(df, "2025-01")
        assert len(good) == 1 and sum(removed.values()) == 0


def test_row_failing_two_rules_is_counted_once_under_the_first():
    good, removed = clean(_frame(fare_amount=-1.0, PULocationID=265), "2025-01")
    assert removed["bad_fare"] == 1 and removed["unknown_pickup_zone"] == 0


def test_month_from_path_and_url():
    assert month_from_path("/x/yellow_tripdata_2025-07.parquet") == "2025-07"
    assert url("2025-07").endswith("/trip-data/yellow_tripdata_2025-07.parquet")


# ---------- T3 property tests ----------
row = st.fixed_dictionaries({
    "minute": st.integers(-60 * 24 * 3, 60 * 24 * 34), "dur_s": st.integers(-600, 30000),
    "passenger_count": st.one_of(st.none(), st.integers(0, 9)), "trip_distance": st.floats(-5, 300),
    "fare_amount": st.floats(-100, 1000), "PULocationID": st.integers(1, 265)})


@settings(max_examples=60, deadline=None)
@given(rows=st.lists(row, min_size=1, max_size=40))
def test_cleaning_accounts_for_every_row_and_matches_independent_rules(rows):
    t0 = pd.Timestamp("2025-01-01")
    df = pd.DataFrame({
        "tpep_pickup_datetime": [t0 + pd.Timedelta(minutes=r["minute"]) for r in rows],
        "tpep_dropoff_datetime": [t0 + pd.Timedelta(minutes=r["minute"], seconds=r["dur_s"]) for r in rows],
        "passenger_count": pd.array([r["passenger_count"] for r in rows], dtype="Int64").astype("float64"),
        "trip_distance": [r["trip_distance"] for r in rows],
        "fare_amount": [r["fare_amount"] for r in rows],
        "PULocationID": [r["PULocationID"] for r in rows]})
    good, removed = clean(df, "2025-01")
    assert len(good) + sum(removed.values()) == len(df)
    assert list(good.index) == list(independent_clean(df, "2025-01").index)


@settings(max_examples=20, deadline=None)
@given(order=st.permutations(range(3)))
def test_combine_does_not_depend_on_month_order(order):
    months = [summarise_month(p) for p in PATHS]
    assert combine([months[i] for i in order]) == combine(months)


# ---------- summaries vs an independent pandas calculation ----------
def test_yearly_summary_matches_pandas(reference):
    ref, raw_counts = reference
    y = combine([summarise_month(p) for p in PATHS])
    assert y["rows_raw"] == sum(raw_counts.values())
    assert y["rows_clean"] == len(ref)
    assert y["mean_fare"] == pytest.approx(ref.fare_amount.mean())
    assert y["mean_distance_mi"] == pytest.approx(ref.trip_distance.mean())
    assert y["mean_duration_min"] == pytest.approx((ref.dur / 60).mean())
    assert y["hourly"] == ref.tpep_pickup_datetime.dt.hour.value_counts().reindex(range(24), fill_value=0).tolist()
    top = ref.PULocationID.value_counts()
    top = sorted(top.items(), key=lambda kv: (-kv[1], kv[0]))[:10]
    assert [(d["zone_id"], d["trips"]) for d in y["top10_pickup_zones"]] == [(int(a), int(b)) for a, b in top]
    assert set(y["removed"]) == set(RULES)
    raw = pd.concat([pd.read_parquet(p) for p in PATHS])
    assert y["passenger_count_missing_raw"] == raw.passenger_count.isna().sum() > 0


def test_empty_month_summary():
    df = pd.read_parquet(PATHS[0]).iloc[:0]
    s = summarise_frame(df, "2025-01")
    assert s["rows_raw"] == 0 and s["hourly"] == [0] * 24
    assert combine([s])["mean_fare"] == 0.0


# ---------- T4 integration: stage 2 ----------
@pytest.mark.parametrize("start_method", [None, "spawn"])
def test_stage2_all_methods_identical(start_method):
    res = stage2_cpu.run(PATHS, [1, 2], repeats=1, start_method=start_method)
    assert [(r["method"], r["workers"]) for r in res["rows"]] == [
        ("sequential", 1), ("threads", 1), ("threads", 2), ("processes", 1), ("processes", 2)]
    assert all(r["identical_to_sequential"] for r in res["rows"])
    assert res["yearly"]["rows_raw"] == 1002


def test_stage2_main_and_bad_method(tmp_path, monkeypatch):
    monkeypatch.setattr(stage2_cpu, "write_result", lambda *a, **k: None)
    res = stage2_cpu.main(["--data-dir", str(FIX), "--months", *MONTHS, "--workers", "2", "--repeats", "1"])
    assert len(res["month_summaries"]) == 3
    with pytest.raises(ValueError):
        stage2_cpu.run_method("gpu", PATHS)


def test_stage2_detects_different_summaries(monkeypatch):
    real = stage2_cpu.run_method

    def broken(method, paths, workers=1, start_method=None):
        out = real(method, paths, workers, start_method)
        if method == "threads":
            out[0] = {**out[0], "fare_sum": out[0]["fare_sum"] + 1}
        return out

    monkeypatch.setattr(stage2_cpu, "run_method", broken)
    with pytest.raises(AssertionError, match="different summaries"):
        stage2_cpu.run(PATHS, [1], repeats=1)


# ---------- T4 integration: stage 1 against a local HTTP server ----------
@pytest.fixture
def local_server():
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(FIX))
    handler.log_message = lambda *a, **k: None
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def test_stage1_downloads_sequential_and_threads_identical(local_server, tmp_path):
    def url_for(m):
        return f"{local_server}/{file_name(m)}"

    res = stage1_io.run(MONTHS, [1, 4], repeats=2, url_for=url_for, tmp_root=tmp_path)
    assert res["mode"] == "download"
    assert [r["workers"] for r in res["rows"]] == [1, 4]
    assert res["rows"][0]["bytes"] == sum(p.stat().st_size for p in PATHS)
    assert list(tmp_path.iterdir()) == []  # every run's temp folder was deleted


def test_short_transfer_is_detected_and_retried(tmp_path):
    body = PATHS[0].read_bytes()
    calls = []

    class Flaky(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            calls.append(1)
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body if len(calls) > 1 else body[:1000])  # first answer ends early
            self.close_connection = True

        def log_message(self, *a):
            pass

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Flaky)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        info = download.download_file(f"http://127.0.0.1:{srv.server_address[1]}/x", tmp_path / "x.parquet")
        assert info["attempts"] == 2 and info["bytes"] == len(body)
        assert info["sha256"] == download.sha256_file(PATHS[0])
        calls.clear()
        with pytest.raises(download.IncompleteDownload):
            download.download_file(f"http://127.0.0.1:{srv.server_address[1]}/x", tmp_path / "y", attempts=1)
    finally:
        srv.shutdown()


def test_stage1_from_disk():
    res = stage1_io.run(MONTHS, [1, 2], repeats=1, from_disk=True, data_dir=FIX)
    assert res["mode"] == "read_from_disk" and res["rows"][1]["rows"] == 1002


def test_download_main_and_manifest(local_server, tmp_path, monkeypatch):
    monkeypatch.setattr(download, "url", lambda m: f"{local_server}/{file_name(m)}")
    monkeypatch.setattr(download, "ZONE_LOOKUP_URL", f"{local_server}/taxi_zone_lookup.csv")
    rows = download.main(["--months", *MONTHS, "--dest", str(tmp_path), "--workers", "2", "--no-save"])
    assert [r["rows"] for r in rows] == [340, 322, 340]
    assert rows[0]["sha256"] == download.sha256_file(PATHS[0])
    assert (tmp_path / "taxi_zone_lookup.csv").exists()


def test_stage1_main_from_disk(monkeypatch):
    monkeypatch.setattr(stage1_io, "write_result", lambda *a, **k: None)
    res = stage1_io.main(["--months", *MONTHS, "--from-disk", "--data-dir", str(FIX), "--workers", "1", "2",
                          "--repeats", "1"])
    assert len(res["rows"]) == 2


# ---------- T4 integration: stage 4 SQL vs pandas ----------
def test_sql_answers_match_pandas(reference, tmp_path):
    ref, raw_counts = reference
    months = [summarise_month(p) for p in PATHS]
    con = stage4_sql.build_db(months, FIX / "taxi_zone_lookup.csv", tmp_path / "t.sqlite")
    a = stage4_sql.run_queries(con)
    hourly = ref.tpep_pickup_datetime.dt.hour.value_counts()
    best = sorted(hourly.items(), key=lambda kv: (-kv[1], kv[0]))[0]
    assert a["q1_busiest_hour"] == [{"hour": best[0], "trips": best[1]}]
    fares = ref.groupby("month").fare_amount.mean()
    assert [r["month"] for r in a["q2_average_fare_by_month"]] == MONTHS
    for r in a["q2_average_fare_by_month"]:
        assert r["avg_fare"] == pytest.approx(fares[r["month"]])
    zones = sorted(ref.PULocationID.value_counts().items(), key=lambda kv: (-kv[1], kv[0]))[:10]
    assert [(r["zone_id"], r["trips"]) for r in a["q3_top10_pickup_zones"]] == [(int(z), int(c)) for z, c in zones]
    assert a["q3_top10_pickup_zones"][0]["zone"].startswith("Synthetic zone")
    dist = ref.groupby("month").trip_distance.mean()
    assert a["q4_longest_average_trip_month"][0]["month"] == dist.idxmax()
    assert a["q4_longest_average_trip_month"][0]["avg_distance_mi"] == pytest.approx(dist.max())
    clean_counts = ref.groupby("month").size()
    for r in a["q5_share_cleaned_out"]:
        m = r["month"]
        assert r["share_removed"] == pytest.approx(1 - clean_counts[m] / raw_counts[m])


def test_stage4_main(tmp_path, monkeypatch):
    summaries = tmp_path / "stage2.json"
    summaries.write_text(json.dumps({"month_summaries": [summarise_month(p) for p in PATHS]}))
    monkeypatch.setattr(stage4_sql, "write_result", lambda *a, **k: None)
    answers = stage4_sql.main(["--summaries", str(summaries), "--zones", str(FIX / "taxi_zone_lookup.csv"),
                               "--db", str(tmp_path / "db.sqlite")])
    assert set(answers) == {"q1_busiest_hour", "q2_average_fare_by_month", "q3_top10_pickup_zones",
                            "q4_longest_average_trip_month", "q5_share_cleaned_out"}


# ---------- T4 integration: stage 3 MPI ----------
def test_round_robin_share():
    items = list(range(12))
    parts = [stage3_mpi.my_share(items, r, 4) for r in range(4)]
    assert parts[1] == [1, 5, 9] and sorted(x for p in parts for x in p) == items


@pytest.mark.mpi
@pytest.mark.skipif(not HAVE_MPI, reason="MPI runtime or mpi4py not installed (MPI tests run on Linux CI)")
def test_stage3_mpi_identical_to_sequential(monkeypatch):
    monkeypatch.setattr(stage3_mpi, "write_result", lambda *a, **k: None)
    res = stage3_mpi.main(["--months", *MONTHS, "--data-dir", str(FIX), "--ranks", "1", "2", "4",
                           "--repeats", "1"])
    assert [r["ranks"] for r in res["rows"]] == [1, 2, 4]
    assert all(r["identical_to_sequential"] for r in res["rows"])
    assert res["yearly"] == combine([summarise_month(p) for p in PATHS])
    assert summary_key([summarise_month(p) for p in PATHS])[0]["month"] == "2025-01"


def test_stage3_requires_mpiexec(monkeypatch):
    monkeypatch.setattr(stage3_mpi.shutil, "which", lambda name: None)
    with pytest.raises(RuntimeError, match="mpiexec not found"):
        stage3_mpi.run_job(1, MONTHS, FIX)


def test_real_urls_are_blocked_in_tests(tmp_path):
    with pytest.raises(RuntimeError, match="use a local fixture"):
        download.download_months(["2025-01"], tmp_path, 1)


# ---------- T8 reproducibility ----------
def test_summaries_are_reproducible():
    assert summary_key([summarise_month(p) for p in PATHS]) == summary_key([summarise_month(p) for p in PATHS])
