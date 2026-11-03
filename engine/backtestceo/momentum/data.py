"""Alpaca market data for the momentum scanner: news, daily bars, 1-minute bars. Disk cache for past ranges.

Keys come from ALPACA_API_KEY / ALPACA_SECRET_KEY. When the environment injects credentials at a proxy, any
placeholder value works (the proxy replaces it).
"""
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, time as dtime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

ET = ZoneInfo("America/New_York")
DATA = "https://data.alpaca.markets"
CACHE = Path(os.environ.get("BACKTEST_CEO_CACHE", Path.home() / ".cache" / "backtest-ceo")) / "momentum"


def et_dt(d: date, hhmm: str) -> datetime:
    h, m = map(int, hhmm.split(":"))
    return datetime.combine(d, dtime(h, m), ET)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_t(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


class Data:
    def __init__(self, cache: Path = CACHE, feed: str | None = None, session=None):
        self.cache = Path(cache)
        self.cache.mkdir(parents=True, exist_ok=True)
        self.feed = feed or os.environ.get("ALPACA_DATA_FEED", "sip")
        self.http = session or requests.Session()
        key = os.environ.get("ALPACA_API_KEY") or os.environ.get("APCA_API_KEY_ID") or "placeholder"
        sec = os.environ.get("ALPACA_SECRET_KEY") or os.environ.get("APCA_API_SECRET_KEY") or "placeholder"
        self.headers = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": sec}

    # ---------------------------------------------------------------- http
    def get(self, path: str, params: dict) -> dict:
        for attempt in range(8):
            try:
                r = self.http.get(DATA + path, headers=self.headers, params=params, timeout=60)
            except requests.RequestException:
                time.sleep(2 ** min(attempt, 4))
                continue
            if r.status_code == 200:
                return r.json()
            if r.status_code == 429 or r.status_code >= 500:
                time.sleep(2 ** min(attempt, 5))
                continue
            raise RuntimeError(f"Alpaca {path} -> {r.status_code}: {r.text[:200]}")
        raise RuntimeError(f"Alpaca {path}: gave up after retries")

    def paged(self, path: str, params: dict, key: str):
        token = None
        while True:
            body = self.get(path, {**params, **({"page_token": token} if token else {})})
            yield body.get(key) or ({} if key == "bars" else [])
            token = body.get("next_page_token")
            if not token:
                return

    def _cached(self, name: str, final: bool, fetch):
        p = self.cache / name
        if p.exists():
            return json.loads(p.read_text())
        out = fetch()
        if final:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(out))
        return out

    # ---------------------------------------------------------------- calendar
    def trading_days(self, start: date, end: date) -> list[date]:
        bars = self.daily(["SPY"], start, end, "raw").get("SPY", [])
        return [parse_t(b["t"]).astimezone(ET).date() for b in bars]

    # ---------------------------------------------------------------- news
    def news_window(self, start: datetime, end: datetime) -> list[dict]:
        """Headlines with created_at in [start, end): {id, t, symbols, headline}."""
        out = []
        for page in self.paged("/v1beta1/news", {"start": iso(start), "end": iso(end), "limit": 50, "sort": "asc",
                                                  "include_content": "false", "exclude_contentless": "false"}, "news"):
            out += [{"id": n["id"], "t": n["created_at"], "symbols": n.get("symbols") or [], "headline": n.get("headline", ""),
                     "source": n.get("source", "")} for n in page]
        return out

    def news_for_day(self, d: date, prev: date, until: str = "16:00") -> list[dict]:
        """News from the previous session's 16:00 ET to `until` ET on d (the catalyst window)."""
        start, end = et_dt(prev, "16:00"), et_dt(d, until)
        final = end < datetime.now(timezone.utc) - timedelta(hours=1)
        return self._cached(f"news/{d}_{until.replace(':', '')}.json", final, lambda: self.news_window(start, end))

    # ---------------------------------------------------------------- bars
    def _bars(self, symbols, timeframe, start: datetime, end: datetime, adjustment: str) -> dict[str, list]:
        out: dict[str, list] = {}
        if self.feed == "sip":  # free SIP access excludes the latest 15 minutes
            end = min(end, datetime.now(timezone.utc) - timedelta(minutes=16))
        if end <= start:
            return out
        for i in range(0, len(symbols), 200):
            chunk = symbols[i:i + 200]
            for page in self.paged("/v2/stocks/bars", {"symbols": ",".join(chunk), "timeframe": timeframe, "start": iso(start),
                                                       "end": iso(end), "limit": 10000, "adjustment": adjustment,
                                                       "feed": self.feed, "sort": "asc"}, "bars"):
                for s, rows in page.items():
                    out.setdefault(s, []).extend(rows)
        return out

    def daily(self, symbols, start: date, end: date, adjustment: str = "raw") -> dict[str, list]:
        """Daily bars, no cache key per symbol set: callers cache the universe pull themselves."""
        return self._bars(sorted(set(symbols)), "1Day", et_dt(start, "00:00"), et_dt(end, "23:59"), adjustment)

    def daily_cached(self, symbols, start: date, end: date, adjustment: str, tag: str) -> dict[str, list]:
        final = et_dt(end, "20:00") < datetime.now(timezone.utc)
        stamp = "" if final else "_asof" + datetime.now(ET).strftime("%Y%m%d%H")  # partial day: reuse within the hour
        return self._cached(f"daily/{tag}_{start}_{end}_{adjustment}{stamp}.json", True,
                            lambda: self.daily(symbols, start, end, adjustment))

    def minute(self, symbols, d: date, start: str = "04:00", end: str = "16:00") -> dict[str, list]:
        """1-minute raw bars for d, cached per symbol-day. Returns {sym: [bar...]} (bars: t,o,h,l,c,v,vw)."""
        final = et_dt(d, end) < datetime.now(timezone.utc) - timedelta(minutes=20)
        out, missing = {}, []
        for s in symbols:
            p = self.cache / "minute" / str(d) / f"{s}.json"
            if final and p.exists():
                out[s] = json.loads(p.read_text())
            else:
                missing.append(s)
        if missing:
            got = self._bars(missing, "1Min", et_dt(d, start), et_dt(d, end), "raw")
            for s in missing:
                out[s] = got.get(s, [])
                if final:
                    p = self.cache / "minute" / str(d) / f"{s}.json"
                    p.parent.mkdir(parents=True, exist_ok=True)
                    p.write_text(json.dumps(out[s]))
        return out

    # ---------------------------------------------------------------- live
    def snapshots(self, symbols) -> dict:
        out = {}
        for i in range(0, len(symbols), 200):
            out.update(self.get("/v2/stocks/snapshots", {"symbols": ",".join(symbols[i:i + 200]), "feed": self.feed}))
        return out

    def movers(self, top: int = 50) -> list[str]:
        body = self.get("/v1beta1/screener/stocks/movers", {"top": top})
        return [g["symbol"] for g in body.get("gainers", [])]

    def most_actives(self, top: int = 100) -> list[str]:
        body = self.get("/v1beta1/screener/stocks/most-actives", {"by": "volume", "top": top})
        return [g["symbol"] for g in body.get("most_actives", [])]


def pmap(fn, items, workers: int = 4):
    with ThreadPoolExecutor(workers) as ex:
        return list(ex.map(fn, items))
