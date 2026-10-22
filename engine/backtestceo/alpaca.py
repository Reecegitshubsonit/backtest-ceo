import json
import os
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests

from .bars import Bar, DataError, parse_rows

DATA = "https://data.alpaca.markets"
TRADING = "https://paper-api.alpaca.markets"  # only the read-only contracts listing is used
OPTIONS_START = date(2024, 2, 1)
EXPIRY_WINDOW_DAYS = 60
BAR_URLS = {
    "stocks": DATA + "/v2/stocks/bars",
    "etfs": DATA + "/v2/stocks/bars",
    "crypto": DATA + "/v1beta3/crypto/us/bars",
    "options": DATA + "/v1beta1/options/bars",
}
CONTRACTS_URL = TRADING + "/v2/options/contracts"


def _today() -> date:
    return datetime.now(timezone.utc).date()


def _message(r) -> str:
    try:
        return str(r.json().get("message") or r.text[:200])
    except Exception:
        return r.text[:200]


def _too_early(on: date) -> None:
    if on < OPTIONS_START:
        raise DataError("OPTIONS_TOO_EARLY", "Alpaca options history starts 2024-02-01.")


class Alpaca:
    """Read-only Alpaca market data. Ranges that are fully in the past are cached on disk and never refetched."""

    def __init__(self, cache_dir, key=None, secret=None, session=None, sleep=time.sleep, today=_today):
        self.cache = Path(cache_dir)
        self.cache.mkdir(parents=True, exist_ok=True)
        self.key = key if key is not None else os.environ.get("ALPACA_API_KEY", "")
        self.secret = secret if secret is not None else os.environ.get("ALPACA_SECRET_KEY", "")
        self.http = session or requests.Session()
        self.sleep, self.today = sleep, today

    @property
    def has_keys(self) -> bool:
        return bool(self.key and self.secret)

    def _get(self, url: str, params: dict) -> dict:
        if not self.has_keys:
            raise DataError("NO_KEYS", "Alpaca keys missing: set ALPACA_API_KEY and ALPACA_SECRET_KEY for the engine.", 503)
        headers = {"APCA-API-KEY-ID": self.key, "APCA-API-SECRET-KEY": self.secret}
        for attempt in range(5):
            try:
                r = self.http.get(url, headers=headers, params=params, timeout=60)
            except requests.RequestException as e:
                raise DataError("NETWORK", f"Could not reach Alpaca ({e.__class__.__name__}).", 502)
            if r.status_code == 200:
                return r.json()
            if r.status_code == 429:
                self.sleep(2 ** attempt)
                continue
            if r.status_code in (401, 403):
                raise DataError("ALPACA_AUTH", "Alpaca refused the keys (check they are valid and have market data access).", 502)
            raise DataError("ALPACA_REJECTED", f"Alpaca answered {r.status_code}: {_message(r)}", 400)
        raise DataError("ALPACA_RATE_LIMIT", "Alpaca rate limit: try again in a minute.", 503)

    def _paged(self, url: str, params: dict, collect) -> list:
        out, token = [], None
        while True:
            body = self._get(url, {**params, **({"page_token": token} if token else {})})
            out += collect(body)
            token = body.get("next_page_token")
            if not token:
                return out

    def _cached(self, name: str, done: bool, loader):
        path = self.cache / (name.replace("/", "_") + ".json")
        if path.exists():
            return json.loads(path.read_text())
        data = loader()
        if done:
            path.write_text(json.dumps(data))
        return data

    def bars(self, asset: str, symbol: str, tf: str, start: date, end: date) -> list[Bar]:
        if end < start:
            raise DataError("BAD_RANGE", "End date is before start date.")
        if asset == "options":
            _too_early(start)
        params = dict(symbols=symbol, timeframe=tf, start=f"{start}T00:00:00Z",
                      end=f"{end + timedelta(days=1)}T00:00:00Z", limit=10000)
        if asset in ("stocks", "etfs"):
            params.update(adjustment="split", feed="sip")
        rows = self._cached(f"bars-{asset}-{symbol}-{tf}-{start}-{end}", end < self.today(),
                            lambda: self._paged(BAR_URLS[asset], params, lambda b: (b.get("bars") or {}).get(symbol, [])))
        return parse_rows(rows)

    def _contracts(self, underlying: str, **filters) -> list[dict]:
        rows: list[dict] = []
        for status in ("active", "inactive"):  # inactive = expired, needed for past dates
            rows += self._paged(CONTRACTS_URL, dict(underlying_symbols=underlying, status=status, limit=10000, **filters),
                                lambda b: b.get("option_contracts") or [])
        return rows

    def expirations(self, underlying: str, on: date) -> list[str]:
        """Expiration dates within 60 days after `on`, from contracts active then or expired since."""
        _too_early(on)
        hi = on + timedelta(days=EXPIRY_WINDOW_DAYS)

        def load():
            rows = self._contracts(underlying, expiration_date_gte=str(on), expiration_date_lte=str(hi))
            return sorted({r["expiration_date"] for r in rows})

        return self._cached(f"exp-{underlying}-{on}", hi < self.today(), load)

    def chain(self, underlying: str, expiration: str, on: date) -> dict:
        _too_early(on)

        def load():
            seen = {}
            for r in self._contracts(underlying, expiration_date=expiration):
                seen[r["symbol"]] = {"symbol": r["symbol"], "type": r["type"], "strike": float(r["strike_price"])}
            return sorted(seen.values(), key=lambda x: (x["strike"], x["type"]))

        contracts = self._cached(f"chain-{underlying}-{expiration}", date.fromisoformat(expiration) < self.today(), load)
        daily = self.bars("etfs", underlying, "1Day", on, on)
        return {"underlying": underlying, "expiration": expiration,
                "underlying_close": daily[-1].c if daily else None, "contracts": contracts}
