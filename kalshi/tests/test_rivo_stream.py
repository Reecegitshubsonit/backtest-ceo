import json
import time

from kalshibot import rivo_stream as rs
from kalshibot.copy import CopyConfig, CopyEngine
from kalshibot.client import KalshiClient
from tests.test_copy import Fake


def frame(**kw):
    f = {"id": "t1", "time": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()),
         "market": {"venue": "kalshi", "venueId": "KXFED-25DEC-T4", "title": "Fed cut?"},
         "outcome": "Yes", "action": "buy", "entry": "open", "price": 0.61, "contracts": 500,
         "trader": {"ref": "kalshi:Alice", "name": "Alice"}}
    f.update(kw)
    return f


def test_sse_parser():
    lines = [": connected", "id: 1:a", "event: trade", 'data: {"x":1}', "", ": ping", "", "event: move", "data: {}", ""]
    assert list(rs.sse_frames(lines)) == [("trade", "1:a", '{"x":1}'), ("move", None, "{}")]


def test_frame_mapping():
    [s] = rs.frame_to_signals(frame())
    assert (s.trader, s.ticker, s.side, s.action, s.price) == ("alice", "KXFED-25DEC-T4", "yes", "buy", 0.61)
    assert rs.frame_to_signals(frame(action="sell", entry="trim")) == []
    assert rs.frame_to_signals(frame(action="sell", entry="close"))[0].action == "sell"
    sell, buy = rs.frame_to_signals(frame(entry="flip", outcome="No"))
    assert (sell.side, sell.action, buy.side, buy.action) == ("yes", "sell", "no", "buy")
    assert rs.frame_to_signals(frame(market={"venue": "polymarket", "venueId": "x"})) == []


def test_handle_frame_dedupes_and_copies(tmp_path):
    client = KalshiClient(base_url="https://x/trade-api/v2", session=Fake(), min_interval=0)
    eng = CopyEngine(client, CopyConfig(traders={"alice": 1.0}), tmp_path / "s.json", tmp_path / "j.jsonl")
    st = rs.StreamState(tmp_path / "rs.json")
    out = rs.handle_frame(eng, st, "1:t1", json.dumps(frame()))
    assert out[0]["result"] == "copied"
    assert rs.handle_frame(eng, st, "1:t1", json.dumps(frame())) == []  # replay ignored
    st2 = rs.StreamState(tmp_path / "rs.json")
    assert st2.last_id == "1:t1" and "t1" in st2.seen
