import json
from datetime import date, datetime, timedelta, timezone

import pytest

from kalshibot.client import KalshiClient
from weather import forecast as fc
from weather.model import WxConfig, bracket_prob, distribution
from weather.stations import kind_from_rules, station_from_rules
from weather.trader import WxTrader, event_date, scan
from weather.calibrate import stats

RULES = ("If the maximum temperature recorded at New York City (CLINYC) for Nov 4, 2026, is greater than 77° "
         "fahrenheit according to The Weather Company, then the market resolves to Yes.")


def test_rules_parsing():
    assert station_from_rules(RULES) == "NYC" and kind_from_rules(RULES) == "high"
    assert station_from_rules("(CLIXYZ)") is None
    assert event_date("KXHIGHNY-26NOV04") == date(2026, 11, 4)


def test_bracket_probs_partition_to_one():
    mu, sd = 71.3, 2.0
    edges = [("less", None, 70), ("between", 70, 71), ("between", 72, 73), ("between", 74, 75),
             ("between", 76, 77), ("greater", 77, None)]
    ps = [bracket_prob(t, f, c, mu, sd) for t, f, c in edges]
    assert sum(ps) == pytest.approx(1.0, abs=1e-9)
    assert ps[1] == max(ps)  # 70-71 holds the mean


def test_observed_floor():
    # already hit 74 by afternoon: brackets below 74 are dead, "less than 70" impossible
    assert bracket_prob("less", None, 70, 71, 2, obs=74, kind="high") == 0
    assert bracket_prob("between", 70, 71, 71, 2, obs=74, kind="high") == 0
    assert bracket_prob("between", 74, 75, 71, 2, obs=74, kind="high") > 0
    # lows: already down to 40 -> "less than 45" is certain
    assert bracket_prob("less", None, 45, 48, 2, obs=40, kind="low") == 1


def test_climate_window_is_local_standard_time():
    a, b = fc.climate_window(date(2026, 11, 4), -5)
    assert a == datetime(2026, 11, 4, 5, tzinfo=timezone.utc) and b - a == timedelta(hours=24)


def test_member_extremes_and_distribution():
    t0 = datetime(2026, 11, 4, 0, tzinfo=timezone.utc)
    times = [t0 + timedelta(hours=i) for i in range(48)]
    members = {f"temperature_2m_member{i:02d}": [60 + (10 if 15 <= h <= 20 else 0) + i * 0.1 for h in range(48)]
               for i in range(20)}
    xs = fc.member_extremes(times, members, date(2026, 11, 4), -5, "high")
    assert len(xs) == 20 and xs[0] == 70 and xs[-1] == pytest.approx(71.9)
    mu, sd = distribution(xs, 1, "high", WxConfig())
    assert mu == pytest.approx(sum(xs) / 20 + 0.8) and sd == 2.3  # spread below floor -> floor
    cal = {"high_lead1": {"n": 40, "bias": 1.4, "sd": 2.9, "models": list(fc.DET_MODELS)}}
    assert distribution(xs, 1, "high", WxConfig(), cal) == pytest.approx((sum(xs) / 20 + 1.4, 2.9))
    old = {"high_lead1": {"n": 40, "bias": 3.0, "sd": 2.9}}  # pre-fix calibration (other models): ignored
    assert distribution(xs, 1, "high", WxConfig(), old) == pytest.approx((sum(xs) / 20 + 0.8, 2.3))


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


class Fake:
    """Kalshi + Open-Meteo stand-in. Ensemble says ~74F tomorrow; market prices 70-71 as the favorite."""

    def __init__(self, day):
        self.day, self.posts, self.nws_high = day, [], 74
        tag = day.strftime("%y%b%d").upper()
        close = iso(datetime(day.year, day.month, day.day, tzinfo=timezone.utc) + timedelta(hours=30))
        def mk(suffix, st, f, c, ya, na, label):
            return {"ticker": f"KXHIGHNY-{tag}-{suffix}", "event_ticker": f"KXHIGHNY-{tag}", "rules_primary": RULES,
                    "strike_type": st, "floor_strike": f, "cap_strike": c, "yes_ask_dollars": ya, "no_ask_dollars": na,
                    "yes_bid_dollars": f"{max(0.0, float(ya) - 0.02):.2f}",
                    "yes_ask_size_fp": "500", "no_ask_size_fp": "500", "volume_24h_fp": "5000",
                    "close_time": close, "yes_sub_title": label, "status": "active"}
        self.markets = [mk("T70", "less", None, 70, "0.03", "0.98", "69 or below"),
                        mk("B70.5", "between", 70, 71, "0.30", "0.72", "70 to 71"),
                        mk("B72.5", "between", 72, 73, "0.45", "0.57", "72 to 73"),
                        mk("B74.5", "between", 74, 75, "0.15", "0.87", "74 to 75"),
                        mk("T75", "greater", 75, None, "0.06", "0.96", "76 or above")]

    def _r(self, body, code=200):
        return type("R", (), {"status_code": code, "json": lambda s: body, "text": json.dumps(body),
                              "raise_for_status": lambda s: None})()

    def get(self, url, params=None, headers=None, timeout=None):
        if "weather.gov/points" in url:
            return self._r({"properties": {"forecast": "https://api.weather.gov/gridpoints/OKX/1,1/forecast"}})
        if "weather.gov/gridpoints" in url:
            return self._r({"properties": {"periods": [{"isDaytime": True, "startTime": f"{self.day.isoformat()}T06:00:00-05:00",
                                                        "temperature": self.nws_high, "temperatureUnit": "F"}]}})
        if "open-meteo" in url:
            t0 = datetime(self.day.year, self.day.month, self.day.day, tzinfo=timezone.utc) - timedelta(days=2)
            times = [t0 + timedelta(hours=i) for i in range(24 * 5)]
            hourly = {"time": [t.strftime("%Y-%m-%dT%H:%M") for t in times]}
            for i in range(30):
                hourly[f"temperature_2m_member{i:02d}"] = [60 + (13.5 + (i % 5) * 0.3 if 17 <= t.hour <= 21 else 0)
                                                           for t in times]
            return self._r({"hourly": hourly})
        path = url.split("/trade-api/v2")[1]
        if path == "/markets":
            return self._r({"markets": self.markets, "cursor": ""})
        if path == "/portfolio/balance":
            return self._r({"balance_dollars": "24.54"})
        return self._r({"market": {**self.markets[0], "status": "active", "result": ""}})

    def post(self, url, json=None, headers=None, timeout=None):
        self.posts.append(json)
        return self._r({"order_id": "o", "fill_count": "2.00", "average_fill_price": json["price"],
                        "average_fee_paid": "0.0100"}, 201)


def test_scan_finds_the_mispriced_brackets():
    now = datetime.now(timezone.utc)
    day = (now - timedelta(hours=5)).date() + timedelta(days=1)
    f = Fake(day)
    client = KalshiClient(base_url="https://x/trade-api/v2", session=f, min_interval=0)
    msgs = []
    opps = scan(client, WxConfig(series=["KXHIGHNY"]), now=now, session=f, log=msgs.append)
    best = {o.ticker.rsplit("-", 1)[1]: o for o in opps}
    # ensemble ~74.6 and NWS 74 vs a market centred on 72-73: 74-75 cheap, 70-71 rich
    assert best["B74.5"].side == "yes" and 0.06 <= best["B74.5"].edge <= 0.20
    assert best["B70.5"].side == "no"
    assert "T75" not in best or best["T75"].side == "no"  # 6c YES is below the 10c floor
    assert all(o.lead == 1 for o in opps)


def test_huge_edge_is_treated_as_model_error():
    now = datetime.now(timezone.utc)
    day = (now - timedelta(hours=5)).date() + timedelta(days=1)
    f = Fake(day)
    client = KalshiClient(base_url="https://x/trade-api/v2", session=f, min_interval=0)
    msgs = []
    opps = scan(client, WxConfig(series=["KXHIGHNY"], max_edge=0.05, min_edge=0.01), now=now, session=f,
                log=msgs.append)
    assert any("too large" in m for m in msgs)
    assert all(o.edge <= 0.05 for o in opps)


def test_paper_trader_respects_caps(tmp_path):
    now = datetime.now(timezone.utc)
    day = (now - timedelta(hours=5)).date() + timedelta(days=1)
    f = Fake(day)
    client = KalshiClient(base_url="https://x/trade-api/v2", session=f, min_interval=0)
    t = WxTrader(client, WxConfig(series=["KXHIGHNY"]), tmp_path)
    res = t.cycle(session=f)
    bought = [r for r in res if r["result"] == "bought"]
    assert bought and t.exposure() <= 4.0 + 1e-9  # max_per_event
    assert all(p.cost <= 2.0 + 1e-9 for p in t.state.positions.values())
    assert f.posts == []  # paper never posts


def test_live_requires_opt_in(tmp_path):
    client = KalshiClient(base_url="https://x/trade-api/v2", session=Fake(date.today()), min_interval=0)
    with pytest.raises(SystemExit):
        WxTrader(client, WxConfig(), tmp_path, live=True)


def test_stats():
    s = stats([1, 2, 3, -2])
    assert s["n"] == 4 and s["bias"] == 1.0 and s["mae"] == 2.0


def test_backtest_simulate_and_loo():
    from weather.backtest import loo, simulate
    errs = {date(2026, 10, i): float(i % 3 - 1) for i in range(1, 31)}
    m, sd = loo(errs, date(2026, 10, 5))
    assert abs(m) < 0.2 and sd >= 1.0
    assert loo({date(2026, 10, 1): 1.0}, date(2026, 10, 1)) is None
    rows = [
        # model 0.60 vs market mid 0.30 -> blended 0.45, YES at 0.31 has edge ~0.13 -> bet, and it wins
        {"station": "NYC", "event": "E1", "ticker": "A", "p_model": 0.60, "bid": 0.29, "ask": 0.31, "result": "yes"},
        # model 0.10 vs mid 0.50 -> NO at 0.51, blended p_no 0.70 -> edge ~0.18 -> bet, and it loses
        {"station": "NYC", "event": "E1", "ticker": "B", "p_model": 0.10, "bid": 0.49, "ask": 0.51, "result": "yes"},
        # agrees with market: no bet
        {"station": "MIA", "event": "E2", "ticker": "C", "p_model": 0.50, "bid": 0.49, "ask": 0.51, "result": "no"},
    ]
    res = simulate(rows, WxConfig())
    assert res["bets"] == 2 and res["win_rate"] == 0.5
    won = [b for b in res["list"] if b["ticker"] == "A"][0]
    assert won["side"] == "yes" and won["pnl"] > 0
    lost = [b for b in res["list"] if b["ticker"] == "B"][0]
    assert lost["side"] == "no" and lost["pnl"] == -lost["cost"]
    assert sum(b["cost"] for b in res["list"]) <= 4.0 + 1e-9  # max_per_event


def test_quotes_at_uses_last_candle_before_decision():
    from weather.backtest import quotes_at

    class S:
        def get(self, url, params=None, headers=None, timeout=None):
            body = {"markets": [{"market_ticker": "A", "candlesticks": [
                {"end_period_ts": 100, "yes_bid": {"close_dollars": "0.40"}, "yes_ask": {"close_dollars": "0.44"}},
                {"end_period_ts": 200, "yes_bid": {"close_dollars": "0.0000"}, "yes_ask": {"close_dollars": "0.99"}},
                {"end_period_ts": 300, "yes_bid": {"close_dollars": "0.60"}, "yes_ask": {"close_dollars": "0.62"}}]}]}
            return type("R", (), {"status_code": 200, "json": lambda s: body, "text": ""})()

    c = KalshiClient(base_url="https://x/trade-api/v2", session=S(), min_interval=0)
    assert quotes_at(c, {"A": 250}) == {"A": (0.40, 0.44)}  # empty book at 200 skipped, 300 is after decision
