"""Shared strategy logic: indicators, scanner, setup detection, position exits. Backtest and paper trader both use it.

Everything works on closed 1-minute bars. A setup found at the close of bar i is a buy-stop at bar i's high + 1c
that is valid only during bar i+1 (the "first candle to make a new high"); if it does not trigger it is recomputed.
"""
from dataclasses import dataclass, field
from datetime import datetime, time as dtime
import re
from math import floor

from .config import Config


# Market-wide pieces, sector roundups, mover lists and call transcripts are not stock-specific catalysts.
ROUNDUP = re.compile(r"stocks? moving|movers|gainers|losers|mid-?day|pre-?market session|after-?market session|"
                     r"transcript|stock market today|futures|\b\d+ stocks\b|top \d+|stocks to watch|market clubhouse|"
                     r"most active|biggest|unusual options", re.I)


def is_catalyst(headline: str, symbols: list, cfg: Config) -> bool:
    if not cfg.catalyst_filter:
        return True
    return len(symbols) <= cfg.catalyst_max_symbols and not ROUNDUP.search(headline or "")


def hhmm(s: str) -> dtime:
    h, m = map(int, s.split(":"))
    return dtime(h, m)


@dataclass
class Bar:
    t: datetime  # bar start, ET
    o: float
    h: float
    l: float
    c: float
    v: float


class EMA:
    def __init__(self, n: int):
        self.k, self.v = 2 / (n + 1), None

    def __call__(self, x: float) -> float:
        self.v = x if self.v is None else self.v + self.k * (x - self.v)
        return self.v


def rvol(cum_vol: float, adv: float, t: datetime) -> float:
    """Time-of-day adjusted relative volume: volume so far vs the ADV share expected by now.

    Expected share = max(30, minutes since 09:30) / 390, capped at 1. Before the open the floor of 30 minutes stands in
    for premarket, so at 09:30 a 5x stock has already traded ~38% of its average full day.
    """
    if adv <= 0:
        return 0.0
    mins = (t.hour * 60 + t.minute) - (9 * 60 + 30)
    frac = min(1.0, max(30, mins) / 390)
    return cum_vol / (adv * frac)


@dataclass
class Setup:
    sym: str
    pattern: str
    trigger: float
    stop: float
    limit: float
    t_ready: datetime
    leg_high: float
    gap_pct: float
    rvol: float

    @property
    def risk(self) -> float:
        return self.trigger - self.stop


class SymbolState:
    """Per symbol-day: indicators, scanner status, pullback setups."""

    def __init__(self, sym: str, prev_close: float, adv: float, news: list, cfg: Config):
        self.sym, self.pc, self.adv, self.cfg = sym, prev_close, adv, cfg
        self.news = sorted(news, key=lambda n: n[0])  # [(datetime, headline)]
        self.bars: list[Bar] = []
        self.hod: list[float] = []
        self.e9, self.e12, self.e26, self.sig = EMA(9), EMA(12), EMA(26), EMA(9)
        self.ema9 = self.macd = self.signal = self.vwap = 0.0
        self.prev_macd = self.prev_signal = 0.0
        self.cum_v = self.cum_pv = 0.0
        self.in_play_at: datetime | None = None
        self.first_leg_j: int | None = None
        self.entries = 0
        self.rvol_now = 0.0

    # -------------------------------------------------------------- per bar
    def gap_pct(self, price: float) -> float:
        return (price / self.pc - 1) * 100 if self.pc > 0 else 0.0

    def catalyst(self, t: datetime):
        hits = [n for n in self.news if n[0] <= t]
        return hits[-1] if hits else None

    def update(self, b: Bar) -> None:
        self.bars.append(b)
        self.hod.append(max(b.h, self.hod[-1]) if self.hod else b.h)
        self.ema9 = self.e9(b.c)
        self.prev_macd, self.prev_signal = self.macd, self.signal
        self.macd = self.e12(b.c) - self.e26(b.c)
        self.signal = self.sig(self.macd)
        typical = (b.h + b.l + b.c) / 3
        self.cum_v += b.v
        self.cum_pv += typical * b.v
        self.vwap = self.cum_pv / self.cum_v if self.cum_v else b.c
        self.rvol_now = rvol(self.cum_v, self.adv, b.t)
        if self.in_play_at is None and b.t.time() >= hhmm(self.cfg.scan_from) and self.scanner_ok(b):
            self.in_play_at = b.t

    def scanner_ok(self, b: Bar) -> bool:
        c = self.cfg
        return (c.min_price <= b.c <= c.max_price and self.gap_pct(b.c) >= c.min_gap_pct and self.rvol_now >= c.min_rvol
                and (not c.require_news or self.catalyst(b.t) is not None))

    # -------------------------------------------------------------- setups
    def setup(self) -> Setup | None:
        c, bars = self.cfg, self.bars
        i = len(bars) - 1
        if self.in_play_at is None or i < 3:
            return None
        b = bars[i]
        if not (c.min_price <= b.c <= c.max_price) or self.gap_pct(b.c) < c.min_gap_pct:
            return None
        if c.require_macd_positive and self.macd <= 0:
            return None
        if c.require_above_vwap and b.c <= self.vwap:
            return None
        lo = max(0, i - c.max_pullback_bars)
        j = max(range(lo, i), key=lambda k: (bars[k].h, k))
        H = bars[j].h
        if b.h >= H:  # current candle still making highs: no pullback yet
            return None
        if c.require_hod and H < self.hod[j]:
            return None
        n = i - j
        pull = bars[j + 1:i + 1]
        if not any(p.c < p.o or p.l < q.l for p, q in zip(pull, bars[j:i])):
            return None
        PL = min(p.l for p in pull)
        s0 = max(0, j - c.leg_lookback)
        s_idx = min(range(s0, j + 1), key=lambda k: bars[k].l)
        S = bars[s_idx].l
        if S <= 0 or H <= S or (H - S) / S * 100 < c.min_leg_pct:
            return None
        if (H - PL) / (H - S) > c.max_retrace:
            return None
        if self.first_leg_j is None and bars[j].t >= self.in_play_at:
            self.first_leg_j = j
        if j == self.first_leg_j:
            pattern = "first_pullback"
        elif n == 1:
            pattern = "micro_pullback"
        else:
            pattern = "bull_flag"
        if pattern not in c.patterns:
            return None
        if pattern != "micro_pullback" and n >= 2 and c.require_light_pullback_volume:
            leg = bars[s_idx + 1:j + 1] or [bars[j]]
            if sum(p.v for p in pull) / len(pull) >= sum(p.v for p in leg) / len(leg):
                return None
        trigger = round(b.h + 0.01, 2)
        stop = round(PL - 0.01, 2)
        risk = trigger - stop
        if risk < c.min_stop_cents / 100 or risk / trigger * 100 > c.max_stop_pct:
            return None
        limit = round(trigger * (1 + c.entry_limit_pct / 100) + 0.005, 2)
        return Setup(self.sym, pattern, trigger, stop, limit, b.t, H, self.gap_pct(b.c), self.rvol_now)

    def avg_vol(self, n: int = 5) -> float:
        tail = self.bars[-n:]
        return sum(b.v for b in tail) / len(tail) if tail else 0.0


def size(setup: Setup, state: SymbolState, cfg: Config, mult: float) -> int:
    shares = floor(cfg.risk_per_trade * mult / setup.risk)
    shares = min(shares, floor(cfg.max_position_dollars / setup.limit), floor(state.avg_vol(5) * cfg.liquidity_frac))
    return max(0, shares)


def slip(price: float, cfg: Config) -> float:
    return max(0.01, price * cfg.slippage_pct / 100)


@dataclass
class Position:
    sym: str
    pattern: str
    entry: float
    stop: float
    shares: int
    t_entry: datetime
    setup: Setup
    remaining: int = 0
    partial_done: bool = False
    bars_held: int = 0
    fills: list = field(default_factory=list)  # (t, price, shares, reason)

    def __post_init__(self):
        self.remaining = self.remaining or self.shares
        self.init_stop = self.stop
        self.r = self.entry - self.stop

    def target_price(self, cfg: Config) -> float:
        return round(self.entry + cfg.target_r * self.r, 2)

    def pnl(self) -> float:
        return sum((p - self.entry) * q for _, p, q, _ in self.fills)

    def exit(self, t, price, qty, reason):
        qty = min(qty, self.remaining)
        if qty > 0:
            self.fills.append((t, round(price, 4), qty, reason))
            self.remaining -= qty

    def on_close(self, b: Bar, st: SymbolState, cfg: Config) -> str | None:
        """Bar-close decisions shared by backtest and live. Returns an exit reason (sell everything at market) or None.
        Also ratchets the trailing stop."""
        self.bars_held += 1
        hod_before = st.hod[-2] if len(st.hod) > 1 else b.h
        rng = b.h - b.l
        if cfg.exit_topping_tail and rng > 0 and b.h >= hod_before and (b.h - max(b.o, b.c)) / rng >= cfg.topping_tail_wick \
                and b.c > self.entry:
            return "topping_tail"
        if self.partial_done:
            if cfg.exit_macd_cross and st.macd < st.signal and st.prev_macd >= st.prev_signal:
                return "macd_cross"
            if cfg.trail_prior_low:
                self.stop = max(self.stop, round(b.l - 0.01, 2))
        elif cfg.bailout_bars and self.bars_held >= cfg.bailout_bars and b.c <= self.entry:
            return "bailout"
        return None


def sim_entry(setup: Setup, b: Bar, cfg: Config) -> float | None:
    """Stop-limit buy at setup.trigger / setup.limit against bar b. Returns fill price or None."""
    if b.h < setup.trigger:
        return None
    if b.o >= setup.trigger:
        if b.o <= setup.limit:
            return min(setup.limit, b.o + slip(b.o, cfg))
        return setup.limit if b.l <= setup.limit else None
    return min(setup.limit, setup.trigger + slip(setup.trigger, cfg))


def sim_bar(pos: Position, b: Bar, cfg: Config, entry_bar: bool) -> None:
    """Intrabar stop / target fills for one bar (conservative ordering)."""
    if pos.remaining <= 0:
        return
    if b.l <= pos.stop:
        px = pos.stop if entry_bar else min(b.o, pos.stop)
        pos.exit(b.t, px - slip(px, cfg), pos.remaining, "stop" if not pos.partial_done else "trail_stop")
        return
    tgt = pos.target_price(cfg)
    if not pos.partial_done and b.h >= tgt + 0.01:
        q = max(1, int(pos.shares * cfg.partial_frac)) if pos.shares > 1 else pos.shares
        pos.exit(b.t, tgt, q, "target")
        pos.partial_done = True
        pos.stop = max(pos.stop, round(pos.entry, 2))
        if pos.remaining and b.c < b.o and b.l <= pos.stop:  # red bar: high came first, then the low
            pos.exit(b.t, pos.stop - slip(pos.stop, cfg), pos.remaining, "breakeven")
