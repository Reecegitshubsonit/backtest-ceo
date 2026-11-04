from datetime import date, datetime

from backtestceo.momentum.data import ET
from backtestceo.momentum.fade import FadeConfig, FadeTrader, backtest, stats
from backtestceo.momentum.gappers import SymDay

D = date(2026, 10, 1)


def sd(after, pc=5.0, sym="T"):
    spec = [("09:00", 7.0, 7.2, 6.9, 7.1, 200_000)]
    spec += [(f"09:3{k}", 7.5 - k * 0.05, 7.6 - k * 0.05, 7.3 - k * 0.05, 7.4 - k * 0.05, 300_000) for k in range(5)]
    spec += after
    rows = [{"t": f"2026-10-01T{int(hm[:2]) + 4:02d}:{hm[3:]}:00Z", "o": o, "h": h, "l": l, "c": c, "v": v}
            for hm, o, h, l, c, v in spec]
    return SymDay.build(D, {"sym": sym, "pc": pc, "adv": 500_000, "atr": 0.5}, rows)


CFG = FadeConfig()


def test_short_at_935_cover_at_close():
    x = sd([("09:35", 7.2, 7.3, 7.0, 7.1, 100_000), ("15:55", 6.0, 6.1, 5.9, 6.0, 50_000)])
    tr = backtest([D], [x], CFG)
    assert len(tr) == 1 and tr[0]["why"] == "cover" and tr[0]["pnl"] > 0
    assert tr[0]["shares"] == int(1000 / tr[0]["entry"])
    assert stats(tr, [D], CFG)["win_rate"] == 1.0


def test_disaster_stop_and_filters():
    x = sd([("09:35", 7.2, 7.3, 7.0, 7.1, 100_000), ("10:00", 9.0, 11.5, 9.0, 11.0, 50_000)])
    t = backtest([D], [x], CFG)[0]
    assert t["why"] == "stop" and t["exit"] >= t["stop"] and t["pnl"] < 0
    assert backtest([D], [sd([("09:35", 7.2, 7.3, 7.0, 7.1, 1)], pc=6.5)], CFG) == []   # gap +15% < 30%
    assert backtest([D], [x], CFG.with_(min_rvol=50)) == []


def test_ranks_biggest_gap_and_caps_positions():
    a = sd([("09:35", 7.2, 7.3, 7.0, 7.1, 1), ("15:55", 6, 6, 6, 6, 1)], pc=5.0, sym="A")   # +50%
    b = sd([("09:35", 7.2, 7.3, 7.0, 7.1, 1), ("15:55", 6, 6, 6, 6, 1)], pc=4.0, sym="B")   # +87.5%
    tr = backtest([D], [a, b], CFG.with_(max_positions=1))
    assert [t["symbol"] for t in tr] == ["B"]


class FakeData:
    feed = "iex"

    def movers(self, top):
        return ["GAP", "SMALL"]

    def most_actives(self, top):
        return []

    def snapshots(self, syms):
        return {"GAP": {"dailyBar": {"o": 7.0, "v": 2_000_000}, "prevDailyBar": {"c": 5.0}},
                "SMALL": {"dailyBar": {"o": 5.2, "v": 2_000_000}, "prevDailyBar": {"c": 5.0}}}

    def daily(self, syms, a, b, adj):
        return {s: [{"v": 500_000}] * 20 for s in syms}

    def get(self, path, params):
        return {"trades": {params["symbols"]: {"p": 7.0}}}


def test_fade_trader_dry_run():
    from backtestceo.momentum.paper import DryRun
    clock = {"t": datetime(2026, 10, 1, 9, 35, 5, tzinfo=ET)}
    br = DryRun()
    tr = FadeTrader(CFG, FakeData(), br, lambda s: (True, ""), now=lambda: clock["t"], log=lambda m: None)
    tr.wait_fill = lambda oid, tries=30: (int(float(br.order(oid)["qty"])), float(br.order(oid)["filled_avg_price"]))
    tr.step()
    assert list(tr.positions) == ["GAP"]  # SMALL gap +4% filtered
    p = tr.positions["GAP"]
    assert br.order(p["stop_id"])["type"] == "stop" and br.order(p["stop_id"])["side"] == "buy"
    clock["t"] = datetime(2026, 10, 1, 15, 55, 5, tzinfo=ET)
    tr.step()
    assert tr.covered and not tr.positions
