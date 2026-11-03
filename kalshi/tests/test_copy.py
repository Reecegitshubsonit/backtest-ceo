import json
import threading
import time
import urllib.request

import pytest

from kalshibot import copy as cp
from kalshibot.client import KalshiClient

BOOK = {"orderbook_fp": {"yes_dollars": [["0.60", "500"]], "no_dollars": [["0.38", "40"]]}}  # yes ask 0.62 x40


class Fake:
    def __init__(self):
        self.market = {"ticker": "KXFED-25DEC-T4", "status": "active", "result": ""}

    def get(self, url, params=None, headers=None, timeout=None):
        path = url.split("/trade-api/v2")[1]
        if path == "/markets":
            body = {"markets": [{"ticker": "KXFED-25DEC-T4", "title": "Will the Fed cut rates in December?"},
                                {"ticker": "KXNBA-LAL", "title": "Lakers win the NBA title?"}], "cursor": ""}
        elif path.endswith("/orderbook"):
            body = BOOK
        else:
            body = {"market": self.market}
        return type("R", (), {"status_code": 200, "json": lambda s: body, "text": ""})()


def engine(tmp_path, **cfg):
    client = KalshiClient(base_url="https://x/trade-api/v2", session=Fake(), min_interval=0)
    c = cp.CopyConfig(traders={"alice": 1.0}, **cfg)
    return cp.CopyEngine(client, c, tmp_path / "s.json", tmp_path / "j.jsonl"), client


def test_parse_text_notification():
    s = cp.parse_signal("alice bought 120 Yes on Will the Fed cut rates in December? at 62¢", now=5)
    assert (s.trader, s.side, s.action, s.contracts, s.price, s.ts) == ("alice", "yes", "buy", 120, 0.62, 5)
    assert s.market == "Will the Fed cut rates in December?"
    s = cp.parse_signal("@Bob sold No on Lakers win the NBA title")
    assert (s.trader, s.side, s.action, s.price) == ("bob", "no", "sell", None)


def test_parse_json_cents_or_dollars():
    assert cp.parse_signal('{"trader":"A","ticker":"T","side":"yes","price":62}').price == 0.62
    assert cp.parse_signal({"trader": "A", "ticker": "T", "side": "no", "price": 0.3}).price == 0.3


def test_best_match():
    idx = [("will the fed cut rates in december?", "FED"), ("lakers win the nba title?", "LAL")]
    assert cp.best_match("Will the Fed cut rates in December", idx) == "FED"
    assert cp.best_match("something else entirely", idx) is None


def test_copy_buy_by_title_then_sell(tmp_path):
    e, _ = engine(tmp_path, usd_per_trade=20)
    now = int(time.time())
    out = e.handle(cp.parse_signal("alice bought 120 Yes on Will the Fed cut rates in December? at 61¢", now), now)
    assert out["result"] == "copied" and out["fill"] == 0.62 and out["slippage"] == 0.01
    assert out["contracts"] == 31  # $20 / (0.62 + fee)
    assert e.state.positions["KXFED-25DEC-T4"].contracts == 31
    # restart keeps state and trader attribution
    e2, _ = engine(tmp_path)
    assert e2.owner["KXFED-25DEC-T4"] == "alice"
    out = e2.handle(cp.Signal("alice", "yes", "sell", ticker="KXFED-25DEC-T4", ts=now), now)
    assert out["result"] == "closed" and out["fill"] == 0.60 and out["pnl"] < 0


@pytest.mark.parametrize("sig,reason", [
    (dict(trader="mallory"), "trader_not_followed"),
    (dict(ts=-1000), "stale"),
    (dict(price=0.55), "slippage"),
    (dict(ticker="", market="no such market here"), "market_not_resolved"),
])
def test_guards(tmp_path, sig, reason):
    e, _ = engine(tmp_path)
    now = int(time.time())
    base = dict(trader="alice", side="yes", action="buy", ticker="KXFED-25DEC-T4", price=0.62, ts=now)
    base.update(sig)
    if base["ts"] < 0:
        base["ts"] = now - 1000
    assert e.handle(cp.Signal(**base), now)["reason"] == reason


def test_liquidity_and_caps(tmp_path):
    e, _ = engine(tmp_path, usd_per_trade=1000, max_per_market=1000, max_per_trader=1000, max_total_exposure=1000)
    now = int(time.time())
    out = e.handle(cp.Signal("alice", "yes", ticker="KXFED-25DEC-T4", price=0.62, ts=now), now)
    assert out["contracts"] == 40  # only 40 offered at the best ask
    e, _ = engine(tmp_path / "b", max_per_market=0.5)
    (tmp_path / "b").mkdir(exist_ok=True)
    assert e.handle(cp.Signal("alice", "yes", ticker="KXFED-25DEC-T4", ts=now), now)["reason"] == "no_room_or_liquidity"


def test_http_server(tmp_path):
    e, _ = engine(tmp_path)
    port = 18787
    threading.Thread(target=cp.serve, args=(e, "127.0.0.1", port, "tok"), daemon=True).start()
    time.sleep(0.3)
    body = json.dumps({"trader": "alice", "ticker": "KXFED-25DEC-T4", "side": "yes", "price": 0.62}).encode()
    req = urllib.request.Request(f"http://127.0.0.1:{port}/signal", data=body, headers={"X-Token": "tok"})
    with urllib.request.urlopen(req) as r:
        assert json.load(r)["result"] == "copied"
    bad = urllib.request.Request(f"http://127.0.0.1:{port}/signal", data=body, headers={"X-Token": "nope"})
    with pytest.raises(urllib.error.HTTPError):
        urllib.request.urlopen(bad)
