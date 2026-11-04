"""Copy-trading (paper): mirror trades of chosen Kalshi leaderboard traders.

Signals arrive from anything that can POST JSON or text (a phone-notification forwarder,
an email parser, a profile poller) or are appended to a JSONL inbox file. Each signal is:

    {"trader": "name", "ticker": "KX...", "side": "yes"|"no", "action": "buy"|"sell",
     "price": 0.62, "contracts": 120, "ts": 1793750000}

`ticker` may be replaced by `"market": "<market title as shown in the app>"`; it is resolved
against open markets by fuzzy title match. Plain notification text such as
"alice bought 120 Yes on Will X happen? at 62¢" is parsed too.

Copies are taker fills at the current best ask (speed matters more than a few ticks), guarded by:
trader allowlist, signal age, max slippage vs the leader's price, price band, $ caps.
Every copy logs leader price vs our fill, so you can measure how much edge survives the delay.
"""
from __future__ import annotations

import difflib
import json
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .client import KalshiClient, KalshiError
from .model import fee, parse_book, r2
from .paper import Journal, Position, State, settle


@dataclass
class Signal:
    trader: str
    side: str
    action: str = "buy"
    ticker: str = ""
    market: str = ""
    price: float | None = None
    contracts: float | None = None
    ts: int = 0


@dataclass
class CopyConfig:
    traders: dict[str, float] = field(default_factory=dict)  # name (lowercase) -> size multiplier
    usd_per_trade: float = 10.0
    max_slippage: float = 0.03        # skip if our ask > leader price + this
    max_age_sec: int = 300            # skip stale signals
    min_price: float = 0.10           # avoid longshots (they lose >60% on average)
    max_price: float = 0.95
    max_per_market: float = 30.0
    max_per_trader: float = 150.0
    max_total_exposure: float = 300.0
    copy_sells: bool = True
    taker_fee_rate: float = 0.07
    starting_cash: float = 1000.0
    live: bool = False                # real orders; also needs --live on the command line
    max_drawdown_usd: float = 10.0    # live: stop buying once balance+cost of open copies falls this far
    min_contracts: int = 1
    kill_file: str = "data/STOP"      # live: create this file to stop new buys immediately

    @classmethod
    def load(cls, path: str | None) -> "CopyConfig":
        if path and Path(path).exists():
            d = json.loads(Path(path).read_text())
            d["traders"] = {k.lower(): float(v) for k, v in d.get("traders", {}).items()}
            return cls(**d)
        return cls()


# -- parsing ------------------------------------------------------------------------------------
TEXT_RE = re.compile(
    r"@?(?P<trader>[\w.\-]+)\s+(?P<action>bought|sold|buys|sells|bet)\s+"
    r"(?:\$?(?P<contracts>[\d,.]+)\s+(?:contracts?\s+(?:of\s+)?)?)?"
    r"(?P<side>yes|no)\b\s*(?:on|in|for)?\s*(?P<market>.+?)"
    r"(?:\s+(?:at|@)\s+(?P<price>[\d.]+)\s*(?P<unit>¢|c|cents|\$)?)?\s*$",
    re.I,
)


def parse_signal(raw: str | dict, now: int | None = None) -> Signal:
    now = now or int(time.time())
    if isinstance(raw, str):
        s = raw.strip()
        if s.startswith("{"):
            raw = json.loads(s)
        else:
            m = TEXT_RE.search(s)
            if not m:
                raise ValueError(f"unparseable signal: {s[:120]!r}")
            px = m["price"]
            p = float(px) if px else None
            if p is not None and (m["unit"] in ("¢", "c", "cents") or p > 1):
                p /= 100
            act = m["action"].lower()
            return Signal(
                trader=m["trader"].lower(), side=m["side"].lower(),
                action="sell" if act.startswith("sel") or act == "sold" else "buy",
                market=m["market"].strip(" .'\""), price=p,
                contracts=float(m["contracts"].replace(",", "")) if m["contracts"] else None, ts=now)
    d = raw
    p = d.get("price")
    p = None if p is None else float(p)
    if p is not None and p > 1:
        p /= 100
    return Signal(trader=str(d["trader"]).lower(), side=str(d["side"]).lower(),
                  action=str(d.get("action", "buy")).lower(), ticker=d.get("ticker", ""),
                  market=d.get("market", ""), price=p,
                  contracts=None if d.get("contracts") is None else float(d["contracts"]),
                  ts=int(d.get("ts") or now))


class Resolver:
    """Market title -> ticker, from the open-markets list (refreshed every `ttl` seconds)."""

    def __init__(self, client: KalshiClient, ttl: int = 900):
        self.client, self.ttl, self.at, self.index = client, ttl, 0.0, []

    def _refresh(self):
        if time.time() - self.at < self.ttl and self.index:
            return
        idx = []
        for m in self.client.markets(status="open", mve_filter="exclude"):
            for name in {m.get("title", ""), f"{m.get('title', '')} {m.get('yes_sub_title', '')}".strip()}:
                if name:
                    idx.append((name.lower(), m["ticker"]))
        self.index, self.at = idx, time.time()

    def resolve(self, title: str, cutoff: float = 0.8) -> str | None:
        self._refresh()
        return best_match(title, self.index, cutoff)


def best_match(title: str, index: list[tuple[str, str]], cutoff: float = 0.8) -> str | None:
    t = title.lower().strip()
    best, score = None, 0.0
    for name, ticker in index:
        r = 1.0 if name == t else difflib.SequenceMatcher(None, t, name).ratio()
        if r > score:
            best, score = ticker, r
    return best if score >= cutoff else None


# -- engine -------------------------------------------------------------------------------------
class CopyEngine:
    def __init__(self, client: KalshiClient, cfg: CopyConfig, state_path: Path, journal_path: Path,
                 resolver: Resolver | None = None, live: bool = False):
        self.client, self.cfg = client, cfg
        self.live = live
        if live and not (cfg.live and client.allow_trading):
            raise SystemExit('live needs "live": true in the copy config, --live, and Kalshi API keys')
        self.state_path = state_path
        self.state = State.load(state_path, cfg.starting_cash)
        self.log = Journal(journal_path)
        self.resolver = resolver or Resolver(client)
        self.owner_path = state_path.with_suffix(".owners.json")
        self.owner: dict[str, str] = (json.loads(self.owner_path.read_text())  # ticker -> trader copied
                                      if self.owner_path.exists() else {})
        self.start_path = state_path.with_suffix(".start.json")
        if live:
            bal = client.balance_usd()
            if not self.start_path.exists():  # equity at first live start = drawdown reference
                self.start_path.write_text(json.dumps({"equity": bal, "ts": int(time.time())}))
            self.state.cash = bal
            self.log("live_start", ts=int(time.time()), balance=bal)

    def _live_block(self) -> str | None:
        if Path(self.cfg.kill_file).exists():
            return "kill_switch"
        start = json.loads(self.start_path.read_text())["equity"]
        equity = self.state.cash + sum(p.cost for p in self.state.positions.values())
        if equity < start - self.cfg.max_drawdown_usd:
            return "drawdown_limit"
        return None

    def save(self) -> None:
        self.state.save(self.state_path)
        self.owner = {t: o for t, o in self.owner.items() if t in self.state.positions}
        self.owner_path.write_text(json.dumps(self.owner))

    def _trader_exposure(self, trader: str) -> float:
        return sum(p.cost for t, p in self.state.positions.items() if self.owner.get(t) == trader)

    def skip(self, sig: Signal, reason: str, **kw) -> dict:
        out = {"result": "skip", "reason": reason, **asdict(sig), **kw}
        self.log("copy_skip", **out)
        return out

    def handle(self, sig: Signal, now: int | None = None) -> dict:
        now = now or int(time.time())
        cfg = self.cfg
        if sig.trader not in cfg.traders:
            return self.skip(sig, "trader_not_followed")
        if sig.side not in ("yes", "no"):
            return self.skip(sig, "bad_side")
        if now - sig.ts > cfg.max_age_sec:
            return self.skip(sig, "stale", age=now - sig.ts)
        ticker = sig.ticker or (self.resolver.resolve(sig.market) if sig.market else None)
        if not ticker:
            return self.skip(sig, "market_not_resolved")
        try:
            book = parse_book(self.client.orderbook(ticker))
        except KalshiError as e:
            return self.skip(sig, "orderbook_error", err=str(e))
        out = self._sell(sig, ticker, book, now) if sig.action == "sell" else self._buy(sig, ticker, book, now)
        self.save()
        return out

    def _buy(self, sig: Signal, ticker: str, book, now: int) -> dict:
        cfg, st = self.cfg, self.state
        ask = book.best_ask(sig.side)
        if ask is None:
            return self.skip(sig, "no_ask", ticker=ticker)
        held = st.positions.get(ticker)
        if held and held.side != sig.side:
            return self.skip(sig, "holding_other_side", ticker=ticker)
        if not cfg.min_price <= ask <= cfg.max_price:
            return self.skip(sig, "price_band", ticker=ticker, ask=ask)
        if sig.price is not None and ask > sig.price + cfg.max_slippage + 1e-9:
            return self.skip(sig, "slippage", ticker=ticker, ask=ask)
        if self.live:
            st.cash = self.client.balance_usd()  # refresh first: the drawdown check uses it
            block = self._live_block()
            if block:
                return self.skip(sig, block, ticker=ticker)
        unit = ask + fee(100, ask, cfg.taker_fee_rate) / 100
        budget = min(
            cfg.usd_per_trade * cfg.traders[sig.trader],
            cfg.max_per_market - (held.cost if held else 0),
            cfg.max_per_trader - self._trader_exposure(sig.trader),
            cfg.max_total_exposure - sum(p.cost for p in st.positions.values()),
            st.cash,
        )
        # don't take more than is offered at the best ask (we are not walking the book in paper)
        offered = book.size_at("no" if sig.side == "yes" else "yes", r2(1 - ask))
        n = int(min(budget / unit, offered or 0))
        if n < max(1, cfg.min_contracts):
            return self.skip(sig, "no_room_or_liquidity", ticker=ticker, ask=ask, offered=offered)
        fill_px, f = ask, fee(n, ask, cfg.taker_fee_rate)
        order_id = None
        if self.live:
            limit = r2(min(cfg.max_price, ask if sig.price is None else max(ask, min(sig.price + cfg.max_slippage, ask + 0.01))))
            try:
                ok, note = self.client.ensure_shard_funds(ticker, n * limit + fee(n, limit, cfg.taker_fee_rate) + 0.02)
            except KalshiError as e:
                ok, note = False, str(e)
            self.log("shard_funding", ts=now, ticker=ticker, ok=ok, note=note)
            if not ok:
                return self.skip(sig, "shard_funding", ticker=ticker, err=note)
            try:
                if sig.side == "yes":
                    res = self.client.create_order(ticker, "bid", n, limit)
                else:
                    res = self.client.create_order(ticker, "ask", n, r2(1 - limit))
            except KalshiError as e:
                return self.skip(sig, "order_error", ticker=ticker, err=str(e))
            self.log("order", ts=now, ticker=ticker, side=sig.side, n=n, limit=limit, response=res)
            filled = int(float(res.get("fill_count") or 0))
            if filled < 1:
                return self.skip(sig, "no_fill", ticker=ticker, limit=limit)
            yes_px = float(res.get("average_fill_price") or (limit if sig.side == "yes" else 1 - limit))
            fill_px = yes_px if sig.side == "yes" else r2(1 - yes_px)
            f = round(float(res.get("average_fee_paid") or 0) * filled, 4)
            n, order_id = filled, res.get("order_id")
        cost = r2(n * fill_px + f)
        st.cash = r2(st.cash - cost)
        pos = st.positions.setdefault(ticker, Position(ticker, ticker.rsplit("-", 1)[0], sig.side))
        pos.contracts += n
        pos.cost = r2(pos.cost + cost)
        self.owner[ticker] = sig.trader
        out = {"result": "copied", "live": self.live, "order_id": order_id, "ticker": ticker, "side": sig.side,
               "contracts": n, "fill": fill_px, "fee": f, "leader_price": sig.price,
               "slippage": None if sig.price is None else r2(fill_px - sig.price),
               "delay_sec": now - sig.ts, "trader": sig.trader}
        self.log("copy_buy", ts=now, **out)
        return out

    def _sell(self, sig: Signal, ticker: str, book, now: int) -> dict:
        st = self.state
        pos = st.positions.get(ticker)
        if not self.cfg.copy_sells or pos is None or pos.side != sig.side:
            return self.skip(sig, "nothing_to_sell", ticker=ticker)
        bid = book.best_bid(sig.side)
        if bid is None:
            return self.skip(sig, "no_bid", ticker=ticker)
        n = pos.contracts
        fill_px, f = bid, fee(n, bid, self.cfg.taker_fee_rate)
        if self.live:
            held = self.client.position_count(ticker)
            n = int(held if sig.side == "yes" else -held) if held else 0
            n = max(0, min(n, pos.contracts))
            if n < 1:
                del st.positions[ticker]
                return self.skip(sig, "position_gone", ticker=ticker)
            floor = max(0.01, r2(bid - 0.02))  # accept up to 2c below the bid to get out
            try:
                if sig.side == "yes":
                    res = self.client.create_order(ticker, "ask", n, floor, reduce_only=True)
                else:
                    res = self.client.create_order(ticker, "bid", n, r2(1 - floor), reduce_only=True)
            except KalshiError as e:
                return self.skip(sig, "order_error", ticker=ticker, err=str(e))
            self.log("order", ts=now, ticker=ticker, side=sig.side, n=n, sell_floor=floor, response=res)
            filled = int(float(res.get("fill_count") or 0))
            if filled < 1:
                return self.skip(sig, "no_fill", ticker=ticker)
            yes_px = float(res.get("average_fill_price") or (floor if sig.side == "yes" else 1 - floor))
            fill_px = yes_px if sig.side == "yes" else r2(1 - yes_px)
            f = round(float(res.get("average_fee_paid") or 0) * filled, 4)
            if filled < pos.contracts:  # partial exit: keep the rest on the books
                part_cost = r2(pos.cost * filled / pos.contracts)
                proceeds = r2(filled * fill_px - f)
                pos.contracts -= filled
                pos.cost = r2(pos.cost - part_cost)
                st.cash = r2(st.cash + proceeds)
                st.realized = r2(st.realized + proceeds - part_cost)
                out = {"result": "partial_close", "ticker": ticker, "contracts": filled, "fill": fill_px,
                       "pnl": r2(proceeds - part_cost), "trader": sig.trader}
                self.log("copy_sell", ts=now, **out)
                return out
            n = filled
        proceeds = r2(n * fill_px - f)
        pnl = r2(proceeds - pos.cost)
        st.cash = r2(st.cash + proceeds)
        st.realized = r2(st.realized + pnl)
        st.wins += pnl > 0
        st.losses += pnl < 0
        del st.positions[ticker]
        out = {"result": "closed", "live": self.live, "ticker": ticker, "contracts": n, "fill": fill_px, "pnl": pnl,
               "trader": sig.trader}
        self.log("copy_sell", ts=now, **out)
        return out

    def settle_all(self) -> None:
        now = int(time.time())
        for t in list(self.state.positions):
            try:
                settle(self.state, self.client.market(t), now, self.log)
            except KalshiError as e:
                self.log("error", ts=now, ticker=t, err=str(e))
        self.save()


# -- inputs -------------------------------------------------------------------------------------
def serve(engine: CopyEngine, host: str, port: int, token: str | None) -> None:
    """POST /signal with a JSON or plain-text body. Header `X-Token` must match if a token is set."""
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    import threading

    lock = threading.Lock()

    class H(BaseHTTPRequestHandler):
        def do_POST(self):
            if self.path.rstrip("/") != "/signal":
                return self._send(404, {"error": "POST /signal"})
            if token and self.headers.get("X-Token") != token:
                return self._send(401, {"error": "bad token"})
            body = self.rfile.read(int(self.headers.get("Content-Length") or 0)).decode("utf-8", "replace")
            try:
                sig = parse_signal(body)
                with lock:
                    out = engine.handle(sig)
            except Exception as e:
                engine.log("signal_error", ts=int(time.time()), body=body[:500], err=repr(e))
                return self._send(400, {"error": str(e)})
            print(json.dumps(out))
            self._send(200, out)

        def _send(self, code, obj):
            b = json.dumps(obj).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)

        def log_message(self, *a):
            pass

    def settler():
        while True:
            time.sleep(300)
            with lock:
                engine.settle_all()

    threading.Thread(target=settler, daemon=True).start()
    print(f"copy bot (paper) listening on http://{host}:{port}/signal")
    ThreadingHTTPServer((host, port), H).serve_forever()


def tail_inbox(engine: CopyEngine, path: Path, poll: float = 2.0) -> None:
    """Follow a JSONL/text file, one signal per line (e.g. written by an email or notification forwarder)."""
    path.touch()
    last_settle = 0.0
    with path.open() as f:
        f.seek(0, 2)
        while True:
            line = f.readline()
            if not line:
                if time.time() - last_settle > 300:
                    engine.settle_all()
                    last_settle = time.time()
                time.sleep(poll)
                continue
            if line.strip():
                try:
                    print(json.dumps(engine.handle(parse_signal(line))))
                except Exception as e:
                    engine.log("signal_error", ts=int(time.time()), body=line[:500], err=repr(e))
                    print("bad signal:", e)
