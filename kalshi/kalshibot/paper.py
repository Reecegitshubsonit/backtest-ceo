"""Paper trading: resting maker bids simulated against Kalshi's public trade tape.

Fill rule (conservative, maker queue-aware) for our bid on side S at price b:
  * a print on side S strictly below b means the market traded through us -> fill up to print size;
  * a print at exactly b where the taker sold S (taker bought the other side) first eats the
    queue that was resting ahead of us when we posted, then fills us.
Settlement: on market result yes/no pay $1 per winning contract; any other result refunds cost.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .model import count, fee, parse_time, price, r2


@dataclass
class Order:
    id: str
    ticker: str
    event_ticker: str
    side: str
    price: float
    remaining: int
    queue_ahead: float
    placed_ts: int
    close_time: str
    p_model: float
    edge: float


@dataclass
class Position:
    ticker: str
    event_ticker: str
    side: str
    contracts: int = 0
    cost: float = 0.0  # including fees


@dataclass
class State:
    cash: float
    orders: dict[str, Order] = field(default_factory=dict)
    positions: dict[str, Position] = field(default_factory=dict)
    last_trade_ts: dict[str, int] = field(default_factory=dict)
    seen_ids: dict[str, list[str]] = field(default_factory=dict)  # trade ids at last_trade_ts
    seq: int = 0
    realized: float = 0.0
    wins: int = 0
    losses: int = 0

    @classmethod
    def load(cls, path: Path, starting_cash: float) -> "State":
        if not path.exists():
            return cls(cash=starting_cash)
        d = json.loads(path.read_text())
        return cls(
            cash=d["cash"],
            orders={k: Order(**v) for k, v in d["orders"].items()},
            positions={k: Position(**v) for k, v in d["positions"].items()},
            last_trade_ts=d.get("last_trade_ts", {}),
            seen_ids=d.get("seen_ids", {}),
            seq=d.get("seq", 0), realized=d.get("realized", 0.0),
            wins=d.get("wins", 0), losses=d.get("losses", 0),
        )

    def save(self, path: Path) -> None:
        d = asdict(self)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(d, indent=1))
        tmp.replace(path)

    # exposure counts both filled cost and cash reserved by resting bids
    def exposure(self, ticker: str | None = None, event: str | None = None) -> float:
        tot = 0.0
        for p in self.positions.values():
            if (ticker is None or p.ticker == ticker) and (event is None or p.event_ticker == event):
                tot += p.cost
        for o in self.orders.values():
            if (ticker is None or o.ticker == ticker) and (event is None or o.event_ticker == event):
                tot += o.remaining * o.price
        return tot

    def reserved(self) -> float:
        return sum(o.remaining * o.price for o in self.orders.values())


class Journal:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)

    def __call__(self, kind: str, **kw) -> None:
        with self.path.open("a") as f:
            f.write(json.dumps({"kind": kind, **kw}) + "\n")


def place(state: State, q, now_ts: int, log: Journal) -> Order | None:
    cost = q.contracts * q.price
    if cost > state.cash - state.reserved():
        return None
    state.seq += 1
    o = Order(f"P{state.seq}", q.ticker, q.event_ticker, q.side, q.price, q.contracts, q.queue_ahead,
              now_ts, q.close_time, q.p_model, q.edge)
    state.orders[o.id] = o
    state.last_trade_ts.setdefault(q.ticker, now_ts)
    log("place", ts=now_ts, **asdict(o))
    return o


def cancel(state: State, oid: str, now_ts: int, log: Journal, reason: str) -> None:
    o = state.orders.pop(oid, None)
    if o:
        log("cancel", ts=now_ts, id=oid, ticker=o.ticker, remaining=o.remaining, reason=reason)


def trade_ts(t: dict) -> int:
    dt = parse_time(t.get("created_time"))
    return int(dt.timestamp()) if dt else 0


def apply_trades(state: State, ticker: str, trades: list[dict], maker_fee_rate: float, log: Journal) -> int:
    """Apply public prints (any order) to our resting orders on `ticker`. Returns contracts filled."""
    filled = 0
    since = state.last_trade_ts.get(ticker, 0)
    seen = set(state.seen_ids.get(ticker, []))
    new = []
    for t in sorted(trades, key=trade_ts):
        tid = t.get("trade_id")
        if trade_ts(t) < since or tid in seen or t.get("ticker", ticker) != ticker:
            continue
        seen.add(tid)
        new.append(t)
    for t in new:
        size = count(t, "count")
        taker = t.get("taker_side")
        for o in sorted((o for o in state.orders.values() if o.ticker == ticker), key=lambda o: -o.price):
            if size <= 0:
                break
            if trade_ts(t) < o.placed_ts:
                continue
            px = price(t, f"{o.side}_price")
            if px is None:
                continue
            if px < o.price - 1e-9:
                take = min(size, o.remaining)
            elif abs(px - o.price) < 1e-9 and taker and taker != o.side:
                eat = min(size, o.queue_ahead)
                o.queue_ahead -= eat
                size -= eat
                take = min(size, o.remaining)
            else:
                continue
            n = int(take)
            if n <= 0:
                continue
            size -= n
            filled += n
            _fill(state, o, n, maker_fee_rate, log, trade_ts(t))
    if new:
        last = max(trade_ts(t) for t in new)
        state.last_trade_ts[ticker] = last
        state.seen_ids[ticker] = [t.get("trade_id") for t in new if trade_ts(t) == last] + (
            state.seen_ids.get(ticker, []) if last == since else [])
    return filled


def _fill(state: State, o: Order, n: int, rate: float, log: Journal, ts: int) -> None:
    f = fee(n, o.price, rate)
    cost = n * o.price + f
    state.cash = r2(state.cash - cost)
    o.remaining -= n
    pos = state.positions.setdefault(o.ticker, Position(o.ticker, o.event_ticker, o.side))
    pos.contracts += n
    pos.cost = r2(pos.cost + cost)
    log("fill", ts=ts, id=o.id, ticker=o.ticker, side=o.side, price=o.price, contracts=n, fee=f)
    if o.remaining <= 0:
        state.orders.pop(o.id, None)


def settle(state: State, market: dict, now_ts: int, log: Journal) -> float | None:
    """Settle a position if the market has a result. Returns P&L or None if not settled yet."""
    t = market["ticker"]
    pos = state.positions.get(t)
    status = market.get("status")
    result = (market.get("result") or "").lower()
    if pos is None or status not in ("settled", "finalized", "determined") or not result:
        return None
    for oid in [k for k, o in state.orders.items() if o.ticker == t]:
        cancel(state, oid, now_ts, log, "settled")
    if result in ("yes", "no"):
        payout = float(pos.contracts) if result == pos.side else 0.0
    else:  # void / scalar edge cases: refund conservatively at cost
        payout = pos.cost
    pnl = r2(payout - pos.cost)
    state.cash = r2(state.cash + payout)
    state.realized = r2(state.realized + pnl)
    if pnl > 0:
        state.wins += 1
    elif pnl < 0:
        state.losses += 1
    del state.positions[t]
    log("settle", ts=now_ts, ticker=t, side=pos.side, result=result, contracts=pos.contracts, cost=pos.cost, pnl=pnl)
    return pnl
