"""Kalshi REST client.

Read-only unless constructed with allow_trading=True: the only write is create_order (V2, IOC),
used by the copy engine in live mode. Auth (RSA-PSS) is needed for /portfolio calls.
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
        allow_trading: bool = False,
    ):
        self.allow_trading = allow_trading
        env = os.environ.get("KALSHI_ENV", "prod").lower()
        self.base_url = (base_url or os.environ.get("KALSHI_BASE_URL") or (DEMO if env == "demo" else PROD)).rstrip("/")
        self.key_id = key_id or os.environ.get("KALSHI_API_KEY_ID")
        self.key_path = key_path or os.environ.get("KALSHI_PRIVATE_KEY_PATH")
        self._key = None
        self.min_interval = min_interval
        self._last = 0.0
        self.s = session or requests.Session()

    # -- transport ---------------------------------------------------------------------------
    def _auth_headers(self, path: str, method: str = "GET") -> dict[str, str]:
        if not (self.key_id and self.key_path):
            raise KalshiError("Set KALSHI_API_KEY_ID and KALSHI_PRIVATE_KEY_PATH for portfolio reads")
        if self._key is None:
            self._key = _load_key(self.key_path)
        ts = str(int(time.time() * 1000))
        return {
            "KALSHI-ACCESS-KEY": self.key_id,
            "KALSHI-ACCESS-TIMESTAMP": ts,
            "KALSHI-ACCESS-SIGNATURE": sign(self._key, ts, method, path),
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
                time.sleep(float(r.headers.get("retry-after") or 0) or 0.5 * 2**attempt)
                continue
            if r.status_code != 200:
                raise KalshiError(f"GET {endpoint} -> {r.status_code}: {r.text[:300]}")
            return r.json()
        raise KalshiError(f"GET {endpoint}: retries exhausted")

    def post(self, endpoint: str, body: dict) -> dict:
        """Signed POST. Not retried: a timeout may still have placed the order."""
        if not self.allow_trading:
            raise KalshiError("trading disabled on this client")
        url = self.base_url + endpoint
        path = requests.utils.urlparse(url).path
        headers = {**self._auth_headers(path, "POST"), "Content-Type": "application/json"}
        r = self.s.post(url, json=body, headers=headers, timeout=20)
        if r.status_code not in (200, 201):
            raise KalshiError(f"POST {endpoint} -> {r.status_code}: {r.text[:300]}")
        return r.json()

    def create_order(self, ticker: str, book_side: str, count: int, price: float, reduce_only: bool = False,
                     client_order_id: str | None = None) -> dict:
        """V2 order on the single YES book: 'bid' buys YES, 'ask' sells YES (= buys NO at 1-price).
        Immediate-or-cancel, so nothing is left resting."""
        import uuid

        if book_side not in ("bid", "ask") or count < 1 or not 0.01 <= price <= 0.99:
            raise KalshiError(f"bad order {book_side} {count} @ {price}")
        body = {"ticker": ticker, "side": book_side, "count": str(int(count)), "price": f"{price:.4f}",
                "time_in_force": "immediate_or_cancel", "self_trade_prevention_type": "taker_at_cross",
                "reduce_only": reduce_only, "client_order_id": client_order_id or str(uuid.uuid4())}
        return self.post("/portfolio/events/orders", body)

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

    def positions(self, ticker: str | None = None) -> dict:
        return self.get("/portfolio/positions", {"limit": 1000, "ticker": ticker}, auth=True)

    def shard_balances(self) -> dict[int, float]:
        """Cash per exchange shard (Kalshi splits markets across matching engines, each with its own balance)."""
        out = {}
        for b in self.balance().get("balance_breakdown") or []:
            try:
                out[int(b.get("exchange_index", 0))] = float(b.get("balance") or 0)
            except (TypeError, ValueError):
                pass
        return out

    def market_shard(self, ticker: str) -> int:
        return int(self.market(ticker).get("exchange_index") or 0)

    def transfer_between_shards(self, source: int, dest: int, usd: float) -> dict:
        import uuid

        body = {"source": "event_contract", "destination": "event_contract", "amount": int(round(usd * 10000)),
                "source_exchange_shard": source, "destination_exchange_shard": dest,
                "client_transfer_id": str(uuid.uuid4())}
        return self.post("/portfolio/intra_exchange_instance_transfer", body)

    transfer_wait_s = 15.0

    def ensure_shard_funds(self, ticker: str, need_usd: float, wait_s: float | None = None) -> tuple[bool, str]:
        """API orders don't move money between shards (the app does). Top up the market's shard if short."""
        shard = self.market_shard(ticker)
        bal = self.shard_balances()
        have = bal.get(shard, 0.0)
        if have >= need_usd:
            return True, f"shard {shard} has ${have:.2f}"
        short = round(need_usd - have + 0.05, 2)
        moved = []
        for src, amt in sorted(bal.items(), key=lambda kv: -kv[1]):
            if src == shard or amt <= 0 or short <= 0:
                continue
            take = round(min(amt, short), 2)
            self.transfer_between_shards(src, shard, take)
            moved.append(f"${take:.2f} {src}->{shard}")
            short = round(short - take, 2)
        if short > 0.0001:
            return False, f"total balance too small for ${need_usd:.2f} on shard {shard}"
        deadline = time.time() + (self.transfer_wait_s if wait_s is None else wait_s)
        while time.time() < deadline:  # transfers are processed asynchronously
            if self.shard_balances().get(shard, 0.0) >= need_usd:
                return True, "moved " + ", ".join(moved)
            time.sleep(1.0)
        return False, "transfer not settled in time (" + ", ".join(moved) + ")"

    def balance_usd(self) -> float:
        b = self.balance()
        v = b.get("balance_dollars")
        return float(v) if v is not None else float(b.get("balance", 0)) / 100

    def position_count(self, ticker: str) -> float:
        """Signed contracts held: + YES, - NO."""
        for p in self.positions(ticker).get("market_positions") or []:
            if p.get("ticker") == ticker:
                v = p.get("position_fp", p.get("position"))
                return float(v or 0)
        return 0.0
