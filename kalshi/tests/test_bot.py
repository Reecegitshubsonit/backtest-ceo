from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from kalshibot import model, paper, runner
from kalshibot.client import KalshiClient, sign
from kalshibot.calibrate import bucketize, ratio_table

NOW = datetime.now(timezone.utc)


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def mk(ticker="KXTEST-1", yb="0.89", ya="0.92", vol="5000", hours=48, event="KXTEST"):
    return {"ticker": ticker, "event_ticker": event, "status": "active", "title": "t",
            "yes_bid_dollars": yb, "yes_ask_dollars": ya, "volume_24h_fp": vol,
            "close_time": iso(NOW + timedelta(hours=hours))}


BOOK = {"orderbook_fp": {"yes_dollars": [["0.88", "50.00"], ["0.89", "120.00"]],
                         "no_dollars": [["0.07", "10.00"], ["0.08", "40.00"]]}}


def test_fee_matches_kalshi_examples():
    assert model.fee(100, 0.50, 0.07) == 1.75
    assert model.fee(1, 0.50, 0.07) == 0.02  # rounds up to the cent
    assert model.fee(10, 0.9, 0.0) == 0.0


def test_parse_book_and_asks():
    b = model.parse_book(BOOK)
    assert b.best_bid("yes") == 0.89 and b.best_ask("yes") == 0.92
    assert b.best_bid("no") == 0.08 and b.best_ask("no") == 0.11
    assert b.size_at("yes", 0.89) == 120
    legacy = model.parse_book({"orderbook": {"yes": [[89, 5]], "no": [[8, 2]]}})
    assert legacy.best_ask("yes") == 0.92


def test_price_accepts_dollars_or_cents():
    assert model.price({"yes_bid_dollars": "0.4200"}, "yes_bid") == 0.42
    assert model.price({"yes_bid": 42}, "yes_bid") == 0.42


def test_prefilter_picks_favorite_side():
    cfg = model.Config()
    assert model.prefilter(mk(), cfg, NOW) == "yes"
    assert model.prefilter(mk(yb="0.08", ya="0.11"), cfg, NOW) == "no"
    assert model.prefilter(mk(yb="0.45", ya="0.55"), cfg, NOW) is None
    assert model.prefilter(mk(hours=1), cfg, NOW) is None
    assert model.prefilter(mk(vol="5"), cfg, NOW) is None
    assert model.prefilter(mk(ticker="KXMVEFOO"), cfg, NOW) is None


def test_quote_improves_bid_without_crossing_and_respects_caps():
    cfg = model.Config()
    q = model.make_quote(mk(), model.parse_book(BOOK), "yes", cfg, model.DEFAULT_CALIBRATION, 1000, 25, 40, 300)
    assert q is not None
    assert q.price == 0.90 and q.price < q.best_ask
    assert q.edge >= cfg.min_edge
    assert q.contracts * q.price <= 25 + 1e-9
    assert q.queue_ahead == 0  # nobody resting at 0.90 yet
    # no room -> no quote
    assert model.make_quote(mk(), model.parse_book(BOOK), "yes", cfg, model.DEFAULT_CALIBRATION, 1000, 0.5, 40, 300) is None


def test_quote_joins_when_spread_is_one_tick():
    book = {"orderbook_fp": {"yes_dollars": [["0.90", "30"]], "no_dollars": [["0.09", "30"]]}}
    q = model.make_quote(mk(yb="0.90", ya="0.91"), model.parse_book(book), "yes", model.Config(),
                         model.DEFAULT_CALIBRATION, 1000, 25, 40, 300)
    assert q.price == 0.90 and q.queue_ahead == 30


def test_model_has_no_edge_at_coinflip():
    assert model.true_prob_favorite(0.5, model.DEFAULT_CALIBRATION) == pytest.approx(0.5)
    assert model.true_prob_favorite(0.95, model.DEFAULT_CALIBRATION) > 0.95


def _trade(tid, yes, side, n, ts):
    return {"trade_id": tid, "ticker": "KXTEST-1", "yes_price_dollars": f"{yes:.4f}",
            "no_price_dollars": f"{1 - yes:.4f}", "count_fp": f"{n}", "taker_side": side,
            "created_time": iso(datetime.fromtimestamp(ts, timezone.utc))}


def test_paper_fill_queue_and_settlement(tmp_path):
    log = paper.Journal(tmp_path / "j.jsonl")
    st = paper.State(cash=100.0)
    t0 = int(NOW.timestamp())
    q = model.Quote("KXTEST-1", "KXTEST", "yes", 0.90, 10, 0.93, 0.02, 0.89, 0.92, 5, "", "")
    paper.place(st, q, t0, log)
    trades = [
        _trade("a", 0.90, "yes", 50, t0 + 1),   # taker bought yes at our price: not us
        _trade("b", 0.90, "no", 8, t0 + 2),     # eats 5 queue, fills 3
        _trade("b", 0.90, "no", 8, t0 + 2),     # duplicate id ignored
        _trade("c", 0.88, "yes", 100, t0 + 3),  # traded through: fills remaining 7
    ]
    assert paper.apply_trades(st, "KXTEST-1", trades, 0.0175, log) == 10
    assert not st.orders
    pos = st.positions["KXTEST-1"]
    assert pos.contracts == 10
    # replaying the same tape does nothing
    assert paper.apply_trades(st, "KXTEST-1", trades, 0.0175, log) == 0
    pnl = paper.settle(st, {"ticker": "KXTEST-1", "status": "finalized", "result": "yes"}, t0 + 10, log)
    assert pnl == pytest.approx(10 - pos.cost)
    assert st.cash == pytest.approx(100 - pos.cost + 10)
    assert st.wins == 1 and not st.positions


def test_paper_loss_and_void(tmp_path):
    log = paper.Journal(tmp_path / "j.jsonl")
    st = paper.State(cash=50.0, positions={"A": paper.Position("A", "E", "no", 5, 4.6),
                                           "B": paper.Position("B", "E", "yes", 5, 4.6)})
    assert paper.settle(st, {"ticker": "A", "status": "settled", "result": "yes"}, 0, log) == -4.6
    assert paper.settle(st, {"ticker": "B", "status": "settled", "result": "void"}, 0, log) == 0
    assert paper.settle(st, {"ticker": "C", "status": "open", "result": ""}, 0, log) is None
    assert st.cash == pytest.approx(54.6)


def test_place_refuses_without_cash(tmp_path):
    st = paper.State(cash=5.0)
    q = model.Quote("X", "E", "yes", 0.9, 10, 0.93, 0.02, 0.89, 0.92, 0, "", "")
    assert paper.place(st, q, 0, paper.Journal(tmp_path / "j")) is None


class FakeAPI:
    """Stands in for requests.Session against the Kalshi REST paths the bot uses."""

    def __init__(self):
        self.trades = []
        self.market = mk()
        self.calls = []

    def get(self, url, params=None, headers=None, timeout=None):
        path = url.split("/trade-api/v2")[1]
        self.calls.append(("GET", path))
        if path == "/markets":
            body = {"markets": [self.market], "cursor": ""}
        elif path.endswith("/orderbook"):
            body = BOOK
        elif path == "/markets/trades":
            body = {"trades": self.trades, "cursor": ""}
        elif path.startswith("/markets/"):
            body = {"market": self.market}
        else:
            raise AssertionError(path)
        return type("R", (), {"status_code": 200, "json": lambda s: body, "text": ""})()

    def __getattr__(self, name):  # any non-GET verb is a bug in a read-only bot
        raise AssertionError(f"unexpected HTTP method {name}")


def test_paper_cycle_end_to_end(tmp_path):
    api = FakeAPI()
    client = KalshiClient(base_url="https://x/trade-api/v2", session=api, min_interval=0)
    cfg = model.Config()
    sp, jp = tmp_path / "s.json", tmp_path / "j.jsonl"
    st = runner.paper_cycle(client, cfg, sp, jp, verbose=False)
    assert len(st.orders) == 1
    o = next(iter(st.orders.values()))
    assert (o.side, o.price) == ("yes", 0.90)
    # same book next cycle: keep the order (queue priority), no churn
    st = runner.paper_cycle(client, cfg, sp, jp, verbose=False)
    assert [x.id for x in st.orders.values()] == [o.id]
    # tape trades through our bid -> filled
    api.trades = [_trade("z", 0.85, "no", 1000, int(NOW.timestamp()) + 5)]
    st = runner.paper_cycle(client, cfg, sp, jp, verbose=False)
    assert st.positions["KXTEST-1"].contracts == o.remaining
    # market settles YES -> profit
    api.market = {**mk(), "status": "finalized", "result": "yes"}
    st = runner.paper_cycle(client, cfg, sp, jp, verbose=False)
    assert not st.positions and st.realized > 0
    assert all(m == "GET" for m, _ in api.calls)


def test_sign_roundtrip():
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding, rsa
    import base64

    k = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    sig = sign(k, "1700000000000", "get", "/trade-api/v2/portfolio/balance?x=1")
    k.public_key().verify(base64.b64decode(sig), b"1700000000000GET/trade-api/v2/portfolio/balance",
                          padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.DIGEST_LENGTH),
                          hashes.SHA256())


def test_calibration_buckets():
    rows = [(0.05, False)] * 95 + [(0.05, True)] * 2 + [(0.4, True)] * 40 + [(0.4, False)] * 60
    b = bucketize(rows)
    lo = b[0]
    assert lo["n"] == 97 and lo["ratio"] < 0.5 and lo["fav_edge_maker"] > 0
    tbl = ratio_table(b)
    assert tbl[-1] == [0.5, 1.0] and len(tbl) == 3
