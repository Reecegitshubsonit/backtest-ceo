"""Brokers. Every order goes through Broker.submit(), which checks the kill switch and the host allowlist
immediately before anything is sent. Only paper/sandbox endpoints exist in this file."""
import itertools
import logging
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .safety import ALPACA_PAPER_URL, ORDER_HOSTS, WEBULL_SANDBOX_HOST, KillSwitchEngaged, SafetyError, assert_host


def new_client_order_id(prefix=""):
    return (prefix.replace("_", "")[:8] + uuid.uuid4().hex)[:32]


class Broker:
    name = "base"
    host = ""

    def __init__(self, kill_check):
        self.kill_check = kill_check

    def submit(self, symbol, side, *, qty=None, notional=None, order_type="market", limit_price=None,
               extended_hours=False, client_order_id=None):
        """side: buy | sell | short | cover. Returns dict(client_order_id, status, filled_qty, filled_price)."""
        if self.kill_check():
            raise KillSwitchEngaged("PAPER_TRADING_KILL_SWITCH is on: order not sent")
        assert_host("https://" + self.host, ORDER_HOSTS)
        if (qty is None) == (notional is None):
            raise ValueError("give exactly one of qty or notional")
        return self._submit(symbol, side, qty=qty, notional=notional, order_type=order_type, limit_price=limit_price,
                            extended_hours=extended_hours, client_order_id=client_order_id or new_client_order_id())

    def wait_fill(self, client_order_id, timeout=20.0, sleep=time.sleep):
        end = time.monotonic() + timeout
        o = self.get_order(client_order_id)
        while o["status"] not in ("filled", "rejected", "canceled", "failed") and time.monotonic() < end:
            sleep(1.0)
            o = self.get_order(client_order_id)
        return o


class FakeBroker(Broker):
    """Dry-run broker: fills market orders immediately at price_fn(symbol); limit orders fill if marketable."""

    def __init__(self, name, price_fn, kill_check=lambda: False, reject=False):
        super().__init__(kill_check)
        self.name, self.host, self.price_fn, self.reject = name, ("paper-api.alpaca.markets" if name == "alpaca" else WEBULL_SANDBOX_HOST), price_fn, reject
        self.orders = {}
        self.counter = itertools.count(1)

    def _submit(self, symbol, side, *, qty, notional, order_type, limit_price, extended_hours, client_order_id):
        px = self.price_fn(symbol)
        if self.reject:
            o = dict(client_order_id=client_order_id, status="rejected", filled_qty=0.0, filled_price=None, message="fake reject")
        else:
            q = qty if qty is not None else round(notional / px, 9)
            marketable = order_type == "market" or (side in ("buy", "cover") and limit_price >= px) or (side in ("sell", "short") and limit_price <= px)
            o = dict(client_order_id=client_order_id, status="filled" if marketable else "new", filled_qty=q if marketable else 0.0,
                     filled_price=px if marketable else None, qty=q)
        o.update(symbol=symbol, side=side, order_type=order_type, limit_price=limit_price, extended_hours=extended_hours,
                 time=datetime.now(timezone.utc).isoformat())
        self.orders[client_order_id] = o
        return dict(o)

    def get_order(self, client_order_id):
        return dict(self.orders[client_order_id])

    def cancel(self, client_order_id):
        o = self.orders[client_order_id]
        if o["status"] == "new":
            o["status"] = "canceled"
        return dict(o)


class AlpacaPaperBroker(Broker):
    """Alpaca paper trading REST v2 (https://paper-api.alpaca.markets). Crypto: market orders, time_in_force gtc,
    notional buys, qty sells. Alpaca crypto cannot be sold short, so the runner never sends 'short' here."""
    name, host = "alpaca", "paper-api.alpaca.markets"

    def __init__(self, key, secret, kill_check, session=None):
        super().__init__(kill_check)
        if not key or not secret:
            raise SafetyError("Alpaca paper keys missing (ALPACA_PAPER_API_KEY/ALPACA_API_KEY and the matching secret)")
        import requests
        self.base = ALPACA_PAPER_URL
        assert_host(self.base, ORDER_HOSTS)
        self.http = session or requests.Session()
        self._headers = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}

    def __repr__(self):
        return "AlpacaPaperBroker(paper-api.alpaca.markets)"

    def _req(self, method, path, **kw):
        url = self.base + path
        assert_host(url, ORDER_HOSTS)
        r = self.http.request(method, url, headers=self._headers, timeout=20, **kw)
        if r.status_code >= 400:
            try:
                msg = r.json().get("message", "")
            except Exception:
                msg = r.text[:200]
            raise RuntimeError(f"Alpaca paper {method} {path} -> {r.status_code}: {msg}")
        return r.json() if r.content else {}

    @staticmethod
    def _norm(o):
        st = o.get("status", "")
        return dict(client_order_id=o.get("client_order_id"), status="failed" if st in ("expired", "suspended") else st,
                    filled_qty=float(o.get("filled_qty") or 0), filled_price=float(o["filled_avg_price"]) if o.get("filled_avg_price") else None,
                    broker_order_id=o.get("id"))

    def _submit(self, symbol, side, *, qty, notional, order_type, limit_price, extended_hours, client_order_id):
        if side == "short":
            raise SafetyError("Alpaca crypto is long-only: short orders are not sent")
        body = dict(symbol=symbol, side="buy" if side in ("buy", "cover") else "sell", type=order_type,
                    time_in_force="gtc" if "/" in symbol else "day", client_order_id=client_order_id)
        body.update(qty=str(qty)) if qty is not None else body.update(notional=str(round(notional, 2)))
        if order_type == "limit":
            body["limit_price"] = str(limit_price)
        if extended_hours and "/" not in symbol:
            body["extended_hours"] = True
        return self._norm(self._req("POST", "/v2/orders", json=body))

    def get_order(self, client_order_id):
        return self._norm(self._req("GET", "/v2/orders:by_client_order_id", params=dict(client_order_id=client_order_id)))

    def cancel(self, client_order_id):
        o = self.get_order(client_order_id)
        if o.get("broker_order_id") and o["status"] not in ("filled", "canceled"):
            self._req("DELETE", f"/v2/orders/{o['broker_order_id']}")
        return self.get_order(client_order_id)

    def account(self):
        a = self._req("GET", "/v2/account")
        return dict(status=a.get("status"), cash=a.get("cash"), equity=a.get("equity"))


_WB_STATUS = {"FILLED": "filled", "PARTIAL_FILLED": "partially_filled", "CANCELLED": "canceled", "FAILED": "failed",
              "SUBMITTED": "new", "PENDING": "new"}


class WebullSandboxBroker(Broker):
    """Webull OpenAPI test environment via the official SDK (pip install webull-openapi-python-sdk), endpoint
    pinned to api.sandbox.webull.com. Stock orders: trade_client.order_v3.place_order(account_id, [order])."""
    name, host = "webull", WEBULL_SANDBOX_HOST

    def __init__(self, app_key, app_secret, account_id, kill_check, region="us", token_dir=None, sdk=None):
        super().__init__(kill_check)
        if not app_key or not app_secret:
            raise SafetyError("Webull sandbox keys missing (WEBULL_APP_KEY / WEBULL_APP_SECRET)")
        if sdk is None:
            try:
                from webull.core.client import ApiClient
                from webull.trade.trade_client import TradeClient
            except ImportError as e:
                raise SafetyError("Webull SDK not installed: .venv/bin/pip install webull-openapi-python-sdk") from e
        else:
            ApiClient, TradeClient = sdk
        # The SDK logs request/response headers at DEBUG (they include the app key and token): keep it quiet.
        for n in ("webull", "webull.core", "webull.trade"):
            logging.getLogger(n).setLevel(logging.WARNING)
        api = ApiClient(app_key, app_secret, region)
        api._stream_logger_set = True  # stops TradeClient attaching DEBUG stdout + file loggers
        api._file_logger_set = True
        api.add_endpoint(region, WEBULL_SANDBOX_HOST)  # without this the SDK defaults to production api.webull.com
        if token_dir:
            Path(token_dir).mkdir(parents=True, exist_ok=True)
            api.set_token_dir(str(token_dir))
        self._check_endpoint(api, region)
        self.trade = TradeClient(api)  # contacts the sandbox (token config / 2FA token check)
        self.account_id = account_id or self._first_account()

    def __repr__(self):
        return "WebullSandboxBroker(api.sandbox.webull.com)"

    @staticmethod
    def _check_endpoint(api, region):
        resolver = getattr(api, "_endpoint_resolver", None)
        try:
            from webull.core.endpoint.resolver_endpoint_request import ResolveEndpointRequest
            got = resolver.resolve(ResolveEndpointRequest(region))
        except Exception:
            got = WEBULL_SANDBOX_HOST if resolver is None else None  # test doubles
        if got and got != WEBULL_SANDBOX_HOST:
            raise SafetyError(f"Webull SDK resolved {got}, not the sandbox")

    def _first_account(self):
        r = self.trade.account_v2.get_account_list()
        if r.status_code != 200:
            raise RuntimeError(f"Webull sandbox account list -> {r.status_code}")
        body = r.json()
        rows = body if isinstance(body, list) else (body.get("data") or body.get("accounts") or [])
        if not rows:
            raise RuntimeError("Webull sandbox returned no accounts")
        return rows[0].get("account_id")

    def order_body(self, symbol, side, *, qty, notional, order_type, limit_price, extended_hours, client_order_id):
        o = dict(combo_type="NORMAL", client_order_id=client_order_id, symbol=symbol, instrument_type="EQUITY", market="US",
                 order_type="LIMIT" if order_type == "limit" else "MARKET", side={"buy": "BUY", "cover": "BUY", "sell": "SELL", "short": "SHORT"}[side],
                 time_in_force="DAY", support_trading_session="ALL" if extended_hours else "CORE")
        if notional is not None:
            o.update(entrust_type="AMOUNT", total_cash_amount=f"{notional:.2f}")
        else:
            o.update(entrust_type="QTY", quantity=str(qty))
        if order_type == "limit":
            o["limit_price"] = f"{limit_price:.2f}"
        if extended_hours and order_type != "limit":
            raise SafetyError("Webull extended-hours orders must be LIMIT orders")
        return o

    def _submit(self, symbol, side, **kw):
        body = self.order_body(symbol, side, **kw)
        r = self.trade.order_v3.place_order(self.account_id, [body])
        if r.status_code != 200:
            raise RuntimeError(f"Webull sandbox place_order -> {r.status_code}: {str(r.text)[:200]}")
        return self.get_order(kw["client_order_id"])

    def preview(self, symbol, side, **kw):
        body = self.order_body(symbol, side, client_order_id=kw.pop("client_order_id", new_client_order_id()), **kw)
        r = self.trade.order_v3.preview_order(self.account_id, [body])
        return r.status_code, (r.json() if r.status_code == 200 else str(r.text)[:200])

    def get_order(self, client_order_id):
        r = self.trade.order_v3.get_order_detail(self.account_id, client_order_id)
        if r.status_code != 200:
            return dict(client_order_id=client_order_id, status="unknown", filled_qty=0.0, filled_price=None)
        body = r.json() or {}
        o = (body.get("orders") or [body])[0]
        return dict(client_order_id=client_order_id, status=_WB_STATUS.get(o.get("status"), str(o.get("status", "unknown")).lower()),
                    filled_qty=float(o.get("filled_quantity") or 0), filled_price=float(o["filled_price"]) if o.get("filled_price") not in (None, "", "0") else None,
                    broker_order_id=o.get("order_id"))

    def cancel(self, client_order_id):
        self.trade.order_v3.cancel_order(self.account_id, client_order_id)
        return self.get_order(client_order_id)
