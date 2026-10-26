"""Bulk download of Alpaca history into data/{stocks,etfs,crypto,options} as gzipped CSV.

    .venv/bin/python -m backtestceo.collect [--only stocks,etfs,crypto,options] [--out DIR] [--refresh]

Resumable: a file that exists is skipped unless --refresh. Files are written whole (tmp then rename),
so an interrupted run never leaves a half file. A symbol with no bars gets a header-only file.
"""
import argparse
import csv
import gzip
import io
import json
import os
import re
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests

from .alpaca import BAR_URLS, CONTRACTS_URL, DATA, OPTIONS_START, TRADING, Alpaca
from .bars import DataError

ROOT = Path(__file__).resolve().parents[2]
EQUITY_START = date(2016, 1, 1)  # earliest SIP bar Alpaca serves
CRYPTO_START = date(2021, 1, 1)
NASDAQ_TRADED = "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqtraded.txt"  # only source of the ETF flag
INTRADAY_EQUITIES = ["SPY", "QQQ", "IWM", "DIA", "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "AMD"]
INTRADAY_CRYPTO = ["BTC/USD", "ETH/USD", "SOL/USD"]
OPTION_UNDERLYINGS = ["SPY", "QQQ", "IWM", "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "AMD"]
BAR_FIELDS = ["t", "o", "h", "l", "c", "v", "n", "vw"]
CONTRACT_FIELDS = ["symbol", "root_symbol", "type", "style", "strike_price", "expiration_date", "multiplier", "status",
                   "open_interest", "open_interest_date", "close_price", "close_price_date"]
NEWS_FIELDS = ["id", "created_at", "updated_at", "headline", "summary", "author", "source", "url", "symbols"]
TICK_FIELDS = {
    "stocks/trades": ["symbol", "t", "x", "p", "s", "c", "i", "z"],
    "stocks/quotes": ["symbol", "t", "bx", "bp", "bs", "ax", "ap", "as", "c", "z"],
    "crypto/trades": ["symbol", "t", "p", "s", "i", "tks"],
    "crypto/quotes": ["symbol", "t", "bp", "bs", "ap", "as"],
    "options/trades": ["symbol", "t", "x", "p", "s", "c"],
}
ACTION_SYMBOL_KEYS = ("symbol", "acquiree_symbol", "old_symbol", "source_symbol", "target_symbol")
TICKER = re.compile(r"^[A-Z]+(\.[A-Z]+)?$")  # e.g. AAPL, BRK.B, ABR.PRA
PER_MINUTE = 190  # free plan allows 200 requests a minute; keep a margin


def safe(symbol: str) -> str:
    return symbol.replace("/", "-")


def flat(row: dict, prefix: str = "") -> dict:
    """One CSV row from nested JSON: dicts become dotted columns, lists become space-joined text."""
    out = {}
    for k, v in row.items():
        if isinstance(v, dict):
            out.update(flat(v, f"{prefix}{k}."))
        elif isinstance(v, list):
            out[prefix + k] = " ".join(str(x) for x in v)
        else:
            out[prefix + k] = v
    return out


def write_csv(path: Path, fields: list[str], rows) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore")
    w.writeheader()
    n = 0
    for r in rows:
        w.writerow(r)
        n += 1
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(gzip.compress(buf.getvalue().encode()))
    tmp.replace(path)
    return n


def classify(assets: list[dict], etf_symbols: set[str]) -> list[dict]:
    """Alpaca equities minus OTC, each tagged etfs or stocks by the Nasdaq Trader ETF flag."""
    out: dict = {}
    for a in assets:
        if a["exchange"] == "OTC" or (a["symbol"] in out and out[a["symbol"]]["status"] == "active"):
            continue  # a reused ticker keeps its active listing
        if not TICKER.match(a["symbol"]):
            continue  # CUSIP-style rights/escrow lines and "_DELISTED" aliases: the data API rejects them
        out[a["symbol"]] = {"symbol": a["symbol"], "name": a.get("name", ""), "exchange": a["exchange"],
                            "status": a["status"], "class": "etfs" if a["symbol"] in etf_symbols else "stocks",
                            "has_options": "has_options" in (a.get("attributes") or [])}
    return sorted(out.values(), key=lambda r: r["symbol"])


def parse_etf_flags(text: str) -> set[str]:
    lines = text.splitlines()
    head = lines[0].split("|")
    sym, etf = head.index("Symbol"), head.index("ETF")
    return {p[sym] for p in (l.split("|") for l in lines[1:]) if len(p) > etf and p[etf] == "Y"}


class Throttled(Alpaca):
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.last, self.requests = 0.0, 0

    def _get(self, url, params):
        wait = self.last + 60 / PER_MINUTE - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        self.last = time.monotonic()
        self.requests += 1
        return super()._get(url, params)


class Collector:
    def __init__(self, api: Alpaca, out: Path, refresh: bool, today: date):
        self.api, self.out, self.refresh, self.today = api, out, refresh, today
        self.done = today - timedelta(days=1)  # last whole day: a saved file is never refetched, so no partial bars
        self.log: dict = {"started": datetime.now(timezone.utc).isoformat(timespec="seconds"), "files": {}, "failed": []}
        self.rows: list[dict] | None = None

    def todo(self, path: Path) -> bool:
        return self.refresh or not path.exists()

    def note(self, group: str, n: int) -> None:
        g = self.log["files"].setdefault(group, {"files": 0, "bars": 0})
        g["files"] += 1
        g["bars"] += n

    def bars_by_symbol(self, url: str, symbols: list[str], tf: str, start: date, end: date, **extra) -> dict:
        return self.by_symbol(url, "bars", symbols, start, end, timeframe=tf, **extra)

    def by_symbol(self, url: str, key: str, symbols: list[str], start: date, end: date, **extra) -> dict:
        """Pages a multi-symbol endpoint (bars, trades, quotes, auctions) into {symbol: rows}."""
        # the free plan refuses SIP data from the last 15 minutes, so the range stops 16 minutes ago
        stop = min(datetime.combine(end + timedelta(days=1), datetime.min.time(), timezone.utc),
                   datetime.now(timezone.utc) - timedelta(minutes=16))
        params = dict(symbols=",".join(symbols), start=f"{start}T00:00:00Z",
                      end=stop.strftime("%Y-%m-%dT%H:%M:%SZ"), limit=10000, **extra)
        out: dict = {s: [] for s in symbols}
        token = None
        while True:
            body = self.api._get(url, {**params, **({"page_token": token} if token else {})})
            for s, rows in (body.get(key) or {}).items():
                out.setdefault(s, []).extend(rows)
            token = body.get("next_page_token")
            if not token:
                return out

    def batch(self, group: str, url: str, symbols: list[str], tf: str, start: date, dest, size: int, **extra) -> None:
        pending = [s for s in symbols if self.todo(dest(s))]
        print(f"[{group}] {len(pending)} of {len(symbols)} to fetch", flush=True)
        for i in range(0, len(pending), size):
            chunk = pending[i:i + size]
            try:
                got = self.bars_by_symbol(url, chunk, tf, start, self.done, **extra)
            except DataError as e:
                if len(chunk) == 1:
                    print(f"  skip {chunk[0]}: {e.message}", flush=True)
                    self.log["failed"].append({"group": group, "symbol": chunk[0], "error": e.message})
                    continue
                for s in chunk:  # one bad symbol rejects the whole batch; retry singly
                    self.batch(group, url, [s], tf, start, dest, 1, **extra)
                continue
            for s in chunk:
                self.note(group, write_csv(dest(s), BAR_FIELDS, got.get(s, [])))
            print(f"  {group}: {min(i + size, len(pending))}/{len(pending)}  requests={self.api.requests}", flush=True)

    def universe(self) -> list[dict]:
        if self.rows is not None:
            return self.rows
        assets = []
        for status in ("active", "inactive"):
            assets += self.api._get(TRADING + "/v2/assets", {"status": status, "asset_class": "us_equity"})
        etfs = parse_etf_flags(requests.get(NASDAQ_TRADED, timeout=60).text)
        rows = classify(assets, etfs)
        write_csv(self.out / "universe.csv.gz", ["symbol", "name", "exchange", "status", "class", "has_options"], rows)
        self.rows = rows
        return rows

    def kind_of(self, symbol: str) -> str:
        if not hasattr(self, "classes"):
            self.classes = {r["symbol"]: r["class"] for r in self.universe()}
        return self.classes.get(symbol, "stocks")

    def equities(self, kinds: set[str]) -> None:
        rows = self.universe()
        for kind in sorted(kinds & {"stocks", "etfs"}):
            syms = [r["symbol"] for r in rows if r["class"] == kind]
            self.batch(f"{kind}/1Day", BAR_URLS[kind], syms, "1Day", EQUITY_START,
                       lambda s, k=kind: self.out / k / "1Day" / f"{safe(s)}.csv.gz", 100, adjustment="all", feed="sip")
            intraday = [s for s in INTRADAY_EQUITIES if any(r["symbol"] == s and r["class"] == kind for r in rows)]
            self.batch(f"{kind}/1Min", BAR_URLS[kind], intraday, "1Min", EQUITY_START,
                       lambda s, k=kind: self.out / k / "1Min" / f"{safe(s)}.csv.gz", 1, adjustment="all", feed="sip")

    def crypto(self) -> None:
        pairs = sorted(a["symbol"] for a in self.api._get(TRADING + "/v2/assets", {"status": "active", "asset_class": "crypto"}))
        for tf in ("1Day", "1Hour"):
            self.batch(f"crypto/{tf}", BAR_URLS["crypto"], pairs, tf, CRYPTO_START,
                       lambda s, t=tf: self.out / "crypto" / t / f"{safe(s)}.csv.gz", 20)
        self.batch("crypto/1Min", BAR_URLS["crypto"], INTRADAY_CRYPTO, "1Min", CRYPTO_START,
                   lambda s: self.out / "crypto" / "1Min" / f"{safe(s)}.csv.gz", 1)

    def options(self) -> None:
        for u in OPTION_UNDERLYINGS:
            contracts = []
            for status in ("active", "inactive"):
                contracts += self.api._paged(CONTRACTS_URL, dict(underlying_symbols=u, status=status, limit=10000,
                                                                 expiration_date_gte=str(OPTIONS_START)),
                                             lambda b: b.get("option_contracts") or [])
            write_csv(self.out / "options" / "contracts" / f"{u}.csv.gz", CONTRACT_FIELDS,
                      sorted(contracts, key=lambda c: (c["expiration_date"], float(c["strike_price"]), c["type"])))
            by_exp: dict = {}
            for c in contracts:
                by_exp.setdefault(c["expiration_date"], []).append(c["symbol"])
            print(f"[options/{u}] {len(contracts)} contracts, {len(by_exp)} expirations", flush=True)
            for exp in sorted(by_exp):
                path = self.out / "options" / "1Day" / u / f"{exp}.csv.gz"
                live = date.fromisoformat(exp) >= self.today  # still trading: always refetch
                if not (live or self.todo(path)):
                    continue
                syms, rows = by_exp[exp], []
                end = min(date.fromisoformat(exp), self.done)
                try:
                    for i in range(0, len(syms), 100):
                        got = self.bars_by_symbol(BAR_URLS["options"], syms[i:i + 100], "1Day", OPTIONS_START, end)
                        rows += [{"symbol": s, **r} for s, rs in sorted(got.items()) for r in rs]
                except DataError as e:  # leave no file so the next run retries this expiration
                    print(f"  skip {u} {exp}: {e.message}", flush=True)
                    self.log["failed"].append({"group": f"options/{u}", "symbol": exp, "error": e.message})
                    continue
                self.note(f"options/1Day/{u}", write_csv(path, ["symbol"] + BAR_FIELDS, rows))
            print(f"  options/{u} done  requests={self.api.requests}", flush=True)

    def corporate_actions(self) -> None:
        """Dividends, splits, mergers, spin-offs, name changes, delistings, filed under the class of the symbol."""
        found: dict = {}
        for year in range(EQUITY_START.year, self.today.year + 1):
            end = min(date(year, 12, 31), self.today)
            for body in self.pages(DATA + "/v1/corporate-actions", dict(start=f"{year}-01-01", end=str(end), limit=1000)):
                for kind, rows in (body.get("corporate_actions") or {}).items():
                    found.setdefault(kind, []).extend(rows)
        print(f"[corporate_actions] {sum(map(len, found.values()))} actions  requests={self.api.requests}", flush=True)
        for kind, rows in found.items():
            by_class: dict = {}
            for r in rows:
                sym = next((r[k] for k in ACTION_SYMBOL_KEYS if r.get(k)), "")
                by_class.setdefault(self.kind_of(sym), []).append(r)
            for cls, rs in by_class.items():
                fields = sorted({k for r in rs for k in r})
                self.note(f"{cls}/corporate_actions", write_csv(self.out / cls / "corporate_actions" / f"{kind}.csv.gz", fields, rs))

    def pages(self, url: str, params: dict):
        token = None
        while True:
            body = self.api._get(url, {**params, **({"page_token": token} if token else {})})
            yield body
            token = body.get("next_page_token")
            if not token:
                return

    def auctions(self) -> None:
        """Opening and closing auction prints, the real price of a market-on-open or market-on-close order."""
        for s in INTRADAY_EQUITIES:
            path = self.out / self.kind_of(s) / "auctions" / f"{s}.csv.gz"
            if not self.todo(path):
                continue
            days = self.by_symbol(DATA + "/v2/stocks/auctions", "auctions", [s], EQUITY_START, self.done, feed="sip")[s]
            rows = [{"d": d["d"], "auction": label, **flat(x)} for d in days
                    for key, label in (("o", "open"), ("c", "close")) for x in d.get(key) or []]
            self.note("auctions", write_csv(path, ["d", "auction", "t", "x", "p", "s", "c"], rows))
            print(f"  auctions {s}: {len(days)} days  requests={self.api.requests}", flush=True)

    def news(self) -> None:
        for s in sorted(set(INTRADAY_EQUITIES) | set(OPTION_UNDERLYINGS)):
            path = self.out / self.kind_of(s) / "news" / f"{s}.csv.gz"
            if not self.todo(path):
                continue
            rows = [flat(n) for b in self.pages(DATA + "/v1beta1/news", dict(symbols=s, start="2015-01-01T00:00:00Z",
                                                                             sort="asc", limit=50, include_content="false"))
                    for n in b.get("news") or []]
            self.note("news", write_csv(path, NEWS_FIELDS, rows))
            print(f"  news {s}: {len(rows)} articles  requests={self.api.requests}", flush=True)

    def option_snapshots(self) -> None:
        """Today's quote, greeks and implied volatility per contract. Alpaca keeps no history of these,
        so each run adds one day; run daily to build the history."""
        for u in OPTION_UNDERLYINGS:
            rows = [{"symbol": k, **flat(v)} for b in self.pages(DATA + f"/v1beta1/options/snapshots/{u}",
                                                                 dict(feed="indicative", limit=1000))
                    for k, v in (b.get("snapshots") or {}).items()]
            fields = ["symbol"] + sorted({k for r in rows for k in r} - {"symbol"})
            self.note("options/snapshots", write_csv(self.out / "options" / "snapshots" / str(self.today) / f"{u}.csv.gz",
                                                     fields, rows))
            print(f"  snapshots {u}: {len(rows)} contracts  requests={self.api.requests}", flush=True)

    def sessions(self, n: int) -> list[date]:
        cal = self.api._get(TRADING + "/v2/calendar", {"start": str(self.today - timedelta(days=2 * n + 10)),
                                                       "end": str(self.today - timedelta(days=1))})
        return [date.fromisoformat(d["date"]) for d in cal][-n:]

    def tick_day(self, group: str, url: str, key: str, symbols: list[str], day: date, path: Path, fields, **extra) -> None:
        if not self.todo(path):
            return
        rows = []
        try:
            for i in range(0, len(symbols), 100):
                got = self.by_symbol(url, key, symbols[i:i + 100], day, day, **extra)
                rows += [{"symbol": s, **flat(r)} for s, rs in sorted(got.items()) for r in rs]
        except DataError as e:
            print(f"  skip {group} {day}: {e.message}", flush=True)
            self.log["failed"].append({"group": group, "symbol": str(day), "error": e.message})
            return
        self.note(group, write_csv(path, fields, rows))
        print(f"  {group} {day}: {len(rows)} rows  requests={self.api.requests}", flush=True)

    def ticks(self, days: int) -> None:
        """Every trade and every bid/ask quote for the last `days` sessions. Tick volume is huge (SPY quotes run
        to millions a day), so this covers the intraday list only."""
        for day in self.sessions(days):
            for s in INTRADAY_EQUITIES:
                base = self.out / self.kind_of(s)
                for key in ("trades", "quotes"):
                    self.tick_day(f"{key} {s}", DATA + f"/v2/stocks/{key}", key, [s], day,
                                  base / key / s / f"{day}.csv.gz", TICK_FIELDS[f"stocks/{key}"], feed="sip")
            for s in INTRADAY_CRYPTO:
                for key in ("trades", "quotes"):
                    self.tick_day(f"{key} {s}", BAR_URLS["crypto"].replace("bars", key), key, [s], day,
                                  self.out / "crypto" / key / safe(s) / f"{day}.csv.gz", TICK_FIELDS[f"crypto/{key}"])
            for u in OPTION_UNDERLYINGS:
                path = self.out / "options" / "trades" / u / f"{day}.csv.gz"
                if not self.todo(path):
                    continue
                listed = [c["symbol"] for c in self.read_contracts(u) if c["expiration_date"] >= str(day)]
                self.tick_day(f"options/trades {u}", DATA + "/v1beta1/options/trades", "trades", listed, day, path,
                              TICK_FIELDS["options/trades"])

    def read_contracts(self, u: str) -> list[dict]:
        path = self.out / "options" / "contracts" / f"{u}.csv.gz"
        if not path.exists():
            return []
        return list(csv.DictReader(gzip.decompress(path.read_bytes()).decode().splitlines()))


def keys() -> None:
    """Fills ALPACA_ keys from .env files the same way engine/run.sh does."""
    if os.environ.get("ALPACA_API_KEY"):
        return
    for f in (ROOT / ".env", Path.home() / "scalp-city" / ".env"):
        if f.exists():
            for line in f.read_text().splitlines():
                k, _, v = line.partition("=")
                if k in ("ALPACA_API_KEY", "ALPACA_SECRET_KEY"):
                    os.environ[k] = v.strip().strip('"')
            return


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--only", default="stocks,etfs,crypto,options,extras",
                   help="extras = corporate actions, option snapshots, auctions, news, trades and quotes")
    p.add_argument("--tick-days", type=int, default=5, help="sessions of trades and quotes to fetch")
    p.add_argument("--out", default=os.environ.get("BACKTEST_CEO_DATA", str(ROOT / "data")))
    p.add_argument("--refresh", action="store_true", help="refetch files that already exist")
    a = p.parse_args(argv)
    kinds = set(a.only.split(","))
    keys()
    out = Path(a.out)
    api = Throttled(out / ".http-cache")
    c = Collector(api, out, a.refresh, datetime.now(timezone.utc).date())
    try:
        if kinds & {"stocks", "etfs"}:
            c.equities(kinds)
        if "crypto" in kinds:
            c.crypto()
        if "options" in kinds:
            c.options()
        if "extras" in kinds:
            c.corporate_actions()
            c.option_snapshots()
            c.auctions()
            c.news()
            c.ticks(a.tick_days)
    finally:
        c.log["finished"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        c.log["requests"] = api.requests
        (out / f"collect-{c.log['started'][:19].replace(':', '')}.json").write_text(json.dumps(c.log, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
