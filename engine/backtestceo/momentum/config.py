"""All tunable rules in one place. Defaults are the documented strategy; the backtest CLI can override any field."""
from dataclasses import dataclass, fields, replace


@dataclass(frozen=True)
class Config:
    # ---- scanner (Cameron's pillars minus float)
    min_price: float = 2.0
    max_price: float = 20.0
    min_gap_pct: float = 10.0          # % up from previous close, at qualification and at entry
    min_rvol: float = 5.0              # time-of-day adjusted relative volume (see engine.rvol)
    require_news: bool = True          # Alpaca/Benzinga headline tagged with the symbol since prev close 16:00 ET
    catalyst_filter: bool = True       # drop roundups / transcripts / market-wide headlines (see engine.ROUNDUP)
    catalyst_max_symbols: int = 2      # a headline tagging more tickers than this is a roundup, not a catalyst
    adv_days: int = 20                 # average-daily-volume lookback
    min_history_days: int = 5          # skip symbols with fewer prior daily bars (no ADV)

    # ---- time of day (ET)
    scan_from: str = "07:00"           # scanner starts qualifying symbols
    entry_from: str = "09:30"          # first entry (09:30 = regular hours only; "07:00" adds premarket)
    entry_until: str = "11:00"         # last entry
    flatten_at: str = "11:30"          # close anything still open

    # ---- setups
    patterns: tuple = ("micro_pullback", "bull_flag", "first_pullback")
    leg_lookback: int = 15             # bars to look back for the impulse leg start
    max_pullback_bars: int = 5
    min_leg_pct: float = 4.0           # impulse leg size, % of price
    max_retrace: float = 0.5           # pullback may give back at most this fraction of the leg
    require_hod: bool = True           # leg high must be the high of day so far
    require_macd_positive: bool = True
    require_above_vwap: bool = True
    require_light_pullback_volume: bool = True  # bull flag / first pullback: pullback avg vol < leg avg vol
    max_stop_pct: float = 5.0          # skip setups whose stop is wider than this % of entry
    min_stop_cents: float = 3.0        # stop at least 3 cents below the trigger
    entry_limit_pct: float = 0.5       # buy stop-limit: limit = trigger + 0.5% (no chasing past that)

    # ---- exits
    target_r: float = 2.0              # sell `partial_frac` at this multiple of risk, stop -> breakeven
    partial_frac: float = 0.5
    trail_prior_low: bool = True       # after partial: exit on the first candle that makes a new low
    exit_topping_tail: bool = True     # exit at close of a topping-tail candle at high of day
    topping_tail_wick: float = 0.6     # upper wick share of the candle range
    exit_macd_cross: bool = True       # after partial: exit when MACD crosses below signal
    bailout_bars: int = 5              # breakout-or-bailout: no progress (close <= entry) after N bars -> out

    # ---- risk / account
    equity: float = 25_000.0
    risk_per_trade: float = 100.0      # dollars at risk entry->stop
    max_position_dollars: float = 25_000.0
    liquidity_frac: float = 0.10       # shares <= this share of the average 1-min volume of the last 5 bars
    daily_max_loss: float = 300.0      # stop trading for the day at -3R
    max_consecutive_losses: int = 3
    cold_size_mult: float = 0.5        # after a loser, size x0.5 until the next winner
    max_trades_per_day: int = 10
    max_entries_per_symbol: int = 2
    max_positions: int = 1

    # ---- simulated fills
    slippage_pct: float = 0.2          # per side, % of price (min 1 cent)

    def with_(self, **kw) -> "Config":
        return replace(self, **kw)


def parse_overrides(pairs: list[str]) -> dict:
    """key=value strings -> typed dict, using the dataclass field types."""
    types = {f.name: f.type for f in fields(Config)}
    out = {}
    for p in pairs:
        k, v = p.split("=", 1)
        if k not in types:
            raise SystemExit(f"unknown config field {k}")
        t = types[k]
        if t in ("bool", bool):
            out[k] = v.lower() in ("1", "true", "yes", "on")
        elif t in ("int", int):
            out[k] = int(v)
        elif t in ("float", float):
            out[k] = float(v)
        elif t in ("tuple", tuple):
            out[k] = tuple(x for x in v.split(",") if x)
        else:
            out[k] = v
    return out
