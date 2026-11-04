from datetime import date

from backtestceo.momentum.gappers import BASE, SymDay, portfolio, simulate


def rows(spec):
    """spec: list of (hh:mm, o, h, l, c, v) -> Alpaca-style rows (ET = UTC-4 in October)."""
    out = []
    for hm, o, h, l, c, v in spec:
        hh, mm = map(int, hm.split(":"))
        out.append({"t": f"2026-10-01T{hh + 4:02d}:{mm:02d}:00Z", "o": o, "h": h, "l": l, "c": c, "v": v})
    return out


def day(after):
    spec = [("09:00", 5.6, 5.8, 5.5, 5.7, 50_000)]
    spec += [(f"09:3{k}", 5.7 + k * 0.02, 5.75 + k * 0.02, 5.68 + k * 0.02, 5.73 + k * 0.02, 60_000) for k in range(5)]
    spec += after
    return SymDay.build(date(2026, 10, 1), {"sym": "T", "pc": 5.0, "adv": 300_000, "atr": 0.4}, rows(spec))


def test_orb_breakout_to_eod():
    sd = day([("09:35", 5.81, 5.95, 5.80, 5.93, 80_000), ("10:00", 5.93, 6.3, 5.9, 6.25, 50_000),
              ("15:55", 6.4, 6.45, 6.35, 6.4, 50_000)])
    t = simulate(sd, {**BASE, "rvol": 1.0})
    assert t and t[0] == 575 and t[5] == "eod" and t[4] > t[2]
    assert t[3] == round(5.68 - 0.01, 2)  # range low stop


def test_orb_stop_and_filters():
    sd = day([("09:35", 5.81, 5.84, 5.60, 5.62, 80_000), ("09:36", 5.6, 5.7, 5.5, 5.55, 50_000)])
    t = simulate(sd, {**BASE, "rvol": 1.0})
    assert t[5] == "stop" and t[4] < t[3]
    assert simulate(sd, {**BASE, "rvol": 1.0, "gap": 30.0}) is None  # gap at open is +14%
    assert simulate(sd, {**BASE, "rvol": 50.0}) is None


def test_portfolio_sizes_by_risk():
    sd = day([("09:35", 5.81, 5.95, 5.80, 5.93, 80_000), ("15:55", 6.4, 6.45, 6.35, 6.4, 50_000)])
    tr = portfolio([sd], {**BASE, "rvol": 1.0})
    assert len(tr) == 1 and tr[0]["shares"] == int(100 / (tr[0]["entry"] - tr[0]["stop"]))
