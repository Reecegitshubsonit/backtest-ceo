"""Bars for the runner. Live: Alpaca market data (read-only host data.alpaca.markets). Dry run: replayed CSV bars
with a simulated clock. Only COMPLETED bars (bar start + length <= now) are ever returned."""
import csv
from datetime import datetime, timedelta, timezone

from .safety import DATA_HOSTS, assert_host

DATA = "https://data.alpaca.markets"


def _parse_ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


class AlpacaData:
    def __init__(self, key, secret, feed="iex", session=None):
        import requests
        self.http = session or requests.Session()
        self._headers = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret} if key and secret else {}
        self.feed = feed or "iex"

    def __repr__(self):
        return "AlpacaData(data.alpaca.markets)"

    def _get(self, path, params):
        url = DATA + path
        assert_host(url, DATA_HOSTS)
        out, token = [], None
        while True:
            p = dict(params, **({"page_token": token} if token else {}))
            r = self.http.get(url, headers=self._headers, params=p, timeout=30)
            if r.status_code != 200:
                raise RuntimeError(f"Alpaca data {path} -> {r.status_code}")
            body = r.json()
            yield body
            token = body.get("next_page_token")
            if not token:
                return

    def _bars(self, path, symbol, tf, start, now, extra):
        rows = []
        for body in self._get(path, dict(symbols=symbol, timeframe=tf, start=start.strftime("%Y-%m-%dT%H:%M:%SZ"), limit=10000, sort="asc", **extra)):
            rows += (body.get("bars") or {}).get(symbol, [])
        return [dict(ts=_parse_ts(b["t"]), o=float(b["o"]), h=float(b["h"]), l=float(b["l"]), c=float(b["c"]), v=float(b.get("v", 0))) for b in rows]

    def bars(self, symbol, minutes, now, lookback):
        tf = {60: "1Hour", 5: "5Min"}[minutes]
        start = now - lookback
        if "/" in symbol:
            bars = self._bars("/v1beta3/crypto/us/bars", symbol, tf, start, now, {})
        else:
            bars = self._bars("/v2/stocks/bars", symbol, tf, start, now, dict(feed=self.feed, adjustment="split"))
        step = timedelta(minutes=minutes)
        return [b for b in bars if b["ts"] + step <= now]

    def last_price(self, symbol):
        if "/" in symbol:
            body = next(self._get("/v1beta3/crypto/us/latest/trades", dict(symbols=symbol)))
            return float(body["trades"][symbol]["p"])
        return self.quote(symbol)["mid"]

    def quote(self, symbol):
        """Latest stock quote (bid/ask). IEX feed by default: free accounts get IEX in real time."""
        body = next(self._get(f"/v2/stocks/{symbol}/quotes/latest", dict(feed=self.feed)))
        q = body.get("quote") or {}
        bid, ask = float(q.get("bp") or 0), float(q.get("ap") or 0)
        if bid <= 0 or ask <= 0:
            raise RuntimeError(f"no usable {symbol} quote (bid/ask missing)")
        return dict(bid=bid, ask=ask, mid=round((bid + ask) / 2, 4), time=q.get("t"))


def load_csv(path):
    with open(path) as f:
        return [dict(ts=datetime.fromisoformat(r["ts"]).astimezone(timezone.utc), o=float(r["open"]), h=float(r["high"]),
                     l=float(r["low"]), c=float(r["close"]), v=float(r["volume"])) for r in csv.DictReader(f)]


class ReplayData:
    """Dry-run data: {(symbol, minutes): [bars]} replayed against a simulated clock."""

    def __init__(self, series):
        self.series = series
        self.now = None

    def bars(self, symbol, minutes, now, lookback):
        step = timedelta(minutes=minutes)
        return [b for b in self.series.get((symbol, minutes), []) if now - lookback <= b["ts"] and b["ts"] + step <= now]

    def last_price(self, symbol):
        for (s, m), bars in self.series.items():
            if s == symbol:
                done = [b for b in bars if b["ts"] + timedelta(minutes=m) <= self.now]
                if done:
                    return done[-1]["c"]
        raise RuntimeError(f"no replay price for {symbol}")

    def quote(self, symbol):
        p = self.last_price(symbol)
        return dict(bid=round(p - 0.01, 2), ask=round(p + 0.01, 2), mid=p, time=self.now.isoformat())
