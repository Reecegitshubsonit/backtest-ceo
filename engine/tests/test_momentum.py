from datetime import date, datetime, timedelta

from backtestceo.momentum.backtest import Risk, run_day, tradable_symbol
from backtestceo.momentum.config import Config, parse_overrides
from backtestceo.momentum.data import ET
from backtestceo.momentum.engine import Bar, Position, SymbolState, is_catalyst, rvol, sim_bar, sim_entry

D = date(2026, 10, 1)
CFG = Config()


def t(hhmm):
    h, m = map(int, hhmm.split(":"))
    return datetime(D.year, D.month, D.day, h, m, tzinfo=ET)


def bar(hhmm, o, h, l, c, v=100_000):
    return Bar(t(hhmm), o, h, l, c, v)


def surge_then_pullback():
    """Premarket build, then a 9:30 squeeze to a new high and a one-candle red pullback."""
    bars = []
    px = 5.5
    for k in range(30):  # 09:00-09:29 slow drift up from +10%
        tm = (datetime(2026, 10, 1, 9, 0) + timedelta(minutes=k)).strftime("%H:%M")
        bars.append(bar(tm, px, px + 0.03, px - 0.01, px + 0.02))
        px += 0.02
    for k, tm in enumerate(["09:30", "09:31", "09:32", "09:33"]):  # leg: +~8%
        bars.append(bar(tm, px, px + 0.13, px - 0.01, px + 0.12, 300_000))
        px += 0.12
    hi = bars[-1].h
    bars.append(bar("09:34", px, hi - 0.02, px - 0.10, px - 0.08, 120_000))  # red pullback candle, lower volume
    return bars


def state(bars, news=True):
    st = SymbolState("TEST", 5.0, 200_000, [(t("08:00"), "Test Corp wins FDA approval")] if news else [], CFG)
    for b in bars:
        st.update(b)
    return st


def test_rvol_time_adjusted():
    assert round(rvol(77_000, 1_000_000, t("09:30")), 1) == 1.0  # 30-minute floor before/at the open
    assert rvol(1_000_000, 1_000_000, t("16:00")) == 1.0


def test_scanner_needs_gap_volume_price_and_news():
    st = state(surge_then_pullback())
    assert st.in_play_at is not None and st.in_play_at <= t("09:30")
    assert state(surge_then_pullback(), news=False).in_play_at is None
    hi_price = SymbolState("X", 30.0, 1, [(t("08:00"), "x")], CFG)
    hi_price.update(bar("09:30", 35, 36, 34, 35, 10**7))
    assert hi_price.in_play_at is None  # outside $2-20


def test_micro_or_first_pullback_setup_and_entry():
    bars = surge_then_pullback()
    st = state(bars)
    su = st.setup()
    assert su is not None
    assert su.pattern in ("first_pullback", "micro_pullback")
    assert su.trigger == round(bars[-1].h + 0.01, 2) and su.stop == round(bars[-1].l - 0.01, 2)
    nxt = bar("09:35", bars[-1].c, su.trigger + 0.2, bars[-1].c - 0.01, su.trigger + 0.15)
    fill = sim_entry(su, nxt, CFG)
    assert su.trigger <= fill <= su.limit
    assert sim_entry(su, bar("09:35", 1, su.trigger - 0.05, 1, 1), CFG) is None


def test_no_setup_while_candle_still_making_highs():
    bars = surge_then_pullback()[:-1]
    assert state(bars).setup() is None


def test_stop_target_breakeven():
    su = state(surge_then_pullback()).setup()
    p = Position("TEST", su.pattern, 10.0, 9.9, 100, t("09:35"), su)
    sim_bar(p, bar("09:36", 10.0, 10.25, 9.95, 10.2), CFG, entry_bar=False)  # 2R target = 10.20
    assert p.partial_done and p.remaining == 50 and p.stop == 10.0
    sim_bar(p, bar("09:37", 10.1, 10.15, 9.99, 10.0), CFG, entry_bar=False)
    assert p.remaining == 0 and p.fills[-1][3] == "trail_stop"
    assert round(p.pnl(), 2) == round(50 * 0.2 + 50 * (10.0 - 0.02 - 10.0), 2)


def test_risk_halts_on_daily_loss_and_streak():
    r = Risk(CFG.with_(daily_max_loss=250))
    r.closed(-100)
    assert r.cold and r.mult() == 0.5 and r.can_trade()
    r.closed(-160)
    assert r.halted == "daily_max_loss" and not r.can_trade()
    r2 = Risk(CFG)
    for _ in range(3):
        r2.closed(-1)
    assert r2.halted == "consecutive_losses"


def test_run_day_end_to_end():
    bars = surge_then_pullback()
    trig = round(bars[-1].h + 0.01, 2)
    bars.append(bar("09:35", bars[-1].c, trig + 0.5, bars[-1].c - 0.01, trig + 0.45, 300_000))
    bars += [bar(f"09:{36 + k}", trig + 0.45, trig + 0.5, trig + 0.40, trig + 0.45) for k in range(5)]
    rows = [{"t": b.t.isoformat(), "o": b.o, "h": b.h, "l": b.l, "c": b.c, "v": b.v} for b in bars]
    trades, scanned, _ = run_day(D, [("TEST", 5.0, 200_000, [(t("08:00"), "FDA approval")])], {"TEST": rows}, CFG)
    assert scanned and len(trades) == 1
    assert trades[0]["entry_time"] == "09:35" and "target" in trades[0]["exit_reasons"] and trades[0]["pnl"] > 0


def test_catalyst_filter_and_symbols():
    assert is_catalyst("Acme Wins FDA Approval", ["ACME"], CFG)
    assert not is_catalyst("12 Health Care Stocks Moving In Tuesday's Pre-Market Session", ["A"], CFG)
    assert not is_catalyst("Merger news", ["A", "B", "C"], CFG)
    assert tradable_symbol("ACME") and not tradable_symbol("ACMEW") and not tradable_symbol("BRK.B")


def test_overrides():
    o = parse_overrides(["min_gap_pct=20", "patterns=first_pullback", "require_news=false", "max_trades_per_day=3"])
    assert o == {"min_gap_pct": 20.0, "patterns": ("first_pullback",), "require_news": False, "max_trades_per_day": 3}


class FakeData:
    feed = "iex"

    def __init__(self, bars):
        self.rows = [{"t": b.t.isoformat(), "o": b.o, "h": b.h, "l": b.l, "c": b.c, "v": b.v} for b in bars]

    def trading_days(self, a, b):
        return [date(2026, 9, 30), D]

    def news_window(self, a, b):
        return [{"id": 1, "t": "2026-10-01T12:00:00Z", "symbols": ["TEST"], "headline": "Test Corp wins FDA approval"}]

    def snapshots(self, syms):
        return {"TEST": {"latestTrade": {"p": self.rows[-1]["c"]}, "prevDailyBar": {"c": 5.0}}}

    def daily(self, syms, a, b, adj):
        return {"TEST": [{"t": f"2026-09-{d:02d}T04:00:00Z", "c": 5.0, "v": 200_000} for d in range(16, 31)]}

    def minute(self, syms, d, a, b):
        return {"TEST": self.rows}


def test_paper_trader_dry_run_flow(tmp_path, monkeypatch):
    from backtestceo.momentum import paper
    monkeypatch.setattr(paper, "STATE", tmp_path)
    bars = surge_then_pullback()
    clock = {"now": t("09:35") + timedelta(seconds=3)}
    broker = paper.DryRun()
    tr = paper.Trader(CFG, FakeData(bars), broker, now=lambda: clock["now"])
    tr.on_minute()
    assert tr.entry_order and tr.entry_order["sym"] == "TEST"
    su = tr.entry_order["setup"]
    broker.tick("TEST", su.trigger)
    tr.check_entry_fill()
    assert tr.pos and tr.stop_id and broker.order(tr.stop_id)["type"] == "stop"
    tgt = tr.pos.target_price(CFG)
    broker.tick("TEST", tgt)
    tr.on_price(tgt)
    assert tr.pos.partial_done and tr.pos.stop == round(tr.pos.entry, 2)
    broker.tick("TEST", tr.pos.stop - 0.01)  # breakeven stop hits
    tr.on_price(tr.pos.stop - 0.01)
    assert tr.pos is None and tr.risk.trades == 1
    assert (tmp_path / f"trades-{D}.jsonl").exists()
