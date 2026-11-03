"""Pure logic: price parsing, fees, longshot-bias edge model, quoting and sizing. No I/O."""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

TICK = 0.01


def _num(x) -> float | None:
    if x is None or x == "":
        return None
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def price(obj: dict, name: str) -> float | None:
    """Dollar price from '<name>_dollars' (current API) or legacy integer cents '<name>'."""
    v = _num(obj.get(f"{name}_dollars"))
    if v is not None:
        return v
    v = _num(obj.get(name))
    return None if v is None else v / 100.0


def count(obj: dict, name: str) -> float:
    v = _num(obj.get(f"{name}_fp"))
    if v is None:
        v = _num(obj.get(name))
    return v or 0.0


def parse_time(s: str | None) -> datetime | None:
    if not s:
        return None
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def r2(x: float) -> float:
    return round(x + 1e-12, 2)


# -- fees ---------------------------------------------------------------------------------------
def fee(contracts: float, p: float, rate: float) -> float:
    """Kalshi fee: ceil-to-cent(rate * C * P * (1-P)). Taker rate 0.07; maker 0.0175 on fee'd series, else 0."""
    raw = rate * contracts * p * (1 - p)
    return math.ceil(round(raw * 100, 6)) / 100 if raw > 0 else 0.0


# -- orderbook ----------------------------------------------------------------------------------
@dataclass
class Book:
    yes_bids: list[tuple[float, float]]  # (price, size), best first
    no_bids: list[tuple[float, float]]

    def best_bid(self, side: str) -> float | None:
        b = self.yes_bids if side == "yes" else self.no_bids
        return b[0][0] if b else None

    def best_ask(self, side: str) -> float | None:
        other = self.no_bids if side == "yes" else self.yes_bids
        return r2(1 - other[0][0]) if other else None

    def size_at(self, side: str, p: float) -> float:
        b = self.yes_bids if side == "yes" else self.no_bids
        return sum(s for q, s in b if abs(q - p) < 1e-9)


def parse_book(resp: dict) -> Book:
    """Kalshi returns bids only: yes bid at X == no ask at 1-X. Accepts orderbook_fp (dollars) or legacy cents."""
    ob = resp.get("orderbook_fp") or {}
    yes, no = ob.get("yes_dollars"), ob.get("no_dollars")
    if yes is None and no is None:
        legacy = resp.get("orderbook") or {}
        yes = [(c / 100, s) for c, s in (legacy.get("yes") or [])]
        no = [(c / 100, s) for c, s in (legacy.get("no") or [])]

    def norm(levels):
        out = [(float(p), float(s)) for p, s in (levels or []) if float(s) > 0]
        return sorted(out, key=lambda t: -t[0])

    return Book(norm(yes), norm(no))


# -- edge model ---------------------------------------------------------------------------------
# Longshot price -> (realized win rate / price). Conservative prior from Bürgi, Deng & Whelan
# ("Makers and Takers: The Economics of the Kalshi Prediction Market"): sub-10c contracts lose >60%
# for buyers; 95c contracts win ~98%. We haircut that toward 1.0. Replace with `kalshibot calibrate`.
DEFAULT_CALIBRATION = [(0.02, 0.55), (0.05, 0.60), (0.10, 0.72), (0.15, 0.82), (0.20, 0.90), (0.30, 0.97), (0.50, 1.0)]


def load_calibration(path: str | None) -> list[tuple[float, float]]:
    if path and Path(path).exists():
        rows = json.loads(Path(path).read_text()).get("ratio_table") or []
        if len(rows) >= 2:
            return sorted((float(a), float(b)) for a, b in rows)
    return DEFAULT_CALIBRATION


def interp(table: list[tuple[float, float]], x: float) -> float:
    if x <= table[0][0]:
        return table[0][1]
    for (x0, y0), (x1, y1) in zip(table, table[1:]):
        if x <= x1:
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return table[-1][1]


def true_prob_favorite(fav_mid: float, table) -> float:
    """Model probability the favorite wins, given its mid price."""
    q = 1 - fav_mid
    return 1 - q * interp(table, q)


# -- config & quoting ---------------------------------------------------------------------------
@dataclass
class Config:
    fav_min: float = 0.80          # favorite side price band we are willing to buy
    fav_max: float = 0.95
    min_hours_to_close: float = 3.0
    max_hours_to_close: float = 24 * 10
    min_volume_24h: float = 200
    max_spread: float = 0.06
    min_edge: float = 0.015        # $ per contract after maker fee
    maker_fee_rate: float = 0.0175  # conservative: assume maker fee applies
    kelly_fraction: float = 0.15
    max_per_market: float = 25.0   # $ cost
    max_per_event: float = 40.0
    max_total_exposure: float = 300.0
    min_contracts: int = 1
    exclude_prefixes: list[str] = field(default_factory=lambda: ["KXMVE"])  # multivariate parlays
    calibration_path: str | None = None
    starting_cash: float = 1000.0

    @classmethod
    def load(cls, path: str | None) -> "Config":
        if path and Path(path).exists():
            return cls(**json.loads(Path(path).read_text()))
        return cls()


@dataclass
class Quote:
    ticker: str
    event_ticker: str
    side: str            # "yes" or "no": the favorite we bid for
    price: float         # our resting bid
    contracts: int
    p_model: float
    edge: float          # $ per contract after maker fee
    best_bid: float
    best_ask: float
    queue_ahead: float
    close_time: str
    title: str = ""


def hours_to_close(market: dict, now: datetime) -> float | None:
    ct = parse_time(market.get("close_time"))
    return None if ct is None else (ct - now).total_seconds() / 3600


def prefilter(m: dict, cfg: Config, now: datetime) -> str | None:
    """Return the favorite side if the market summary passes cheap filters, else None."""
    if any(m.get("ticker", "").startswith(p) for p in cfg.exclude_prefixes):
        return None
    if m.get("status") not in (None, "open", "active"):
        return None
    h = hours_to_close(m, now)
    if h is None or not (cfg.min_hours_to_close <= h <= cfg.max_hours_to_close):
        return None
    if count(m, "volume_24h") < cfg.min_volume_24h:
        return None
    yb, ya = price(m, "yes_bid"), price(m, "yes_ask")
    if not yb or not ya or ya >= 1 or yb <= 0:
        return None
    mid = (yb + ya) / 2
    if cfg.fav_min <= mid <= cfg.fav_max:
        return "yes"
    if cfg.fav_min <= 1 - mid <= cfg.fav_max:
        return "no"
    return None


def kelly_contracts(p: float, cost: float, bankroll: float, frac: float) -> float:
    if cost <= 0 or cost >= 1 or p <= cost:
        return 0.0
    f = (p - cost) / (1 - cost)
    return frac * f * bankroll / cost


def make_quote(m: dict, book: Book, side: str, cfg: Config, table, bankroll: float,
               room_market: float, room_event: float, room_total: float) -> Quote | None:
    bid, ask = book.best_bid(side), book.best_ask(side)
    if bid is None or ask is None or ask - bid > cfg.max_spread + 1e-9:
        return None
    # Improve by one tick when there is room, otherwise join. Never cross (post-only).
    px = r2(bid + TICK) if ask - bid >= 2 * TICK - 1e-9 else bid
    if px >= ask or not (cfg.fav_min - 0.02 <= px <= cfg.fav_max):
        return None
    p = true_prob_favorite((bid + ask) / 2, table)
    unit_fee = fee(100, px, cfg.maker_fee_rate) / 100
    edge = p - px - unit_fee
    if edge < cfg.min_edge:
        return None
    n = kelly_contracts(p, px + unit_fee, bankroll, cfg.kelly_fraction)
    cap = min(cfg.max_per_market, room_market, room_event, room_total)
    n = int(min(n, cap / (px + unit_fee)))
    if n < cfg.min_contracts:
        return None
    queue = book.size_at(side, px)
    return Quote(m["ticker"], m.get("event_ticker", ""), side, px, n, round(p, 4), round(edge, 4),
                 bid, ask, queue, m.get("close_time", ""), m.get("title", ""))


def now_utc() -> datetime:
    return datetime.now(timezone.utc)
