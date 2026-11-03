"""Alpaca PAPER trading loop for the momentum strategy. Same scanner / setup / exit code as the backtest.

    python -m backtestceo.momentum scan                 # one scanner pass, prints in-play symbols
    python -m backtestceo.momentum paper                # dry run: logs the orders it would send
    python -m backtestceo.momentum paper --live         # sends orders to https://paper-api.alpaca.markets only

Each minute (a few seconds after the bar closes):
  1. pull new headlines since the previous close 16:00 ET; news symbols are the universe
  2. snapshots -> keep symbols in the price band and up >= min_gap_pct
  3. rebuild today's 1-min bars from 04:00 for those, replay them through SymbolState (identical to the backtest)
  4. cancel last minute's unfilled entry; if a setup is armed and risk allows, send a buy stop-limit (day TIF)
  5. on a fill: place a sell stop at the pullback low; target / trailing / bar-close exits are managed here
Between minute closes it polls the latest trade every few seconds to take the 2R partial.

Keys: ALPACA_PAPER_API_KEY / ALPACA_API_KEY and the matching secret, from the environment or the repo .env.
--live also requires ALPACA_PAPER_TRADING_ONLY=true. The order host is hard-wired to paper-api.alpaca.markets and
checked before every request. Kill switch: PAPER_TRADING_KILL_SWITCH=1 or a KILL file in the state dir.
Regular-hours entries only (Alpaca rejects stop orders outside 09:30-16:00).
"""
import json
import os
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path

import requests

from ..paper import envfile, safety
from .backtest import Risk, to_bars, tradable_symbol
from .config import Config
from .data import CACHE, ET, Data, et_dt, parse_t
from .engine import is_catalyst, Position, SymbolState, hhmm, size

PAPER = "https://paper-api.alpaca.markets"
REPO = Path(__file__).resolve().parents[3]
STATE = CACHE / "paper"


def log(msg: str) -> None:
    line = f"{datetime.now(ET):%Y-%m-%d %H:%M:%S} {msg}"
    print(line, flush=True)
    STATE.mkdir(parents=True, exist_ok=True)
    with open(STATE / "paper.log", "a") as f:
        f.write(line + "\n")


# ------------------------------------------------------------------ brokers
class AlpacaPaper:
    def __init__(self, env):
        self.key = env.first(envfile.ALPACA_KEY_VARS)
        self.secret = env.first(envfile.ALPACA_SECRET_VARS)
        if not (self.key and self.secret):
            raise safety.SafetyError("Alpaca paper keys missing (ALPACA_PAPER_API_KEY / ALPACA_PAPER_SECRET_KEY)")
        self.http = requests.Session()
        self.env = env

    def __repr__(self):
        return "AlpacaPaper(paper-api.alpaca.markets)"

    def req(self, method, path, **kw):
        url = PAPER + path
        if safety.assert_host(url) != "paper-api.alpaca.markets":
            raise safety.SafetyError("order host must be paper-api.alpaca.markets")
        if method != "GET" and safety.kill_switch_on(self.env, STATE / "KILL", lambda: envfile.read(REPO / ".env")):
            raise safety.KillSwitchEngaged("kill switch on: no orders")
        r = self.http.request(method, url, headers={"APCA-API-KEY-ID": self.key, "APCA-API-SECRET-KEY": self.secret},
                              timeout=20, **kw)
        if r.status_code >= 400:
            raise RuntimeError(f"alpaca {method} {path} -> {r.status_code}: {r.text[:200]}")
        return r.json() if r.text else {}

    def account(self):
        return self.req("GET", "/v2/account")

    def submit(self, **o):
        o.setdefault("client_order_id", "mom-" + uuid.uuid4().hex[:16])
        return self.req("POST", "/v2/orders", json=o)

    def order(self, oid):
        return self.req("GET", f"/v2/orders/{oid}")

    def cancel(self, oid):
        try:
            self.req("DELETE", f"/v2/orders/{oid}")
        except RuntimeError as e:
            log(f"cancel {oid}: {e}")

    def replace(self, oid, **kw):
        return self.req("PATCH", f"/v2/orders/{oid}", json=kw)

    def close(self, sym):
        return self.req("DELETE", f"/v2/positions/{sym}")


class DryRun:
    """Logs orders; fills stop-limit entries / stops / markets from the latest bar so the loop can be exercised."""

    def __init__(self):
        self.orders, self.last = {}, {}

    def __repr__(self):
        return "DryRun(no orders sent)"

    def account(self):
        return {"equity": "dry-run", "buying_power": "dry-run"}

    def submit(self, **o):
        oid = "dry-" + uuid.uuid4().hex[:10]
        o = {**o, "id": oid, "status": "new", "filled_qty": "0", "filled_avg_price": None}
        self.orders[oid] = o
        log(f"DRY order {o['side']} {o['qty']} {o['symbol']} {o['type']} stop={o.get('stop_price')} limit={o.get('limit_price')}")
        if o["type"] == "market":
            self._fill(o, self.last.get(o["symbol"], 0))
        return o

    def _fill(self, o, px):
        o.update(status="filled", filled_qty=str(o["qty"]), filled_avg_price=str(px))

    def tick(self, sym, price):
        """Feed a price: trigger resting dry-run orders."""
        self.last[sym] = price
        for o in self.orders.values():
            if o["symbol"] != sym or o["status"] != "new":
                continue
            sp, lp = float(o.get("stop_price") or 0), float(o.get("limit_price") or 0)
            if o["side"] == "buy" and o["type"] == "stop_limit" and price >= sp and price <= lp:
                self._fill(o, price)
            elif o["side"] == "sell" and o["type"] == "stop" and price <= sp:
                self._fill(o, price)

    def order(self, oid):
        return self.orders[oid]

    def cancel(self, oid):
        if self.orders.get(oid, {}).get("status") == "new":
            self.orders[oid]["status"] = "canceled"

    def replace(self, oid, **kw):
        self.orders[oid].update(kw)
        return self.orders[oid]

    def close(self, sym):
        return {}


# ------------------------------------------------------------------ trader
class Trader:
    def __init__(self, cfg: Config, data: Data, broker, now=lambda: datetime.now(ET)):
        self.cfg, self.data, self.broker, self.now = cfg, data, broker, now
        self.day = now().date()
        days = data.trading_days(self.day - timedelta(days=10), self.day)
        prior = [d for d in days if d < self.day]
        self.prev = prior[-1]
        self.news: dict[str, list] = {}
        self.news_seen: set = set()
        self.news_until = et_dt(self.prev, "16:00")
        self.daily: dict[str, tuple] = {}  # sym -> (prev_close, adv)
        self.risk = Risk(cfg)
        self.entries: dict[str, int] = {}
        self.entry_order: dict | None = None  # {sym, id, setup, shares}
        self.pos: Position | None = None
        self.stop_id: str | None = None
        self.states: dict[str, SymbolState] = {}

    # ---- data
    def poll_news(self):
        end = self.now()
        for n in self.data.news_window(self.news_until - timedelta(minutes=2), end):
            if n["id"] in self.news_seen:
                continue
            self.news_seen.add(n["id"])
            if self.cfg.require_news and not is_catalyst(n["headline"], n["symbols"], self.cfg):
                continue
            for s in n["symbols"]:
                if tradable_symbol(s):
                    self.news.setdefault(s, []).append((parse_t(n["t"]).astimezone(ET), n["headline"]))
        self.news_until = end

    def prev_adv(self, syms):
        need = [s for s in syms if s not in self.daily]
        if not need:
            return
        start = self.day - timedelta(days=int(self.cfg.adv_days * 1.6) + 10)
        bars = self.data.daily(need, start, self.prev, "split")
        for s in need:
            rows = [b for b in bars.get(s, []) if parse_t(b["t"]).astimezone(ET).date() <= self.prev][-self.cfg.adv_days:]
            if len(rows) >= self.cfg.min_history_days and parse_t(rows[-1]["t"]).astimezone(ET).date() == self.prev:
                self.daily[s] = (rows[-1]["c"], sum(b["v"] for b in rows) / len(rows))
            else:
                self.daily[s] = (0.0, 0.0)

    def scan(self) -> dict[str, SymbolState]:
        """Rebuild SymbolStates for news symbols that are in the band and gapping. Returns all in-play ones."""
        c = self.cfg
        self.poll_news()
        syms = sorted(self.news) if c.require_news else sorted(set(self.news) | set(self.data.movers(50)))
        if not syms:
            return {}
        snaps = self.data.snapshots(syms)
        cands = []
        for s, sn in snaps.items():
            px = ((sn or {}).get("latestTrade") or {}).get("p") or ((sn or {}).get("minuteBar") or {}).get("c")
            pc = ((sn or {}).get("prevDailyBar") or {}).get("c")
            if px and pc and c.min_price <= px <= c.max_price and (px / pc - 1) * 100 >= c.min_gap_pct:
                cands.append(s)
        self.prev_adv(cands)
        if self.pos and self.pos.sym not in cands:
            cands.append(self.pos.sym)  # keep managing an open position even if it fell out of the band
        self.prev_adv(cands)
        cands = [s for s in cands if self.daily.get(s, (0, 0))[1] > 0]
        bars = self.data.minute(cands, self.day, "04:00", self.now().strftime("%H:%M")) if cands else {}
        cutoff = self.now().replace(second=0, microsecond=0)
        out = {}
        for s in cands:
            pc, adv = self.daily[s]
            st = SymbolState(s, pc, adv, self.news.get(s, []), c)
            st.entries = self.entries.get(s, 0)
            for b in to_bars(bars.get(s, [])):
                if b.t + timedelta(minutes=1) <= cutoff:  # closed bars only
                    st.update(b)
            if st.in_play_at:
                out[s] = st
        self.states = out
        return out

    # ---- orders
    def on_minute(self):
        c, t = self.cfg, self.now()
        states = self.scan()
        for s, st in states.items():
            b = st.bars[-1]
            log(f"in play {s} since {st.in_play_at:%H:%M} px={b.c:.2f} gap={st.gap_pct(b.c):.1f}% rvol={st.rvol_now:.1f} "
                f"vwap={st.vwap:.2f} macd={st.macd:.3f}")
        self.check_entry_fill()
        if self.entry_order:  # armed for one bar only
            self.broker.cancel(self.entry_order["id"])
            log(f"entry {self.entry_order['sym']} not filled in its bar: canceled")
            self.entry_order = None
        if self.pos:
            self.manage_close(states.get(self.pos.sym))
        if t.time() >= hhmm(c.flatten_at) and self.pos:
            self.exit_all("flatten")
        if self.pos or self.entry_order or not self.risk.can_trade():
            return
        if not (hhmm(max(c.entry_from, "09:30")) <= t.time() <= hhmm(c.entry_until)):
            return
        for s, st in sorted(states.items(), key=lambda kv: -kv[1].rvol_now):
            if st.entries >= c.max_entries_per_symbol:
                continue
            su = st.setup()
            if not su:
                continue
            q = size(su, st, c, self.risk.mult())
            if q < 1:
                continue
            o = self.broker.submit(symbol=s, qty=str(q), side="buy", type="stop_limit", time_in_force="day",
                                   stop_price=f"{su.trigger:.2f}", limit_price=f"{su.limit:.2f}")
            self.entry_order = {"sym": s, "id": o["id"], "setup": su, "shares": q}
            log(f"ARM {su.pattern} {s} buy {q} stop {su.trigger} limit {su.limit} risk-stop {su.stop} "
                f"(gap {su.gap_pct:.1f}% rvol {su.rvol:.1f})")
            break

    def check_entry_fill(self):
        eo = self.entry_order
        if not eo:
            return
        o = self.broker.order(eo["id"])
        filled = int(float(o.get("filled_qty") or 0))
        if filled <= 0:
            return
        if o.get("status") != "filled":
            self.broker.cancel(eo["id"])  # partial: keep what we got
        su = eo["setup"]
        px = float(o["filled_avg_price"])
        self.pos = Position(eo["sym"], su.pattern, px, su.stop, filled, self.now(), su)
        self.entries[eo["sym"]] = self.entries.get(eo["sym"], 0) + 1
        self.risk.trades += 1
        self.entry_order = None
        self.place_stop()
        log(f"FILLED {self.pos.sym} {filled} @ {px:.4f} stop {self.pos.stop} target {self.pos.target_price(self.cfg)}")

    def place_stop(self):
        p = self.pos
        if self.stop_id:
            self.broker.cancel(self.stop_id)
        o = self.broker.submit(symbol=p.sym, qty=str(p.remaining), side="sell", type="stop", time_in_force="day",
                               stop_price=f"{p.stop:.2f}")
        self.stop_id = o["id"]

    def stop_filled(self) -> bool:
        if not self.stop_id:
            return False
        o = self.broker.order(self.stop_id)
        if o.get("status") == "filled":
            self.pos.exit(self.now(), float(o["filled_avg_price"]), int(float(o["filled_qty"])),
                          "trail_stop" if self.pos.partial_done else "stop")
            self.stop_id = None
            self.done()
            return True
        return False

    def sell(self, qty, reason):
        if self.stop_id:
            self.broker.cancel(self.stop_id)
            self.stop_id = None
        o = self.broker.submit(symbol=self.pos.sym, qty=str(qty), side="sell", type="market", time_in_force="day")
        for _ in range(20):
            o = self.broker.order(o["id"])
            if o.get("status") == "filled":
                break
            time.sleep(0.5)
        px = float(o.get("filled_avg_price") or 0) or self.pos.entry
        self.pos.exit(self.now(), px, qty, reason)
        log(f"SELL {qty} {self.pos.sym} @ {px:.4f} ({reason})")

    def exit_all(self, reason):
        if self.pos and self.pos.remaining:
            self.sell(self.pos.remaining, reason)
        self.done()

    def done(self):
        p = self.pos
        if p and p.remaining <= 0:
            self.risk.closed(p.pnl())
            log(f"CLOSED {p.sym} pnl {p.pnl():.2f} day {self.risk.pnl:.2f}{' HALT ' + self.risk.halted if self.risk.halted else ''}")
            with open(STATE / f"trades-{self.day}.jsonl", "a") as f:
                f.write(json.dumps({"sym": p.sym, "pattern": p.pattern, "entry": p.entry, "stop": p.init_stop,
                                    "shares": p.shares, "fills": [(str(a), b, c_, d) for a, b, c_, d in p.fills],
                                    "pnl": round(p.pnl(), 2)}) + "\n")
            self.pos = None

    def on_price(self, price: float):
        """Fast loop: take the partial at target, then move the stop to breakeven."""
        p = self.pos
        if not p or self.stop_filled() or not self.pos:
            return
        if not p.partial_done and price >= p.target_price(self.cfg):
            q = max(1, int(p.shares * self.cfg.partial_frac)) if p.shares > 1 else p.shares
            self.sell(q, "target")
            p.partial_done = True
            p.stop = max(p.stop, round(p.entry, 2))
            if p.remaining:
                self.place_stop()
            else:
                self.done()

    def manage_close(self, st: SymbolState | None):
        p = self.pos
        if self.stop_filled() or not st or not self.pos:
            return
        b = st.bars[-1]
        old = p.stop
        why = p.on_close(b, st, self.cfg)
        if why:
            self.exit_all(why)
        elif p.stop > old and self.stop_id:
            try:
                self.broker.replace(self.stop_id, stop_price=f"{p.stop:.2f}")
            except RuntimeError:
                self.place_stop()


def latest_price(data: Data, sym: str) -> float | None:
    try:
        return data.get("/v2/stocks/trades/latest", {"symbols": sym, "feed": data.feed})["trades"][sym]["p"]
    except Exception:
        return None


def main(a, cfg: Config):
    env = envfile.load(REPO / ".env", os.environ)
    feed = env.get("ALPACA_DATA_FEED") or "iex"
    if feed != "sip":
        log(f"data feed {feed}: IEX volume is a small slice of the tape; RVOL uses IEX daily volume for consistency. "
            "Set ALPACA_DATA_FEED=sip with a real-time SIP subscription for tape-accurate scanning.")
    data = Data(feed=feed)
    if a.cmd == "scan":
        tr = Trader(cfg, data, DryRun())
        for s, st in tr.scan().items():
            b = st.bars[-1]
            print(f"{s:6s} in-play {st.in_play_at:%H:%M} px {b.c:.2f} gap {st.gap_pct(b.c):.1f}% rvol {st.rvol_now:.1f} "
                  f"news: {st.catalyst(b.t)[1][:80]}")
        return 0
    if a.live:
        if (env.get("ALPACA_PAPER_TRADING_ONLY") or "").lower() != "true":
            raise safety.SafetyError("--live needs ALPACA_PAPER_TRADING_ONLY=true")
        bad = [k for k in safety.ALPACA_URL_VARS if env.get(k) and safety.host_of(env[k]) != "paper-api.alpaca.markets"]
        if bad:
            raise safety.SafetyError("Alpaca base URL is not the paper endpoint: " + ",".join(bad))
        broker = AlpacaPaper(env)
    else:
        broker = DryRun()
    acct = broker.account()
    log(f"start {broker!r} equity={acct.get('equity')} feed={feed} cfg risk/trade=${cfg.risk_per_trade} max loss=${cfg.daily_max_loss}")
    tr = Trader(cfg, data, broker)
    last_min = None
    while True:
        now = datetime.now(ET)
        if now.time() > hhmm(cfg.flatten_at) and not tr.pos and not tr.entry_order:
            log(f"window over; day pnl {tr.risk.pnl:.2f}")
            return 0
        m = now.replace(second=0, microsecond=0)
        if now.second >= 3 and m != last_min and now.time() >= hhmm(cfg.scan_from):
            last_min = m
            try:
                tr.on_minute()
            except safety.SafetyError:
                raise
            except Exception as e:  # keep running through transient API errors
                log(f"minute error: {e.__class__.__name__}: {e}")
            if a.once:
                return 0
        for sym in {x for x in (tr.pos and tr.pos.sym, tr.entry_order and tr.entry_order["sym"]) if x}:
            px = latest_price(data, sym)
            if px:
                if isinstance(broker, DryRun):
                    broker.tick(sym, px)
                if tr.entry_order:
                    tr.check_entry_fill()
                tr.on_price(px)
        time.sleep(3)
