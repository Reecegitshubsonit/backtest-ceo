import json
import time

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from kalshibot import copy as cp
from kalshibot.client import KalshiClient

# yes bids top 0.60 x500, no bids top 0.38 x40  => YES ask 0.62, NO ask 0.40
BOOK = {"orderbook_fp": {"yes_dollars": [["0.60", "500"]], "no_dollars": [["0.38", "40"]]}}


class Live:
    def __init__(self, balance=30.0, held="0"):
        self.balance, self.held, self.posts = balance, held, []
        self.fill = {"fill_count": "3.00", "average_fill_price": "0.6200", "average_fee_paid": "0.0200"}

    def _r(self, body, code=200):
        return type("R", (), {"status_code": code, "json": lambda s: body, "text": json.dumps(body)})()

    def get(self, url, params=None, headers=None, timeout=None):
        path = url.split("/trade-api/v2")[1]
        if path.startswith("/portfolio"):
            assert headers and "KALSHI-ACCESS-SIGNATURE" in headers
        if path == "/portfolio/balance":
            return self._r({"balance": int(self.balance * 100)})
        if path == "/portfolio/positions":
            return self._r({"market_positions": [{"ticker": "KXT-1", "position_fp": self.held}]})
        if path.endswith("/orderbook"):
            return self._r(BOOK)
        return self._r({"market": {"ticker": "KXT-1", "status": "active"}})

    def post(self, url, json=None, headers=None, timeout=None):
        assert "KALSHI-ACCESS-SIGNATURE" in headers
        self.posts.append(json)
        return self._r({"order_id": "o1", **self.fill}, 201)


@pytest.fixture
def keyfile(tmp_path):
    k = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    p = tmp_path / "k.pem"
    p.write_bytes(k.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL,
                                  serialization.NoEncryption()))
    return str(p)


def engine(tmp_path, keyfile, sess, **cfg):
    client = KalshiClient(base_url="https://x/trade-api/v2", key_id="kid", key_path=keyfile, session=sess,
                          min_interval=0, allow_trading=True)
    base = dict(traders={"alice": 1.0}, live=True, usd_per_trade=2.0, max_per_market=3.0, max_per_trader=8.0,
                max_total_exposure=24.0, kill_file=str(tmp_path / "STOP"))
    base.update(cfg)
    return cp.CopyEngine(client, cp.CopyConfig(**base), tmp_path / "live.json", tmp_path / "lj.jsonl", live=True)


def sig(side="yes", action="buy", price=0.61):
    return cp.Signal("alice", side, action, ticker="KXT-1", price=price, ts=int(time.time()))


def test_live_needs_double_opt_in(tmp_path, keyfile):
    with pytest.raises(SystemExit):
        engine(tmp_path, keyfile, Live(), live=False)


def test_live_buy_yes_small(tmp_path, keyfile):
    s = Live()
    e = engine(tmp_path, keyfile, s)
    out = e.handle(sig())
    assert out["result"] == "copied" and out["live"] and out["contracts"] == 3
    body = s.posts[0]
    assert body["side"] == "bid" and body["count"] == "3" and body["price"] == "0.6300"
    assert body["time_in_force"] == "immediate_or_cancel" and not body["reduce_only"]
    pos = e.state.positions["KXT-1"]
    assert pos.contracts == 3 and pos.cost == pytest.approx(3 * 0.62 + 0.06)


def test_live_buy_no_uses_ask_side(tmp_path, keyfile):
    s = Live()
    s.fill = {"fill_count": "4.00", "average_fill_price": "0.6000", "average_fee_paid": "0.0200"}
    e = engine(tmp_path, keyfile, s)
    out = e.handle(sig(side="no", price=0.40))
    body = s.posts[0]
    assert body["side"] == "ask" and body["price"] == "0.5900"  # buy NO <= 0.41 == sell YES >= 0.59
    assert out["fill"] == 0.40 and e.state.positions["KXT-1"].side == "no"


def test_kill_switch_and_drawdown(tmp_path, keyfile):
    s = Live()
    e = engine(tmp_path, keyfile, s)
    (tmp_path / "STOP").touch()
    assert e.handle(sig())["reason"] == "kill_switch"
    (tmp_path / "STOP").unlink()
    s.balance = 15.0  # started at 30, limit 10
    assert e.handle(sig())["reason"] == "drawdown_limit"
    assert s.posts == []


def test_no_fill_records_nothing(tmp_path, keyfile):
    s = Live()
    s.fill = {"fill_count": "0.00", "remaining_count": "0.00"}
    e = engine(tmp_path, keyfile, s)
    assert e.handle(sig())["reason"] == "no_fill" and not e.state.positions


def test_live_sell_reduce_only(tmp_path, keyfile):
    s = Live()
    e = engine(tmp_path, keyfile, s)
    e.handle(sig())
    s.held = "3.00"
    s.fill = {"fill_count": "3.00", "average_fill_price": "0.6000", "average_fee_paid": "0.0200"}
    out = e.handle(sig(action="sell"))
    body = s.posts[1]
    assert body["side"] == "ask" and body["reduce_only"] and body["price"] == "0.5800"
    assert out["result"] == "closed" and "KXT-1" not in e.state.positions


def test_read_only_client_cannot_post():
    from kalshibot.client import KalshiError
    c = KalshiClient(base_url="https://x/trade-api/v2", session=Live(), min_interval=0)
    with pytest.raises(KalshiError):
        c.create_order("KXT-1", "bid", 1, 0.5)
