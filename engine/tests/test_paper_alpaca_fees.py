"""Alpaca crypto: $10 minimum order and fees taken from the bought asset (filled_qty > qty actually held)."""
import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from backtestceo.paper import cli, config as C
from backtestceo.paper.brokers import AlpacaPaperBroker, FakeBroker
from backtestceo.paper.feed import MemoryFeed
from backtestceo.paper.marketdata import ReplayData, load_csv
from backtestceo.paper.runner import Runner

FX = Path(__file__).parent / "fixtures" / "paper"


class _R:
    def __init__(self, code, body):
        self.status_code, self._b = code, body
        self.content = json.dumps(body).encode()
        self.text = json.dumps(body)

    def json(self):
        return self._b


class _Session:
    """Records requests; answers like Alpaca paper."""

    def __init__(self, held=None):
        self.calls, self.held = [], held

    def request(self, method, url, headers=None, timeout=None, **kw):
        assert url.startswith("https://paper-api.alpaca.markets/")
        self.calls.append((method, url, kw))
        if url.endswith("/v2/positions/BTCUSD"):
            if method == "DELETE":
                return _R(200, {"id": "x", "client_order_id": "close1", "status": "accepted", "filled_qty": "0"})
            return _R(404, {"message": "position does not exist"}) if self.held is None else _R(200, {"qty": self.held, "qty_available": self.held})
        return _R(200, {"id": "o1", "client_order_id": kw.get("json", {}).get("client_order_id"), "status": "accepted", "filled_qty": "0"})


def test_alpaca_crypto_minimum_is_10_dollars():
    sess = _Session()
    b = AlpacaPaperBroker("k", "s", lambda: False, session=sess)
    with pytest.raises(ValueError, match="at least \\$10"):
        b.submit("BTC/USD", "buy", notional=5)
    assert sess.calls == []  # rejected before anything was sent
    b.submit("BTC/USD", "buy", notional=10)
    assert sess.calls[-1][2]["json"]["notional"] == "10"


def test_smoke_cli_default_is_10_and_refuses_less(tmp_path, capsys):
    assert cli._args(["smoke-test"]).alpaca_notional == 10.0
    assert cli.main(["smoke-test", "--dry-run", "--broker", "alpaca", "--alpaca-notional", "5", "--no-feed", "--state-dir", str(tmp_path)]) == 2
    assert "at least $10" in capsys.readouterr().err


def test_alpaca_position_qty_and_close_use_positions_endpoint():
    sess = _Session(held="0.000120981")
    b = AlpacaPaperBroker("k", "s", lambda: False, session=sess)
    assert b.position_qty("BTC/USD") == pytest.approx(0.000120981)
    b.close_position("BTC/USD")
    assert sess.calls[-1][:2] == ("DELETE", "https://paper-api.alpaca.markets/v2/positions/BTCUSD")
    assert AlpacaPaperBroker("k", "s", lambda: False, session=_Session(held=None)).position_qty("BTC/USD") == 0.0
    with pytest.raises(Exception, match="KILL"):
        AlpacaPaperBroker("k", "s", lambda: True, session=sess).close_position("BTC/USD")


def test_fake_broker_reproduces_the_insufficient_balance_error():
    b = FakeBroker("alpaca", lambda s: 82450.0, crypto_fee=0.0025)
    o = b.submit("BTC/USD", "buy", notional=10)
    assert b.position_qty("BTC/USD") < o["filled_qty"]
    bad = b.submit("BTC/USD", "sell", qty=o["filled_qty"])
    assert bad["status"] == "rejected" and "insufficient balance" in bad["message"]


def test_smoke_dry_run_sells_back_post_fee_position(tmp_path, capsys):
    assert cli.main(["smoke-test", "--dry-run", "--broker", "alpaca", "--no-feed", "--state-dir", str(tmp_path)]) == 0
    out = json.loads(capsys.readouterr().out)["alpaca"]
    assert out["buy"]["status"] == "filled" and out["position_after_fees"] < out["buy"]["filled_qty"]
    assert out["close"]["status"] == "filled" and out["close"]["filled_qty"] == pytest.approx(out["position_after_fees"])


def test_smoke_sells_only_its_own_qty_when_other_btc_is_held(tmp_path):
    b = FakeBroker("alpaca", lambda s: 80000.0, crypto_fee=0.0025)
    b.submit("BTC/USD", "buy", notional=1000)  # e.g. a runner position
    before = b.position_qty("BTC/USD")
    a = cli._args(["smoke-test", "--dry-run", "--broker", "alpaca"])
    data = ReplayData({})
    res = cli.smoke(a, {"alpaca": b}, data, MemoryFeed(), lambda: False)["alpaca"]
    assert res["sell"]["status"] == "filled"
    assert b.position_qty("BTC/USD") == pytest.approx(before, abs=1e-9)


def test_runner_records_post_fee_qty_and_exits_succeed():
    series = {("BTC/USD", 60): load_csv(FX / "btc_1h.csv")}
    data = ReplayData(series)
    start = datetime(2026, 9, 1, tzinfo=timezone.utc)
    data.now = start
    alp = FakeBroker("alpaca", data.last_price, crypto_fee=0.0025)
    cfg = replace(C.RunnerConfig(), strategies=tuple(s for s in C.RunnerConfig().strategies if s.key == "ema9_21_btc1h"))
    feed = MemoryFeed()
    r = Runner(cfg, data, {"alpaca": alp}, feed, lambda: False, mode="dry-run", log=lambda *_: None)
    n = {"i": 0}
    seen_entry = []

    def sleep(_):
        n["i"] += 1
        p = r.st["ema9_21_btc1h"]["pos"]
        if p and not seen_entry:
            seen_entry.append(p["qty"])
            assert p["qty"] == pytest.approx(alp.position_qty("BTC/USD"), abs=1e-9)  # post-fee, not gross filled qty
            gross = [o for o in alp.orders.values() if o["side"] == "buy"][-1]["filled_qty"]
            assert p["qty"] < gross
    r.run(lambda: start + n["i"] * timedelta(hours=1), sleep=sleep, max_ticks=24 * 20)
    st = r.st["ema9_21_btc1h"]
    assert seen_entry and len(st["closed"]) >= 2
    assert not [o for o in alp.orders.values() if o["status"] == "rejected"]
    assert "order" not in json.dumps([e for e in feed.kinds("agent_activity") if e.get("level") == "error"])
    if not st["pos"]:
        assert alp.position_qty("BTC/USD") == pytest.approx(0.0, abs=1e-9)


def test_runner_exit_is_capped_at_broker_position():
    """Shared BTC position smaller than the runner's book (e.g. fees or a manual sale): sell what is there."""
    b = FakeBroker("alpaca", lambda s: 80000.0, crypto_fee=0.0)
    b.submit("BTC/USD", "buy", qty=0.001)
    cfg = replace(C.RunnerConfig(), strategies=tuple(s for s in C.RunnerConfig().strategies if s.key == "ema9_21_btc1h"))
    r = Runner(cfg, ReplayData({}), {"alpaca": b}, MemoryFeed(), lambda: False, mode="dry-run", log=lambda *_: None)
    s = cfg.strategies[0]
    r.st[s.key]["pos"] = dict(side="long", dir=1, qty=0.0011, entry=80000.0, opened_at="x", entry_bar_ts="x", stop=None)
    f = r._execute(s, datetime(2026, 9, 1, tzinfo=timezone.utc), "sell", "test exit", qty=0.0011)
    assert f and f["qty"] == pytest.approx(0.001) and b.position_qty("BTC/USD") == pytest.approx(0.0)
