"""Paper runner with fake brokers: safety refusals, kill switch, caps, event emission and runner-level parity."""
import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from backtestceo.paper import cli, config as C, envfile, safety
from backtestceo.paper.brokers import AlpacaPaperBroker, FakeBroker, WebullSandboxBroker
from backtestceo.paper.feed import LiveEvents, MemoryFeed
from backtestceo.paper.marketdata import ReplayData, load_csv
from backtestceo.paper.runner import Runner

FX = Path(__file__).parent / "fixtures" / "paper"
EXP = json.loads((FX / "expected.json").read_text())
GOOD = dict(WEBULL_ENV="sandbox", ALPACA_PAPER_TRADING_ONLY="true")


# ---------------- safety ----------------
@pytest.mark.parametrize("env", [
    {},
    dict(GOOD, WEBULL_ENV="production"),
    dict(GOOD, ALPACA_PAPER_TRADING_ONLY="false"),
    dict(GOOD, ALPACA_BASE_URL="https://api.alpaca.markets"),
    dict(GOOD, APCA_API_BASE_URL="https://api.alpaca.markets/v2"),
    dict(GOOD, WEBULL_ENDPOINT="api.webull.com"),
])
def test_refuses_to_start_without_paper_settings(env):
    with pytest.raises(safety.SafetyError):
        safety.require_paper(env)


def test_accepts_paper_settings():
    safety.require_paper(dict(GOOD, ALPACA_BASE_URL="https://paper-api.alpaca.markets"))


@pytest.mark.parametrize("url", ["https://api.alpaca.markets/v2/orders", "https://api.webull.com/x", "https://evil.example", "http://paper-api.alpaca.markets/v2"])
def test_host_allowlist_rejects_live_and_unknown_hosts(url):
    with pytest.raises(safety.SafetyError):
        safety.assert_host(url, safety.ORDER_HOSTS)


def test_cli_start_refuses_without_paper_flags(tmp_path, capsys, monkeypatch):
    for k in envfile.NAMES:
        monkeypatch.delenv(k, raising=False)
    env = tmp_path / ".env"
    env.write_text("WEBULL_ENV=production\nALPACA_PAPER_TRADING_ONLY=true\n")
    assert cli.main(["run", "--env-file", str(env), "--state-dir", str(tmp_path)]) == 2
    assert "WEBULL_ENV=sandbox" in capsys.readouterr().err


def test_env_reader_reads_only_named_vars_and_never_shows_values(tmp_path):
    f = tmp_path / ".env"
    f.write_text("export ALPACA_API_KEY='abc123'\nOTHER_SECRET=zzz\nWEBULL_ENV=sandbox\n")
    e = envfile.load(f, {})
    assert e["ALPACA_API_KEY"] == "abc123" and "OTHER_SECRET" not in e
    assert "abc123" not in repr(e) and "abc123" not in str(e)
    assert f.read_text().startswith("export ALPACA_API_KEY")  # untouched


def test_brokers_do_not_expose_keys_in_repr():
    b = AlpacaPaperBroker("KEYVALUE", "SECRETVALUE", lambda: False)
    assert "KEYVALUE" not in repr(b) and b.base == "https://paper-api.alpaca.markets"


# ---------------- kill switch ----------------
def test_kill_switch_sources(tmp_path):
    assert safety.kill_switch_on({"PAPER_TRADING_KILL_SWITCH": "1"})
    assert not safety.kill_switch_on({"PAPER_TRADING_KILL_SWITCH": "0"})
    k = tmp_path / "KILL"
    k.touch()
    assert safety.kill_switch_on({}, k)
    assert safety.kill_switch_on({}, None, lambda: {"PAPER_TRADING_KILL_SWITCH": "true"})
    assert safety.kill_switch_on({}, None, lambda: (_ for _ in ()).throw(OSError()))  # unreadable -> fail closed


def test_kill_switch_blocks_every_order():
    on = {"v": True}
    b = FakeBroker("alpaca", lambda s: 100.0, kill_check=lambda: on["v"])
    with pytest.raises(safety.KillSwitchEngaged):
        b.submit("BTC/USD", "buy", notional=10)
    assert b.orders == {}


def _sim(series, start, hours, step_min=60, cfg=None, kill=lambda: False, feed=None):
    data = ReplayData(series)
    data.now = start
    feed = feed or MemoryFeed()
    brokers = {"alpaca": FakeBroker("alpaca", data.last_price, kill), "webull": FakeBroker("webull", data.last_price, kill)}
    r = Runner(cfg or C.RunnerConfig(), data, brokers, feed, kill, mode="dry-run", log=lambda *_: None)
    n = {"i": 0}

    def sleep(_):
        n["i"] += 1
    r.run(lambda: start + n["i"] * timedelta(minutes=step_min), sleep=sleep, max_ticks=int(hours * 60 / step_min))
    return r, feed, brokers


# first5m_qqq left the paper set on 2026-10-28 (backtest-only now); its rule is still covered here
FIRST5M_QQQ = C.StrategyConfig("first5m_qqq", "first5m_qqq", "first5m", "webull", "QQQ")


def _only(cfg, *keys, **kw):
    pool = cfg.strategies + ((FIRST5M_QQQ,) if "first5m_qqq" in keys else ())
    return replace(cfg, strategies=tuple(s for s in pool if s.key in keys), **kw)


@pytest.fixture(scope="module")
def series():
    return {("ETH/USD", 60): load_csv(FX / "eth_1h.csv"), ("BTC/USD", 60): load_csv(FX / "btc_1h.csv"), ("QQQ", 5): load_csv(FX / "qqq_5m.csv")}


def test_kill_switch_in_main_loop_halts_runner(series):
    flips = {"n": 0}

    def kill():
        flips["n"] += 1
        return flips["n"] > 3
    r, feed, brokers = _sim(series, datetime(2026, 9, 1, 13, tzinfo=timezone.utc), 48, cfg=_only(C.RunnerConfig(), "ema9_21_btc1h"), kill=kill)
    assert r.halted and "KILL" in json.dumps(feed.kinds("agent_activity")).upper()
    assert all(o["time"] for o in brokers["alpaca"].orders.values())
    assert len(brokers["alpaca"].orders) <= 1


# ---------------- caps ----------------
def test_caps_block_entries(series):
    cfg = _only(C.RunnerConfig(), "ema9_21_btc1h", caps=C.Caps(max_entries_per_day=1, max_entries_per_day_total=1))
    r, feed, brokers = _sim(series, datetime(2026, 9, 1, tzinfo=timezone.utc), 24 * 20, cfg=cfg)
    days = {}
    for o in brokers["alpaca"].orders.values():
        if o["side"] == "buy":
            d = datetime.fromisoformat(o["time"]).date()
            days[d] = days.get(d, 0) + 1
    rejected = [e for e in feed.kinds("ceo_decision") if e["outcome"] == "rejected"]
    assert any("daily entry cap" in e["reason"] for e in rejected)
    for e in feed.kinds("strategy_result"):
        for leg in e["paper"]["legs"]:
            assert leg["entries_today"] <= 1
    # notional never above the cap
    assert all(o["qty"] * o["filled_price"] <= 2000.01 for o in brokers["alpaca"].orders.values() if o["side"] == "buy")


def test_caps_cannot_be_loosened(tmp_path):
    f = tmp_path / "c.json"
    f.write_text(json.dumps({"caps": {"max_notional_usd": 50000}}))
    with pytest.raises(ValueError):
        C.load(f)
    f.write_text(json.dumps({"caps": {"max_notional_usd": 500}}))
    assert C.load(f).caps.max_notional_usd == 500


def test_first5m_size_capped_by_notional(series):
    cfg = _only(C.RunnerConfig(), "first5m_qqq")
    r, feed, brokers = _sim(series, datetime(2026, 9, 1, 13, tzinfo=timezone.utc), 24 * 5, step_min=5, cfg=cfg)
    entries = [o for o in brokers["webull"].orders.values() if o["side"] in ("buy", "short")]
    assert entries and all(o["qty"] * o["filled_price"] <= 2000 for o in entries)
    assert all(o["qty"] == int(o["qty"]) for o in entries)


# ---------------- events ----------------
def test_pipeline_emits_every_agent_and_ceo_decision(series):
    r, feed, _ = _sim(series, datetime(2026, 9, 1, 13, tzinfo=timezone.utc), 24 * 3, step_min=5, cfg=_only(C.RunnerConfig(), "first5m_qqq"))
    acts = feed.kinds("agent_activity")
    assert {e["slot"] for e in acts} == {"scanner", "regime", "strategist", "backtester", "auditor", "risk"}
    assert all("RULE-BASED" in e["task"] for e in acts)
    dec = feed.kinds("ceo_decision")
    ids = {e["id"] for e in dec}
    for i in ids:  # pending first, then the verdict under the same id
        seq = [e["outcome"] for e in dec if e["id"] == i]
        assert seq[0] == "pending" and seq[-1] in ("approved", "rejected")
    sr = feed.kinds("strategy_result")
    names = {e["strategy"] for e in sr}
    assert names == {"first5m_qqq"}  # one wall screen per active paper leg, keyed by the runner key
    f5 = sr[-1]
    assert f5["family"] == "first5m_rth_direction" and f5["name"] == "First 5-min Candle · QQQ"
    assert f5["stats"]["trades"] and f5["paper"]["legs"][0]["fills"]


def test_publish_one_screen_per_default_paper_leg_and_no_backtest_only(series):
    r, feed, _ = _sim(series, datetime(2026, 9, 1, 13, tzinfo=timezone.utc), 1, step_min=5)
    names = {e["strategy"]: e["name"] for e in feed.kinds("strategy_result")}
    assert set(names) == {s.key for s in C.RunnerConfig().strategies}
    assert len(names) == 13 and "first5m_qqq" not in names
    assert not any("AEX" in n or "EMA150" in n for n in names.values())
    assert names["sip_pltr"] == "Stocks-in-Play ORB · PLTR" and names["supertrend_eth4h"] == "Adaptive SuperTrend · ETH/USD 4h"


def test_events_conform_to_live_events_schema(series):
    """Same rules as live-events/server.mjs validate()."""
    _, feed, _ = _sim(series, datetime(2026, 9, 1, 13, tzinfo=timezone.utc), 24 * 2, step_min=5)
    slots = {"scanner", "strategist", "backtester", "auditor", "regime", "risk"}
    for e in feed.events:
        assert len(e["source"]) <= 80 and e["at"].endswith("Z")
        if e["kind"] == "agent_activity":
            assert e["slot"] in slots and e["state"] in ("idle", "working", "waiting", "error") and len(e["task"]) <= 200
            assert e.get("level", "info") in ("info", "warn", "error")
        elif e["kind"] == "ceo_decision":
            assert e["id"] and e["agent"] in slots and e["outcome"] in ("approved", "rejected", "pending")
        else:
            assert e["kind"] == "strategy_result" and e["strategy"] and e["name"] and isinstance(e["stats"], dict)
            assert e["stage"] in ("scanning", "strategist", "backtest", "validation", "risk", "ceo")
            assert all(isinstance(v, (int, float)) for v in e["equity"])
    json.dumps(feed.events)


def test_feed_keeps_events_when_service_is_down(tmp_path):
    f = LiveEvents("http://127.0.0.1:9", log_path=tmp_path / "ev.jsonl", timeout=0.2)
    f.emit(dict(kind="agent_activity", slot="risk", task="t", state="working"))
    assert f.flush() is False and len(f.pending) == 1 and f.last_error
    assert (tmp_path / "ev.jsonl").read_text().count("\n") == 1


def test_feed_must_be_local():
    with pytest.raises(safety.SafetyError):
        LiveEvents("https://example.com")


# ---------------- runner-level parity with backtest.py ----------------
def _ts(s):
    return datetime.fromisoformat(s).astimezone(timezone.utc)


@pytest.mark.parametrize("key,rule,exp", [("ai_ema_adx_eth4h", "alphainsider", "alphainsider"), ("supertrend_eth4h", "supertrend", "supertrend")])
def test_runner_long_trades_match_backtest(series, key, rule, exp):
    start = datetime(2026, 3, 1, tzinfo=timezone.utc)
    cfg = _only(C.RunnerConfig(), key, lookback_hours=10 ** 6)  # whole fixture = same indicator warm-up as backtest.py
    r, feed, brokers = _sim(series, start, 24 * 120, cfg=cfg)
    closed = [(c["entry_time"], c["exit_time"]) for c in r.st[key]["closed"]]
    end = start + timedelta(days=120)
    want = [(_ts(t["entry_time"]), _ts(t["exit_time"])) for t in EXP[exp]["trades"]
            if t["side"] == "long" and start < _ts(t["entry_time"]) and _ts(t["exit_time"]) < end]
    got = [(_ts(a), _ts(b)) for a, b in closed]
    assert want and got == want  # identical long trades (Alpaca crypto is long-only, so shorts are skipped)


def test_runner_first5m_days_and_sides_match_backtest(series):
    start = datetime(2026, 9, 1, 12, tzinfo=timezone.utc)
    r, _, _ = _sim(series, start, 24 * 14, step_min=5, cfg=_only(C.RunnerConfig(), "first5m_qqq"))
    got = [(_ts(c["entry_time"]).date(), c["side"]) for c in r.st["first5m_qqq"]["closed"]]
    end = start + timedelta(days=14)
    want = [(_ts(t["entry_time"]).date(), t["side"]) for t in EXP["first5m_qqq"]["trades"] if start <= _ts(t["entry_time"]) < end - timedelta(days=1)]
    assert got[:len(want)] == want


# ---------------- Webull order body / endpoint ----------------
class _Resp:
    def __init__(self, code, body):
        self.status_code, self._b, self.text = code, body, json.dumps(body)

    def json(self):
        return self._b


class _FakeApi:
    def __init__(self, key, secret, region):
        self.endpoints = {}

    def add_endpoint(self, region, host):
        self.endpoints[region] = host

    def set_token_dir(self, d):
        pass


class _FakeTrade:
    def __init__(self, api):
        assert api.endpoints["us"] == "api.sandbox.webull.com"
        self.placed = []
        t = self

        class O:
            def place_order(self, acct, orders):
                t.placed.append(orders[0])
                return _Resp(200, {"client_order_id": orders[0]["client_order_id"]})

            def get_order_detail(self, acct, coid):
                o = [x for x in t.placed if x["client_order_id"] == coid][0]
                return _Resp(200, {"orders": [{"status": "FILLED", "filled_quantity": o.get("quantity", "1"), "filled_price": o.get("limit_price", "600.00")}]})

            def cancel_order(self, acct, coid):
                return _Resp(200, {})

            def preview_order(self, acct, orders):
                return _Resp(200, {"ok": True})
        self.order_v3 = O()


def test_webull_extended_hours_limit_order_body():
    b = WebullSandboxBroker("k", "s", "ACCT", lambda: False, sdk=(_FakeApi, _FakeTrade))
    o = b.submit("QQQ", "buy", qty=1, order_type="limit", limit_price=601.234, extended_hours=True)
    body = b.trade.placed[0]
    assert body["support_trading_session"] == "ALL" and body["order_type"] == "LIMIT" and body["limit_price"] == "601.23"
    assert body["entrust_type"] == "QTY" and body["quantity"] == "1" and body["side"] == "BUY" and len(body["client_order_id"]) <= 32
    assert o["status"] == "filled"
    with pytest.raises(safety.SafetyError):
        b.submit("QQQ", "buy", qty=1, extended_hours=True)  # extended session needs a LIMIT order
    b.submit("QQQ", "short", qty=2)
    assert b.trade.placed[-1]["side"] == "SHORT" and b.trade.placed[-1]["support_trading_session"] == "CORE"


def test_webull_sdk_endpoint_is_pinned_to_sandbox():
    sdk = pytest.importorskip("webull.core.client")
    api = sdk.ApiClient("k", "s", "us")
    api.add_endpoint("us", safety.WEBULL_SANDBOX_HOST)
    WebullSandboxBroker._check_endpoint(api, "us")  # raises if the SDK would resolve anything else
    raw = sdk.ApiClient("k", "s", "us")
    with pytest.raises(safety.SafetyError):
        WebullSandboxBroker._check_endpoint(raw, "us")  # SDK default is production api.webull.com


def test_smoke_test_dry_run_and_plan(tmp_path, capsys):
    assert cli.main(["smoke-test", "--state-dir", str(tmp_path)]) == 0
    assert "nothing sent" in capsys.readouterr().out
    assert cli.main(["smoke-test", "--dry-run", "--extended-hours", "--no-feed", "--state-dir", str(tmp_path)]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["alpaca"]["buy"]["status"] == "filled" and out["alpaca"]["close"]["status"] == "filled"
    assert out["webull"]["buy"]["extended_hours"] is True and out["webull"]["buy"]["order_type"] == "limit"
