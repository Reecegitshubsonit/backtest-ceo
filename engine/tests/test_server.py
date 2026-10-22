from fastapi.testclient import TestClient

from backtestceo.bars import Bar, DataError
from backtestceo.server import create_app


class FakeClient:
    has_keys = True

    def bars(self, asset, symbol, tf, start, end):
        if symbol == "NONE":
            return []
        if symbol == "BAD":
            raise DataError("ALPACA_REJECTED", "nope", 400)
        return [Bar("2026-10-20T13:30:00Z", 1, 2, 0.5, 1.5, 100)]

    def expirations(self, underlying, on):
        return ["2026-10-23"]

    def chain(self, underlying, expiration, on):
        return {"underlying": underlying, "expiration": expiration, "underlying_close": 600.0, "contracts": []}


http = TestClient(create_app(FakeClient()))
Q = "/api/bars?asset=etfs&tf=5Min&start=2026-10-20&end=2026-10-20&symbol="


def test_health():
    assert http.get("/api/health").json() == {"ok": True, "alpaca_keys_present": True}


def test_bars_ok_and_symbol_uppercased():
    body = http.get(Q + "spy").json()
    assert body["symbol"] == "SPY" and body["bars"][0] == {"t": "2026-10-20T13:30:00Z", "o": 1, "h": 2, "l": 0.5, "c": 1.5, "v": 100}


def test_bad_asset():
    r = http.get("/api/bars?asset=futures&symbol=ES&tf=5Min&start=2026-10-20&end=2026-10-20")
    assert r.status_code == 400 and r.json()["code"] == "BAD_ASSET"


def test_bad_timeframe():
    r = http.get("/api/bars?asset=etfs&symbol=SPY&tf=2Min&start=2026-10-20&end=2026-10-20")
    assert r.json()["code"] == "BAD_TIMEFRAME"


def test_bad_date():
    r = http.get("/api/bars?asset=etfs&symbol=SPY&tf=5Min&start=10/20/2026&end=2026-10-20")
    assert r.status_code == 400 and r.json()["code"] == "BAD_DATE"


def test_empty_is_404():
    r = http.get(Q + "NONE")
    assert r.status_code == 404 and r.json()["code"] == "EMPTY"


def test_data_error_passthrough():
    r = http.get(Q + "BAD")
    assert r.status_code == 400 and r.json() == {"code": "ALPACA_REJECTED", "message": "nope"}


def test_expirations_and_chain():
    assert http.get("/api/options/expirations?underlying=spy&on=2026-10-20").json()["expirations"] == ["2026-10-23"]
    body = http.get("/api/options/chain?underlying=spy&expiration=2026-10-23&on=2026-10-20").json()
    assert body["underlying"] == "SPY" and body["underlying_close"] == 600.0
