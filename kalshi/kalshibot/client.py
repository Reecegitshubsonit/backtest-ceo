"""Read-only Kalshi REST client.

Only GET is implemented. There is no code path that creates, amends or cancels an order:
paper mode simulates fills locally. Auth (RSA-PSS) is only needed for /portfolio reads.
"""
from __future__ import annotations

import base64
import os
import time
from pathlib import Path
from typing import Any, Iterator

import requests

PROD = "https://api.elections.kalshi.com/trade-api/v2"
DEMO = "https://demo-api.kalshi.co/trade-api/v2"


class KalshiError(RuntimeError):
    pass


def _load_key(path: str):
    from cryptography.hazmat.primitives import serialization

    return serialization.load_pem_private_key(Path(path).expanduser().read_bytes(), password=None)


def sign(private_key, timestamp_ms: str, method: str, path: str) -> str:
    """RSA-PSS/SHA256 over timestamp + METHOD + path (path includes /trade-api/v2, no query)."""
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding

    msg = f"{timestamp_ms}{method.upper()}{path.split('?')[0]}".encode()
    sig = private_key.sign(
        msg,
        padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.DIGEST_LENGTH),
        hashes.SHA256(),
    )
    return base64.b64encode(sig).decode()


class KalshiClient:
    def __init__(
        self,
        base_url: str | None = None,
        key_id: str | None = None,
        key_path: str | None = None,
        min_interval: float = 0.08,
        session: requests.Session | None = None,
    ):
        env = os.environ.get("KALSHI_ENV", "prod").lower()
        self.base_url = (base_url or os.environ.get("KALSHI_BASE_URL") or (DEMO if env == "demo" else PROD)).rstrip("/")
        self.key_id = key_id or os.environ.get("KALSHI_API_KEY_ID")
        self.key_path = key_path or os.environ.get("KALSHI_PRIVATE_KEY_PATH")
        self._key = None
        self.min_interval = min_interval
        self._last = 0.0
        self.s = session or requests.Session()

    # -- transport ---------------------------------------------------------------------------
    def _auth_headers(self, path: str) -> dict[str, str]:
        if not (self.key_id and self.key_path):
            raise KalshiError("Set KALSHI_API_KEY_ID and KALSHI_PRIVATE_KEY_PATH for portfolio reads")
        if self._key is None:
            self._key = _load_key(self.key_path)
        ts = str(int(time.time() * 1000))
        return {
            "KALSHI-ACCESS-KEY": self.key_id,
            "KALSHI-ACCESS-TIMESTAMP": ts,
            "KALSHI-ACCESS-SIGNATURE": sign(self._key, ts, "GET", path),
        }

    def get(self, endpoint: str, params: dict | None = None, auth: bool = False) -> dict:
        url = self.base_url + endpoint
        path = requests.utils.urlparse(url).path
        params = {k: v for k, v in (params or {}).items() if v is not None}
        for attempt in range(5):
            wait = self.min_interval - (time.monotonic() - self._last)
            if wait > 0:
                time.sleep(wait)
            self._last = time.monotonic()
            headers = self._auth_headers(path) if auth else {}
            r = self.s.get(url, params=params, headers=headers, timeout=20)
            if r.status_code == 429 or r.status_code >= 500:
                time.sleep(0.5 * 2**attempt)
                continue
            if r.status_code != 200:
                raise KalshiError(f"GET {endpoint} -> {r.status_code}: {r.text[:300]}")
            return r.json()
        raise KalshiError(f"GET {endpoint}: retries exhausted")

    def paginate(self, endpoint: str, key: str, params: dict | None = None, max_pages: int = 50) -> Iterator[dict]:
        params = dict(params or {})
        for _ in range(max_pages):
            data = self.get(endpoint, params)
            yield from data.get(key) or []
            cursor = data.get("cursor")
            if not cursor:
                return
            params["cursor"] = cursor

    # -- public market data -----------------------------------------------------------------
    def markets(self, **params: Any) -> Iterator[dict]:
        params.setdefault("limit", 1000)
        return self.paginate("/markets", "markets", params)

    def market(self, ticker: str) -> dict:
        return self.get(f"/markets/{ticker}")["market"]

    def orderbook(self, ticker: str, depth: int = 10) -> dict:
        return self.get(f"/markets/{ticker}/orderbook", {"depth": depth})

    def trades(self, ticker: str | None = None, min_ts: int | None = None, max_ts: int | None = None,
               max_pages: int = 20) -> list[dict]:
        p = {"ticker": ticker, "min_ts": min_ts, "max_ts": max_ts, "limit": 1000}
        return list(self.paginate("/markets/trades", "trades", p, max_pages=max_pages))

    # -- authenticated, read-only ------------------------------------------------------------
    def balance(self) -> dict:
        return self.get("/portfolio/balance", auth=True)

    def positions(self) -> dict:
        return self.get("/portfolio/positions", {"limit": 1000}, auth=True)
