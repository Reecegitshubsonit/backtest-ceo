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
