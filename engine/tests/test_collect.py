import csv
import gzip
from datetime import date

from backtestceo.collect import Collector, classify, flat, parse_etf_flags, safe, write_csv
from backtestceo.bars import DataError

ROW = {"t": "2026-10-20T04:00:00Z", "o": 1, "h": 2, "l": 0.5, "c": 1.5, "v": 100, "n": 3, "vw": 1.2}


def read(path):
    return list(csv.DictReader(gzip.decompress(path.read_bytes()).decode().splitlines()))


def test_parse_etf_flags_reads_the_etf_column():
    text = "Nasdaq Traded|Symbol|Security Name|ETF\nY|SPY|SPDR|Y\nY|AAPL|Apple|N\nFile Creation Time: x"
    assert parse_etf_flags(text) == {"SPY"}


def test_classify_drops_otc_and_keeps_active_listing_of_reused_ticker():
    assets = [
        {"symbol": "ABC", "exchange": "NYSE", "status": "active", "attributes": ["has_options"]},
        {"symbol": "ABC", "exchange": "NASDAQ", "status": "inactive", "attributes": []},
        {"symbol": "SPY", "exchange": "ARCA", "status": "active", "attributes": []},
        {"symbol": "PINK", "exchange": "OTC", "status": "active", "attributes": []},
        {"symbol": "003CVR016", "exchange": "NYSE", "status": "inactive", "attributes": []},
        {"symbol": "AET_DELISTED", "exchange": "NYSE", "status": "inactive", "attributes": []},
        {"symbol": "F011876", "exchange": "NYSE", "status": "inactive", "attributes": []},
    ]
    rows = classify(assets, {"SPY"})
    assert [(r["symbol"], r["class"], r["status"], r["has_options"]) for r in rows] == [
        ("ABC", "stocks", "active", True), ("SPY", "etfs", "active", False)]


def test_safe_names_crypto_pairs():
    assert safe("BTC/USD") == "BTC-USD"


def test_write_csv_writes_header_only_for_no_bars(tmp_path):
    p = tmp_path / "a" / "X.csv.gz"
    assert write_csv(p, ["t", "c"], []) == 0
    assert gzip.decompress(p.read_bytes()).decode().strip() == "t,c"


class FakeApi:
    requests = 0

    def __init__(self, answer):
        self.answer = answer

    def _get(self, url, params):
        return self.answer(params["symbols"].split(","))


def test_batch_retries_singly_when_one_symbol_rejects_the_batch(tmp_path):
    def answer(symbols):
        if "BAD" in symbols:
            raise DataError("ALPACA_REJECTED", "invalid symbol")
        return {"bars": {s: [ROW] for s in symbols}}

    c = Collector(FakeApi(answer), tmp_path, False, date(2026, 10, 26))
    c.batch("stocks/1Day", "u", ["A", "BAD", "C"], "1Day", date(2026, 1, 1), lambda s: tmp_path / f"{s}.csv.gz", 100)
    assert read(tmp_path / "A.csv.gz")[0]["c"] == "1.5"
    assert (tmp_path / "C.csv.gz").exists() and not (tmp_path / "BAD.csv.gz").exists()
    assert c.log["failed"] == [{"group": "stocks/1Day", "symbol": "BAD", "error": "invalid symbol"}]


def test_batch_skips_existing_files_unless_refresh(tmp_path):
    asked = []

    def answer(symbols):
        asked.extend(symbols)
        return {"bars": {}}

    (tmp_path / "A.csv.gz").write_bytes(b"")
    c = Collector(FakeApi(answer), tmp_path, False, date(2026, 10, 26))
    c.batch("g", "u", ["A", "B"], "1Day", date(2026, 1, 1), lambda s: tmp_path / f"{s}.csv.gz", 100)
    assert asked == ["B"]


def test_flat_dots_nested_fields_and_joins_lists():
    snap = {"latestQuote": {"bp": 1.0, "ap": 1.1}, "greeks": {"delta": 0.5}, "impliedVolatility": 0.2}
    assert flat(snap) == {"latestQuote.bp": 1.0, "latestQuote.ap": 1.1, "greeks.delta": 0.5, "impliedVolatility": 0.2}
    assert flat({"c": [" ", "F", "I"], "p": 2}) == {"c": "  F I", "p": 2}


def test_batch_stops_at_yesterday_so_no_partial_bar_is_saved(tmp_path):
    ends = []

    class Api(FakeApi):
        def _get(self, url, params):
            ends.append(params["end"])
            return {"bars": {}}

    c = Collector(Api(None), tmp_path, False, date(2026, 10, 26))
    c.batch("g", "u", ["A"], "1Day", date(2026, 1, 1), lambda s: tmp_path / f"{s}.csv.gz", 100)
    assert ends == ["2026-10-26T00:00:00Z"]
