"""Signal rules ported from /workspace/backtests/backtest.py. Bars are dicts {ts (aware datetime, bar start), o, h, l, c, v}.
Bar strategies: signals are evaluated at a completed bar's close and acted on at the next bar's open (run_bars)."""
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from .indicators import dmi, ema, supertrend

ET = ZoneInfo("America/New_York")


def _cols(bars):
    return ([b["o"] for b in bars], [b["h"] for b in bars], [b["l"] for b in bars], [b["c"] for b in bars])


def sig_alphainsider(bars, ema_len=200, adx_thr=25):
    """s_alphainsider: EMA trend filter + ADX strength filter, long & short."""
    _, h, l, c = _cols(bars)
    e = ema(c, ema_len)
    pdi, mdi, adx = dmi(h, l, c, 14)
    le = [c[i] > e[i] and adx[i] > adx_thr and pdi[i] > mdi[i] for i in range(len(c))]
    lx = [c[i] < e[i] or mdi[i] > pdi[i] for i in range(len(c))]
    se = [c[i] < e[i] and adx[i] > adx_thr and mdi[i] > pdi[i] for i in range(len(c))]
    sx = [c[i] > e[i] or pdi[i] > mdi[i] for i in range(len(c))]
    return dict(le=le, lx=lx, se=se, sx=sx, stop_pct=None)


def sig_supertrend(bars):
    """s_supertrend: SuperTrend(10,3) direction & exit, confluence close vs EMA200 and ADX(14) > 20."""
    _, h, l, c = _cols(bars)
    d = supertrend(h, l, c, 10, 3.0)
    e = ema(c, 200)
    _, _, adx = dmi(h, l, c, 14)
    n = len(c)
    le = [d[i] == 1 and c[i] > e[i] and adx[i] > 20 for i in range(n)]
    lx = [d[i] == -1 for i in range(n)]
    se = [d[i] == -1 and c[i] < e[i] and adx[i] > 20 for i in range(n)]
    sx = [d[i] == 1 for i in range(n)]
    return dict(le=le, lx=lx, se=se, sx=sx, stop_pct=None)


def sig_emacross(bars):
    """s_emacross: long on 9>21 cross, exit on cross down, 2% stop. Long only."""
    c = [b["c"] for b in bars]
    f, s = ema(c, 9), ema(c, 21)
    n = len(c)
    le = [i > 0 and f[i] > s[i] and f[i - 1] <= s[i - 1] for i in range(n)]
    lx = [i > 0 and f[i] < s[i] and f[i - 1] >= s[i - 1] for i in range(n)]
    return dict(le=le, lx=lx, se=[False] * n, sx=[False] * n, stop_pct=0.02)


SIGNALS = {"alphainsider": sig_alphainsider, "supertrend": sig_supertrend, "emacross": sig_emacross}


def resample(bars, hours):
    """pandas df.resample('<hours>h') with first/max/min/last/sum, bins anchored at midnight UTC; empty bins dropped."""
    out, cur, key = [], None, None
    for b in bars:
        t = b["ts"].astimezone(timezone.utc)
        k = t.replace(hour=t.hour - t.hour % hours, minute=0, second=0, microsecond=0)
        if k != key:
            if cur:
                out.append(cur)
            key, cur = k, dict(ts=k, o=b["o"], h=b["h"], l=b["l"], c=b["c"], v=b.get("v", 0.0))
        else:
            cur["h"] = max(cur["h"], b["h"]); cur["l"] = min(cur["l"], b["l"]); cur["c"] = b["c"]; cur["v"] += b.get("v", 0.0)
    if cur:
        out.append(cur)
    return out


def bar_action(pos, sig, i):
    """run_bars' transition at bar i+1's open from bar i's signals. pos: 1 long, -1 short, 0 flat.
    Returns (close_now, open_side) where open_side is 1, -1 or 0."""
    le, lx, se, sx = sig["le"][i], sig["lx"][i], sig["se"][i], sig["sx"][i]
    close = (pos == 1 and (lx or se)) or (pos == -1 and (sx or le))
    after = 0 if close else pos
    opn = 0
    if after == 0:
        opn = 1 if le else (-1 if se else 0)
    return close, opn


def replay_bars(bars, sig):
    """Replays run_bars' position logic (no costs) and returns trades [{entry_time, exit_time, side, entry, exit}].
    Used by tests to prove the live decision path (bar_action + stop check) reproduces backtest.py."""
    o, h, l, c = _cols(bars)
    pos, ent, ent_t, trades = 0, 0.0, None, []
    stop_pct = sig.get("stop_pct")

    def close(px, t):
        nonlocal pos
        trades.append(dict(entry_time=ent_t, exit_time=t, side="long" if pos > 0 else "short", entry=ent, exit=px))
        pos = 0

    for i in range(len(c)):
        t = bars[i]["ts"]
        if i > 0:
            cl, opn = bar_action(pos, sig, i - 1)
            if cl:
                close(o[i], t)
            if pos == 0 and opn:
                pos, ent, ent_t = opn, o[i], t
        if stop_pct and pos != 0:
            sp = ent * (1 - stop_pct) if pos > 0 else ent * (1 + stop_pct)
            if (pos > 0 and l[i] <= sp) or (pos < 0 and h[i] >= sp):
                close(min(sp, o[i]) if pos > 0 else max(sp, o[i]), t)
    if pos != 0:
        close(c[-1], bars[-1]["ts"])
    return trades


# ---------------- first 5-minute RTH candle (RHerman) ----------------
FIRST5M_START, FIRST5M_LAST = time(9, 30), time(15, 55)


def first5m_signal(day_bars):
    """From one day's 5m bars (ET). Returns None or dict(side, stop, signal_ts). Mirrors s_first5m's signal rule:
    bullish 09:30 candle -> long, bearish -> short, doji -> no trade; stop = signal candle's opposite extreme."""
    rth = [b for b in day_bars if FIRST5M_START <= b["ts"].astimezone(ET).time() <= FIRST5M_LAST]
    if not rth or rth[0]["ts"].astimezone(ET).time() != FIRST5M_START:
        return None
    s = rth[0]
    if s["c"] == s["o"]:
        return None
    side = 1 if s["c"] > s["o"] else -1
    return dict(side=side, stop=s["l"] if side > 0 else s["h"], signal_ts=s["ts"])


def first5m_entry_ok(side, entry, stop):
    rpts = abs(entry - stop)
    return not (rpts <= 0 or (side > 0 and entry <= stop) or (side < 0 and entry >= stop))


def first5m_size(entry, stop, risk=200.0, pt=1.0, max_lev=4, equity=10_000.0):
    """QQQ cross-check sizing from backtest.py: n = max(1, floor(risk / (stop pts * pt))), capped at max_lev x equity."""
    n = max(1, int(risk // (abs(entry - stop) * pt)))
    if max_lev:
        n = max(1, min(n, int(max_lev * equity // entry)))
    return n


def first5m_stop_hit(side, stop, bar):
    return (side > 0 and bar["l"] <= stop) or (side < 0 and bar["h"] >= stop)


def first5m_replay(bars, **size_kw):
    """Replays s_first5m's trade list (entry/exit/side/contracts) from 5m bars for parity tests."""
    by_day = {}
    for b in bars:
        by_day.setdefault(b["ts"].astimezone(ET).date(), []).append(b)
    trades = []
    for day in sorted(by_day):
        g = [b for b in by_day[day] if FIRST5M_START <= b["ts"].astimezone(ET).time() <= FIRST5M_LAST]
        if len(g) < 10:
            continue
        sig = first5m_signal(g)
        if not sig:
            continue
        rest = g[1:]
        ent = rest[0]["o"]
        if not first5m_entry_ok(sig["side"], ent, sig["stop"]):
            continue
        n = first5m_size(ent, sig["stop"], **size_kw)
        exit_px, exit_t = rest[-1]["c"], rest[-1]["ts"]
        for b in rest:
            if first5m_stop_hit(sig["side"], sig["stop"], b):
                exit_px = min(sig["stop"], b["o"]) if sig["side"] > 0 else max(sig["stop"], b["o"])
                exit_t = b["ts"]
                break
        trades.append(dict(entry_time=rest[0]["ts"], exit_time=exit_t, side="long" if sig["side"] > 0 else "short",
                           entry=ent, exit=exit_px, contracts=n))
    return trades


# ================= US stock strategies on Alpaca SIP data (ported from /workspace/backtests/backtest_alpaca.py) =================
# Exactly as backtested, no re-tuning. Sizing is the runner's (whole shares within the per-strategy notional cap), not the
# backtest's fractional-equity sizing.
from datetime import date as _date  # noqa: E402

from .indicators import NAN, atr, rma  # noqa: E402

RTH_OPEN, RTH_CLOSE = time(9, 30), time(16, 0)
# NYSE full-day holidays and 13:00 early closes (nyse.com), Oct 2026 -> Dec 2027 plus the dry-run fixture window.
NYSE_HOLIDAYS = {_date.fromisoformat(d) for d in (
    "2026-09-07", "2026-11-26", "2026-12-25", "2027-01-01", "2027-01-18", "2027-02-15", "2027-03-26", "2027-05-31",
    "2027-06-18", "2027-07-05", "2027-09-06", "2027-11-25", "2027-12-24")}
NYSE_EARLY_CLOSE = {_date.fromisoformat(d) for d in ("2026-11-27", "2026-12-24", "2027-11-26")}
ETFS = set("SPY QQQ IWM DIA XLK XLF XLE XLV XLY XLP XLI XLU XLB XLRE XLC SMH GLD TLT ARKK KRE XBI".split())


def cost_of(sym):
    """backtest_alpaca.cost_of: per side spread + slippage (reference only; the paper broker's fills are what they are)."""
    return 0.0001 if sym in ETFS else 0.0002


def session(now):
    """(open, close) aware datetimes of today's NYSE regular session, or None (weekend / holiday)."""
    et = now.astimezone(ET)
    d = et.date()
    if et.weekday() >= 5 or d in NYSE_HOLIDAYS:
        return None
    close = time(13, 0) if d in NYSE_EARLY_CLOSE else RTH_CLOSE
    return datetime.combine(d, RTH_OPEN, ET), datetime.combine(d, close, ET)


def in_rth(now):
    s = session(now)
    return bool(s and s[0] <= now < s[1])


def rth_bars(bars, day):
    """One day's regular-session 5m bars (ET date `day`), like backtest_alpaca's RTH-only 5m data."""
    return [b for b in bars if b["ts"].astimezone(ET).date() == day and RTH_OPEN <= b["ts"].astimezone(ET).time() < RTH_CLOSE]


def rsi(closes, n):
    """backtest_alpaca.rsi: Wilder RSI via rma(); 0/0 (no down moves) -> NaN, so `rsi < 10` is False."""
    d = [NAN] + [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    up = rma([NAN if x != x else max(x, 0.0) for x in d], n)
    dn = rma([NAN if x != x else max(-x, 0.0) for x in d], n)
    out = []
    for u, v in zip(up, dn):
        out.append(NAN if (u != u or v != v or v == 0) else 100 - 100 / (1 + u / v))
    return out


def sma(xs, n):
    return [NAN if i + 1 < n else sum(xs[i + 1 - n:i + 1]) / n for i in range(len(xs))]


# ---------- RSI(2) pullback (Connors) ----------
def rsi2_decision(closes, in_pos):
    """Decision at today's close, `closes` ending with today's (live) close. Flat: buy if close > SMA200 and RSI(2) < 10.
    Long: sell at the first close above SMA5. Returns (action | None, info)."""
    r2, s200, s5 = rsi(closes, 2)[-1], sma(closes, 200)[-1], sma(closes, 5)[-1]
    c = closes[-1]
    info = dict(close=c, rsi2=r2, sma200=s200, sma5=s5)
    if in_pos:
        return ("sell" if c > s5 else None), info
    return ("buy" if (c > s200 and r2 < 10) else None), info


def rsi2_replay(closes):
    """run_rsi2's position logic (no costs): [(entry_i, exit_i)]; an open trade at the end is not listed."""
    r2, s200, s5 = rsi(closes, 2), sma(closes, 200), sma(closes, 5)
    pos, ent, out = False, None, []
    for i in range(1, len(closes)):
        if pos:
            if closes[i] > s5[i]:
                out.append((ent, i))
                pos = False
            continue
        if closes[i] > s200[i] and r2[i] < 10:
            pos, ent = True, i
    return out


# ---------- Stocks-in-Play 5-min ORB (Zarattini, Barbon & Aziz) ----------
SIP_MIN_OPEN, SIP_MIN_AVG_VOL, SIP_MIN_ATR, SIP_MIN_RVOL, SIP_STOP_ATR = 5.0, 1e6, 0.5, 1.0, 0.1


def sip_context(daily):
    """From COMPLETED daily bars (oldest first, before today): ATR14 and 14-day mean volume as of today's open
    (backtest: atr(dd, 14).shift() and dd.volume.rolling(14).mean().shift())."""
    h, l, c = [b["h"] for b in daily], [b["l"] for b in daily], [b["c"] for b in daily]
    a14 = atr(h, l, c, 14)[-1] if len(daily) >= 14 else NAN
    v14 = sum(b["v"] for b in daily[-14:]) / 14 if len(daily) >= 14 else NAN
    return a14, v14


def sip_filter(open0, a14, v14, vol0, prev_first_vols):
    """Day filter: open > $5, 14-day avg volume > 1M, ATR14 > $0.50, first-5m relative volume >= 100% of the prior 14
    sessions' first-5m volume. Returns (ok, rvol, why)."""
    prev = list(prev_first_vols)[-14:]
    if len(prev) < 14:
        return False, None, f"only {len(prev)} prior first-5m volumes (need 14)"
    m = sum(prev) / len(prev)
    rv = vol0 / m if m > 0 else 0.0
    fails = [w for ok, w in ((open0 > SIP_MIN_OPEN, f"open {open0:.2f} <= 5"), (v14 > SIP_MIN_AVG_VOL, f"avg vol {v14:,.0f} <= 1M"),
                             (a14 > SIP_MIN_ATR, f"ATR14 {a14:.2f} <= 0.50"), (rv >= SIP_MIN_RVOL, f"rel vol {rv:.2f} < 1.00")) if not ok]
    return not fails, rv, "; ".join(fails) or "in play"


def sip_signal(first):
    """First 5m candle direction; level = the opening-range high (long) / low (short). Doji -> None."""
    if first["c"] == first["o"]:
        return None
    side = 1 if first["c"] > first["o"] else -1
    return dict(side=side, level=first["h"] if side > 0 else first["l"])


def sip_triggered(side, level, bar):
    return bar["h"] >= level if side > 0 else bar["l"] <= level


def sip_entry_price(side, level, bar_open):
    return max(level, bar_open) if side > 0 else min(level, bar_open)


def sip_stop(side, entry, a14):
    return entry - side * SIP_STOP_ATR * a14


def sip_stopped(side, stop, bar, entry_bar):
    """'close' mode: the entry bar stops out only if it CLOSES through the stop; later bars on any touch."""
    if entry_bar:
        return bar["c"] <= stop if side > 0 else bar["c"] >= stop
    return bar["l"] <= stop if side > 0 else bar["h"] >= stop


def sip_day(rth, a14):
    """sip_day() for one session of RTH 5m bars (filters already passed): dict(side, entry, exit, stop, reason) or None."""
    sig = sip_signal(rth[0])
    if not sig:
        return None
    side, lvl = sig["side"], sig["level"]
    rest = rth[1:]
    j = next((k for k, b in enumerate(rest) if sip_triggered(side, lvl, b)), -1)
    if j < 0:
        return None
    ent = sip_entry_price(side, lvl, rest[j]["o"])
    stop = sip_stop(side, ent, a14)
    for k in range(j, len(rest)):
        if sip_stopped(side, stop, rest[k], k == j):
            return dict(side=side, entry=ent, exit=stop, stop=stop, reason="stop")
    return dict(side=side, entry=ent, exit=rest[-1]["c"], stop=stop, reason="close")


# ---------- Overnight hold ----------
def overnight_ret(prev_close, next_open, sym):
    """run_overnight: (open / previous close) * (1 - cost)^2 - 1."""
    return next_open / prev_close * (1 - cost_of(sym)) ** 2 - 1
