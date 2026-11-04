from datetime import date

from backtestceo.momentum.gappers import SymDay
from backtestceo.momentum.premarket import BASE, PMF, pm_fade, pm_fade_signal, portfolio, simulate

D = date(2026, 10, 1)


def sd(spec, pc=5.0):
    rows = [{"t": f"2026-10-01T{int(hm[:2]) + 4:02d}:{hm[3:]}:00Z", "o": o, "h": h, "l": l, "c": c, "v": v}
            for hm, o, h, l, c, v in spec]
    return SymDay.build(D, {"sym": "T", "pc": pc, "adv": 1_000_000, "atr": 0.5}, rows)


PRE = [("07:00", 6.0, 6.2, 5.9, 6.1, 50_000), ("07:01", 6.1, 6.6, 6.1, 6.6, 80_000),   # +32% close at 07:01
       ("07:02", 6.6, 6.7, 6.4, 6.5, 60_000), ("07:03", 6.5, 6.55, 6.45, 6.5, 40_000)]


def test_pm_fade_signal_and_trade():
    x = sd(PRE + [("09:30", 6.0, 6.1, 5.8, 5.9, 100_000), ("15:55", 5.0, 5.1, 4.9, 5.0, 50_000)])
    k = pm_fade_signal(x, PMF)
    assert x.m[k] == 7 * 60 + 2  # next bar after the +30% close
    tr = pm_fade([D], [x], PMF)
    assert len(tr) == 1 and tr[0]["why"] == "cover" and tr[0]["pnl"] > 0


def test_pm_fade_stop():
    x = sd(PRE + [("08:00", 7.0, 10.5, 7.0, 10.0, 50_000), ("09:30", 10, 10, 9, 9, 1), ("15:55", 9, 9, 9, 9, 1)])
    t = pm_fade([D], [x], PMF)[0]
    assert t["why"] == "stop" and t["pnl"] < 0


def test_premarket_long_hod_break_sizes_on_initial_stop():
    x = sd(PRE + [("07:04", 6.5, 6.8, 6.5, 6.75, 90_000), ("07:05", 6.8, 7.4, 6.8, 7.3, 90_000),
                  ("09:29", 7.3, 7.4, 7.2, 7.3, 10_000), ("09:30", 7.3, 7.4, 7.2, 7.3, 10_000)])
    P = {**BASE, "kind": "hod", "gap": 20.0, "vol": 0.05, "tgt": 0, "trail": True}
    t = simulate(x, P)
    assert t and t[2] > t[3]  # entry above the reported (initial) stop
    tr = portfolio([x], P)
    assert tr and 1 <= tr[0]["shares"] <= int(100 / (tr[0]["fill"] - tr[0]["stop"]))  # $100 risk to the initial stop
