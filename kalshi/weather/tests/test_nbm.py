from datetime import date, datetime, timezone

from weather import nbm


def t(s):
    return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)


ROWS = [
    {"runtime": t("2026-10-14 12:00"), "ftime": t("2026-10-16 00:00"), "txn": 63.0, "xnd": 2.0},
    {"runtime": t("2026-10-15 06:00"), "ftime": t("2026-10-16 00:00"), "txn": 64.0, "xnd": 2.0},
    {"runtime": t("2026-10-15 12:00"), "ftime": t("2026-10-16 00:00"), "txn": 65.0, "xnd": 1.0},
    {"runtime": t("2026-10-15 18:00"), "ftime": t("2026-10-16 00:00"), "txn": 66.0, "xnd": 1.0},
    {"runtime": t("2026-10-15 12:00"), "ftime": t("2026-10-15 12:00"), "txn": 50.0, "xnd": 2.0},  # issued after start
    {"runtime": t("2026-10-15 00:00"), "ftime": t("2026-10-15 12:00"), "txn": 52.0, "xnd": 2.0},
]


def test_high_uses_latest_run_published_before_decision():
    # decision 20:00Z on the 15th: the 18Z run is not out yet (2h lag), 12Z is
    assert nbm.extreme(ROWS, date(2026, 10, 15), "high", before=t("2026-10-15 20:00")) == (65.0, 1.0, t("2026-10-15 12:00"))
    assert nbm.extreme(ROWS, date(2026, 10, 15), "high", before=t("2026-10-15 21:00"))[0] == 66.0
    assert nbm.extreme(ROWS, date(2026, 10, 15), "high")[0] == 66.0


def test_low_targets_12z_and_ignores_runs_after_period_start():
    assert nbm.extreme(ROWS, date(2026, 10, 15), "low") == (52.0, 2.0, t("2026-10-15 00:00"))


def test_fit_and_sigma():
    errs = [(1.0, 2.0), (-1.0, 2.0)] * 15
    f = nbm.fit(errs)
    assert f["n"] == 30 and abs(f["bias"]) < 1e-9 and f["sd"] >= 1.0 and 0.4 < f["k"] < 0.6
    assert nbm.sigma(f, 4.0, "scaled") == max(1.0, f["k"] * 4)
    assert nbm.sigma(f, 4.0, "const") == f["sd"]
    assert nbm.fit(errs[:5]) is None
