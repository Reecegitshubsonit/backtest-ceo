"""US stock paper strategies (Webull sandbox): parity with /workspace/backtests/backtest_alpaca.py on real Alpaca SIP
samples (fixtures from make_stock_fixtures.py), session/holiday handling and order-type rules."""
import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from backtestceo.paper import config as C, strategies as S
from backtestceo.paper.brokers import FakeBroker
from backtestceo.paper.feed import MemoryFeed
from backtestceo.paper.marketdata import ReplayData, completed_days, load_csv
from backtestceo.paper.runner import Runner

FX = Path(__file__).parent / "fixtures" / "paper"
EXP = json.loads((FX / "stocks_expected.json").read_text())
ET = S.ET
STOCKS = {"sip": ["PLTR", "TSLA", "ARKK"], "rsi2": ["SMH", "AMD"], "overnight": ["NVDA", "MSTR", "LLY"]}


@pytest.fixture(scope="module")
def series():
    out = {}
    for syms in STOCKS.values():
        for sym in syms:
            out[(sym, 5)] = load_csv(FX / f"{sym.lower()}_5m.csv")
            out[(sym, 1440)] = load_csv(FX / f"{sym.lower()}_1d.csv")
    return out


def test_default_paper_set():
    cfg = C.RunnerConfig()
    keys = [s.key for s in cfg.strategies]
    assert "first5m_qqq" not in keys and "first5m_qqq" in cfg.backtest_only
    assert {s.symbol for s in cfg.strategies if s.rule == "sip"} == {"PLTR", "TSLA", "ARKK"}
    assert {s.symbol for s in cfg.strategies if s.rule == "rsi2"} == {"SMH", "AMD"}
    assert {s.symbol for s in cfg.strategies if s.rule == "overnight"} == {"NVDA", "MSTR", "LLY"}
    assert all(s.broker == "webull" for s in cfg.strategies if s.rule in ("sip", "rsi2", "overnight"))
    assert {s.key for s in cfg.strategies if s.broker == "alpaca"} == {"supertrend_eth4h", "supertrend_btc4h", "ai_ema_adx_eth4h", "ai_ema_adx_btc4h", "ema9_21_btc1h"}
    # per-strategy caps unchanged; the overall daily cap still covers one entry per strategy per day
    assert (cfg.caps.max_open_positions, cfg.caps.max_notional_usd, cfg.caps.max_entries_per_day, cfg.caps.max_entries_per_day_total) == (1, 2000.0, 4, 16)
    assert len(cfg.strategies) <= cfg.caps.max_entries_per_day_total


# ---------------- parity with backtest_alpaca.py ----------------
@pytest.mark.parametrize("sym", STOCKS["rsi2"])
def test_rsi2_entries_match_backtest(series, sym):
    daily = series[(sym, 1440)]
    got = [daily[i]["ts"].astimezone(ET).date().isoformat() for i, _ in S.rsi2_replay([b["c"] for b in daily])]
    assert got == EXP[f"rsi2_{sym}"] and got


def test_rsi2_decision_rules():
    up = [100 + i * 0.5 for i in range(220)]
    act, info = S.rsi2_decision(up[:-2] + [up[-3] - 3, up[-3] - 6], False)  # sharp 2-day drop in an uptrend
    assert act == "buy" and info["rsi2"] < 10 and info["close"] > info["sma200"]
    assert S.rsi2_decision(up, False)[0] is None            # no pullback
    assert S.rsi2_decision(up, True)[0] == "sell"            # close above SMA5 exits
    down = [200 - i * 0.5 for i in range(220)]
    assert S.rsi2_decision(down, False)[0] is None           # below SMA200: never buys


@pytest.mark.parametrize("sym", STOCKS["sip"])
def test_sip_days_sides_and_returns_match_backtest(series, sym):
    m5, daily = series[(sym, 5)], series[(sym, 1440)]
    days = sorted({b["ts"].astimezone(ET).date() for b in m5})
    firsts, got = [], []
    cost = S.cost_of(sym)
    for d in days:
        rth = S.rth_bars(m5, d)
        if not rth or rth[0]["ts"].astimezone(ET).time() != S.RTH_OPEN or len(rth) < 10:
            continue
        prev = list(firsts)
        firsts.append(rth[0]["v"])
        now = datetime.combine(d, S.RTH_OPEN, ET)
        a14, v14 = S.sip_context(completed_days(daily, now))
        ok, rv, _ = S.sip_filter(rth[0]["o"], a14, v14, rth[0]["v"], prev)
        if not ok:
            continue
        t = S.sip_day(rth, a14)
        if not t:
            continue
        ce = cost + 0.0001 if t["reason"] == "stop" else cost
        frac = min(0.01 / (0.1 * a14 / t["entry"]), 4.0)
        ret = frac * (t["side"] * (t["exit"] / t["entry"] - 1) - (cost + 0.0001) - ce)
        got.append(dict(date=d.isoformat(), ret=ret, side=t["side"]))
    want = EXP[f"sip_{sym}"]
    assert [(g["date"], g["side"]) for g in got] == [(w["date"], w["side"]) for w in want] and want
    assert all(abs(g["ret"] - w["ret"]) < 1e-9 for g, w in zip(got, want))


def test_sip_filter_and_stop_rules():
    ok, rv, _ = S.sip_filter(10.0, 1.0, 2e6, 150.0, [100.0] * 14)
    assert ok and rv == 1.5
    assert not S.sip_filter(10.0, 1.0, 2e6, 150.0, [100.0] * 13)[0]   # needs 14 prior sessions
    assert not S.sip_filter(4.9, 1.0, 2e6, 150.0, [100.0] * 14)[0]    # price
    assert not S.sip_filter(10.0, 0.5, 2e6, 150.0, [100.0] * 14)[0]   # ATR14
    assert not S.sip_filter(10.0, 1.0, 1e6, 150.0, [100.0] * 14)[0]   # avg volume
    assert not S.sip_filter(10.0, 1.0, 2e6, 99.0, [100.0] * 14)[0]    # relative volume
    assert S.sip_signal(dict(o=10, h=11, l=9.5, c=10.5)) == dict(side=1, level=11)
    assert S.sip_signal(dict(o=10, h=11, l=9.5, c=9.8)) == dict(side=-1, level=9.5)
    assert S.sip_signal(dict(o=10, h=11, l=9.5, c=10)) is None
    assert S.sip_stop(1, 100.0, 2.0) == pytest.approx(99.8)
    bar = dict(o=100, h=100.5, l=99.7, c=99.9)
    assert not S.sip_stopped(1, 99.8, bar, True) and S.sip_stopped(1, 99.8, bar, False)  # entry bar needs a close through


# ---------------- session ----------------
def test_session_weekends_holidays_and_early_close():
    assert S.session(datetime(2026, 10, 31, 15, tzinfo=timezone.utc)) is None          # Saturday
    assert S.session(datetime(2026, 11, 26, 15, tzinfo=timezone.utc)) is None          # Thanksgiving
    o, c = S.session(datetime(2026, 11, 27, 15, tzinfo=timezone.utc))
    assert c.astimezone(ET).hour == 13                                                  # early close
    o, c = S.session(datetime(2026, 10, 28, 15, tzinfo=timezone.utc))
    assert (o.astimezone(ET).hour, o.astimezone(ET).minute, c.astimezone(ET).hour) == (9, 30, 16)
    assert S.in_rth(datetime(2026, 10, 28, 13, 30, tzinfo=timezone.utc)) and not S.in_rth(datetime(2026, 10, 28, 13, 29, tzinfo=timezone.utc))


# ---------------- runner ----------------
def _sim(series, start, hours, keys, step_min=5, cfg=None):
    data = ReplayData(series)
    data.now = start
    feed = MemoryFeed()
    kill = lambda: False
    brokers = {"alpaca": FakeBroker("alpaca", data.last_price, kill), "webull": FakeBroker("webull", data.last_price, kill)}
    cfg = cfg or C.RunnerConfig()
    cfg = replace(cfg, strategies=tuple(s for s in cfg.strategies if s.key in keys))
    r = Runner(cfg, data, brokers, feed, kill, mode="dry-run", log=lambda *_: None)
    n = {"i": 0}

    def sleep(_):
        n["i"] += 1
    r.run(lambda: start + n["i"] * timedelta(minutes=step_min), sleep=sleep, max_ticks=int(hours * 60 / step_min))
    return r, feed, brokers


def test_overnight_buys_before_close_sells_next_open_whole_shares(series):
    r, feed, b = _sim(series, datetime(2026, 9, 1, 13, tzinfo=timezone.utc), 48, ("overnight_nvda", "overnight_lly"))
    orders = sorted(b["webull"].orders.values(), key=lambda o: o["time"])
    for key, sym in (("overnight_nvda", "NVDA"), ("overnight_lly", "LLY")):
        closed = r.st[key]["closed"]
        assert closed, key
        for c in closed:
            et_in, et_out = datetime.fromisoformat(c["entry_time"]).astimezone(ET), datetime.fromisoformat(c["exit_time"]).astimezone(ET)
            assert (et_in.hour, et_in.minute) == (15, 55) and et_out.date() > et_in.date() and (et_out.hour, et_out.minute) == (9, 30)
    assert all(o["qty"] == int(o["qty"]) and o["qty"] >= 1 for o in orders)
    assert all(o["order_type"] == "market" for o in orders)  # all inside the regular session
    assert all(o["qty"] * o["filled_price"] <= 2000 for o in orders if o["side"] == "buy")


def test_sip_runner_trades_only_in_play_days(series):
    r, feed, b = _sim(series, datetime(2026, 9, 1, 13, tzinfo=timezone.utc), 56, ("sip_pltr", "sip_tsla", "sip_arkk"), step_min=1)
    want = {(w["date"], w["side"]) for k in ("PLTR", "TSLA", "ARKK") for w in EXP[f"sip_{k}"]}
    for s in ("sip_pltr", "sip_tsla", "sip_arkk"):
        for c in r.st[s]["closed"]:
            d = datetime.fromisoformat(c["entry_time"]).astimezone(ET).date().isoformat()
            assert (d, 1 if c["side"] == "long" else -1) in want
            out = datetime.fromisoformat(c["exit_time"]).astimezone(ET)
            assert out.date().isoformat() == d and (out.hour, out.minute) <= (15, 58)  # flat by the close, same day
    assert sum(len(r.st[s]["closed"]) for s in ("sip_pltr", "sip_tsla", "sip_arkk")) >= 3
    assert all(o["qty"] == int(o["qty"]) for o in b["webull"].orders.values())


def test_stock_orders_outside_rth_are_whole_share_extended_limits(series):
    data = ReplayData(series)
    data.now = datetime(2026, 9, 2, 21, 30, tzinfo=timezone.utc)  # 17:30 ET, after hours
    kill = lambda: False
    br = {"webull": FakeBroker("webull", data.last_price, kill)}
    cfg = replace(C.RunnerConfig(), strategies=tuple(s for s in C.RunnerConfig().strategies if s.key == "overnight_nvda"))
    r = Runner(cfg, data, br, MemoryFeed(), kill, mode="dry-run", log=lambda *_: None)
    s = cfg.strategies[0]
    r._stock_order(s, data.now, "buy", 3.7, "test")
    o = list(br["webull"].orders.values())[-1]
    assert o["order_type"] == "limit" and o["extended_hours"] is True and o["qty"] == 3 and o["limit_price"] > 0
    br["webull"].price_fn = lambda sym: 10_000.0  # not marketable: the runner must cancel, never leave it resting
    r._stock_order(s, data.now, "buy", 1, "test")
    o = list(br["webull"].orders.values())[-1]
    assert o["status"] == "canceled"


def test_webull_extended_hours_requires_limit():
    from backtestceo.paper.brokers import WebullSandboxBroker
    from backtestceo.paper.safety import SafetyError
    b = WebullSandboxBroker.__new__(WebullSandboxBroker)
    with pytest.raises(SafetyError):
        b.order_body("NVDA", "buy", qty=1, notional=None, order_type="market", limit_price=None, extended_hours=True, client_order_id="x")
