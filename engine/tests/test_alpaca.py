import json
from datetime import date

import pytest
import requests

from backtestceo.alpaca import Alpaca
from backtestceo.bars import Bar, DataError

TODAY = date(2026, 10, 21)
ROW = {"t": "2026-10-20T13:30:00Z", "o": 1, "h": 2, "l": 0.5, "c": 1.5, "v": 100}


class Resp:
    def __init__(self, status, body):
        self.status_code, self._body = status, body

    def json(self):
        return self._body

    @property
    def text(self):
        return json.dumps(self._body)


class FakeSession:
    def __init__(self, responses):
        self.responses, self.calls = list(responses), []

    def get(self, url, headers=None, params=None, timeout=None):
        self.calls.append((url, dict(params)))
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


def make(tmp_path, responses, key="k", secret="s"):
    s = FakeSession(responses)
    return Alpaca(tmp_path, key=key, secret=secret, session=s, sleep=lambda _: None, today=lambda: TODAY), s


def bars_body(sym, rows, token=None):
    return Resp(200, {"bars": {sym: rows}, "next_page_token": token})


def test_etf_bars_parse_and_params(tmp_path):
    a, s = make(tmp_path, [bars_body("SPY", [ROW])])
    assert a.bars("etfs", "SPY", "5Min", date(2026, 10, 20), date(2026, 10, 20)) == [Bar("2026-10-20T13:30:00Z", 1, 2, 0.5, 1.5, 100)]
    url, p = s.calls[0]
    assert url.endswith("/v2/stocks/bars")
    assert p["feed"] == "sip" and p["timeframe"] == "5Min"
    assert p["start"] == "2026-10-20T00:00:00Z" and p["end"] == "2026-10-21T00:00:00Z"


def test_crypto_uses_crypto_endpoint(tmp_path):
    a, s = make(tmp_path, [bars_body("BTC/USD", [ROW])])
    assert len(a.bars("crypto", "BTC/USD", "1Hour", date(2026, 10, 1), date(2026, 10, 2))) == 1
    url, p = s.calls[0]
    assert url.endswith("/v1beta3/crypto/us/bars") and "feed" not in p


def test_options_endpoint(tmp_path):
    a, s = make(tmp_path, [bars_body("SPY261120C00600000", [ROW])])
    a.bars("options", "SPY261120C00600000", "1Min", date(2026, 10, 20), date(2026, 10, 20))
    assert s.calls[0][0].endswith("/v1beta1/options/bars")


def test_paging_follows_token(tmp_path):
    a, s = make(tmp_path, [bars_body("SPY", [ROW], "p2"), bars_body("SPY", [ROW])])
    assert len(a.bars("stocks", "SPY", "1Min", date(2026, 10, 20), date(2026, 10, 20))) == 2
    assert s.calls[1][1]["page_token"] == "p2"


def test_completed_range_is_cached(tmp_path):
    a, s = make(tmp_path, [bars_body("SPY", [ROW])])
    a.bars("stocks", "SPY", "1Min", date(2026, 10, 20), date(2026, 10, 20))
    assert len(a.bars("stocks", "SPY", "1Min", date(2026, 10, 20), date(2026, 10, 20))) == 1
    assert len(s.calls) == 1


def test_range_ending_today_is_not_cached(tmp_path):
    a, s = make(tmp_path, [bars_body("SPY", [ROW]), bars_body("SPY", [ROW])])
    a.bars("stocks", "SPY", "1Min", TODAY, TODAY)
    a.bars("stocks", "SPY", "1Min", TODAY, TODAY)
    assert len(s.calls) == 2


def test_options_before_2024_02_refused(tmp_path):
    a, s = make(tmp_path, [])
    with pytest.raises(DataError) as e:
        a.bars("options", "SPY240119C00470000", "1Min", date(2024, 1, 10), date(2024, 1, 10))
    assert e.value.code == "OPTIONS_TOO_EARLY" and not s.calls


def test_bad_range(tmp_path):
    a, _ = make(tmp_path, [])
    with pytest.raises(DataError) as e:
        a.bars("stocks", "SPY", "1Min", date(2026, 10, 20), date(2026, 10, 19))
    assert e.value.code == "BAD_RANGE"


def test_missing_keys(tmp_path):
    a, _ = make(tmp_path, [], key="", secret="")
    assert not a.has_keys
    with pytest.raises(DataError) as e:
        a.bars("stocks", "SPY", "1Min", date(2026, 10, 20), date(2026, 10, 20))
    assert e.value.code == "NO_KEYS" and e.value.status == 503


def test_auth_error(tmp_path):
    a, _ = make(tmp_path, [Resp(403, {"message": "forbidden"})])
    with pytest.raises(DataError) as e:
        a.bars("stocks", "SPY", "1Min", date(2026, 10, 20), date(2026, 10, 20))
    assert e.value.code == "ALPACA_AUTH"


def test_rejected_carries_alpaca_message(tmp_path):
    a, _ = make(tmp_path, [Resp(422, {"message": "invalid symbol"})])
    with pytest.raises(DataError) as e:
        a.bars("stocks", "ZZZZ", "1Min", date(2026, 10, 20), date(2026, 10, 20))
    assert e.value.code == "ALPACA_REJECTED" and "invalid symbol" in e.value.message


def test_rate_limit_retries(tmp_path):
    a, s = make(tmp_path, [Resp(429, {}), bars_body("SPY", [ROW])])
    assert len(a.bars("stocks", "SPY", "1Min", date(2026, 10, 20), date(2026, 10, 20))) == 1
    assert len(s.calls) == 2


def test_rate_limit_gives_up(tmp_path):
    a, _ = make(tmp_path, [Resp(429, {})] * 5)
    with pytest.raises(DataError) as e:
        a.bars("stocks", "SPY", "1Min", date(2026, 10, 20), date(2026, 10, 20))
    assert e.value.code == "ALPACA_RATE_LIMIT"


def test_network_error(tmp_path):
    a, _ = make(tmp_path, [requests.ConnectionError("down")])
    with pytest.raises(DataError) as e:
        a.bars("stocks", "SPY", "1Min", date(2026, 10, 20), date(2026, 10, 20))
    assert e.value.code == "NETWORK"


def contracts(*rows, token=None):
    return Resp(200, {"option_contracts": list(rows), "next_page_token": token})


def c(sym, exp, typ, strike):
    return {"symbol": sym, "expiration_date": exp, "type": typ, "strike_price": str(strike)}


def test_expirations_merge_active_and_expired(tmp_path):
    a, s = make(tmp_path, [
        contracts(c("A", "2026-10-23", "call", 600), c("B", "2026-10-30", "put", 600)),
        contracts(c("C", "2026-10-23", "put", 590)),
    ])
    assert a.expirations("SPY", date(2026, 10, 20)) == ["2026-10-23", "2026-10-30"]
    assert [p["status"] for _, p in s.calls] == ["active", "inactive"]
    assert s.calls[0][1]["expiration_date_gte"] == "2026-10-20"
    assert s.calls[0][1]["expiration_date_lte"] == "2026-12-19"


def test_expirations_too_early(tmp_path):
    a, _ = make(tmp_path, [])
    with pytest.raises(DataError) as e:
        a.expirations("SPY", date(2023, 12, 1))
    assert e.value.code == "OPTIONS_TOO_EARLY"


def test_chain_sorted_deduped_with_underlying_close(tmp_path):
    a, s = make(tmp_path, [
        contracts(c("SPY261023P00600000", "2026-10-23", "put", 600), c("SPY261023C00590000", "2026-10-23", "call", 590)),
        contracts(c("SPY261023C00600000", "2026-10-23", "call", 600), c("SPY261023P00600000", "2026-10-23", "put", 600)),
        bars_body("SPY", [{**ROW, "c": 598.5}]),
    ])
    out = a.chain("SPY", "2026-10-23", date(2026, 10, 20))
    assert out["underlying_close"] == 598.5
    assert [(x["strike"], x["type"]) for x in out["contracts"]] == [(590.0, "call"), (600.0, "call"), (600.0, "put")]
    assert s.calls[0][1]["expiration_date"] == "2026-10-23"
    assert s.calls[2][1]["timeframe"] == "1Day"
