"""Entry signals on the underlying: indicators (EMA, VWAP, RSI, breakout) and candle patterns.

Each base signal returns +1 (bullish), -1 (bearish) or 0 for every (symbol, day, entry time), using only
30-min bars that closed before the entry slot and daily bars up to the previous session. The search can
invert any signal (momentum <-> reversion) and add a daily trend filter and a volatility-regime filter.
"""
import math
from collections import defaultdict

import numpy as np

from . import data as D
from .outcomes import TIMES, SLOT


def _ema(x, n):
    out = np.empty(len(x)); a = 2 / (n + 1); e = x[0]
    for i, v in enumerate(x): e = e + a * (v - e); out[i] = e
    return out


def _rsi(x, n):
    d = np.diff(x, prepend=x[0]); up, dn = np.maximum(d, 0), np.maximum(-d, 0)
    g = np.empty(len(x)); l = np.empty(len(x)); gg = ll = 0.0
    for i in range(len(x)):
        gg = (gg * (n - 1) + up[i]) / n; ll = (ll * (n - 1) + dn[i]) / n; g[i] = gg; l[i] = ll
    return np.where(l == 0, 100.0, 100 - 100 / (1 + g / np.maximum(l, 1e-12)))


BASE = []          # (family, variant, function(ctx) -> int8 array over bars)


def base_signals():
    """List of (family, variant_label). Order within a family = ordinal neighbour order."""
    S = []
    for f, s in ((5, 20), (9, 21), (20, 50)): S.append(("ema_state", f"{f}/{s}"))
    for f, s in ((5, 20), (9, 21), (20, 50)): S.append(("ema_cross", f"{f}/{s}"))
    for n in (20, 50): S.append(("price_vs_ema", str(n)))
    for k in (0.0, 0.002, 0.004): S.append(("vwap", str(k)))
    for n in (2, 5, 14):
        for lo in (10, 20, 30): S.append((f"rsi{n}", f"{lo}/{100-lo}"))
    for n in (4, 8, 13): S.append(("breakout", str(n)))
    S += [("engulfing", ""), ("hammer_star", ""), ("three_bar", ""), ("inside_break", "")]
    for g in (0.003, 0.006): S.append(("gap", str(g)))
    for lo in (10, 25): S.append(("d_rsi2", f"{lo}/{100-lo}"))
    for n in (50, 200): S.append(("d_price_vs_sma", str(n)))
    S.append(("d_ema_state", "10/30"))
    for lo in (0.2, 0.3): S.append(("d_ibs", str(lo)))
    S.append(("d_breakout", "20"))
    S.append(("always", ""))
    return S


def compute(sym, days):
    """returns sig[int8: n_days, n_times, n_base], trend[int8: n_days] (+1 above SMA200), volhi[int8: n_days]"""
    u = D.underlying(sym)
    names = base_signals(); nb = len(names)
    # 30-min adjusted bars, continuous
    rows = []
    for r in u["30m-adj"]:
        t = D.ts(r["t"]); sl = (t.hour * 60 + t.minute - 570) // 30
        if 0 <= sl < 13: rows.append((t.date(), sl, r["o"], r["h"], r["l"], r["c"], r["v"], r.get("vw", r["c"])))
    d_, sl_, o, h, l, c, v, vw = (np.array(x) for x in zip(*rows))
    pos = {(d, s): i for i, (d, s) in enumerate(zip(d_, sl_))}
    ema = {n: _ema(c, n) for n in (5, 9, 20, 21, 50)}
    rsi = {n: _rsi(c, n) for n in (2, 5, 14)}
    # session VWAP
    vwap = np.empty(len(c)); pv = vv = 0.0; prev = None
    for i in range(len(c)):
        if d_[i] != prev: pv = vv = 0.0; prev = d_[i]
        pv += vw[i] * v[i]; vv += v[i]; vwap[i] = pv / vv if vv else c[i]
    # daily adjusted
    dl = [(D.ts(r["t"]).date(), r["o"], r["h"], r["l"], r["c"]) for r in u["1d"]]
    dd = [x[0] for x in dl]; dc = np.array([x[4] for x in dl]); dh = np.array([x[2] for x in dl]); dlo = np.array([x[3] for x in dl])
    dpos = {d: i for i, d in enumerate(dd)}
    drsi2 = _rsi(dc, 2); dema10, dema30 = _ema(dc, 10), _ema(dc, 30)
    sma = {n: np.array([dc[max(0, i - n + 1):i + 1].mean() for i in range(len(dc))]) for n in (50, 200)}
    lr = np.diff(np.log(dc), prepend=np.log(dc[0]))
    rv = np.array([lr[max(1, i - 19):i + 1].std() * math.sqrt(252) for i in range(len(dc))])
    rv_med = np.array([np.median(rv[max(0, i - 252):i + 1]) for i in range(len(dc))])

    sig = np.zeros((len(days), len(TIMES), nb), np.int8)
    trend = np.zeros(len(days), np.int8); volhi = np.zeros(len(days), np.int8)
    for di, day in enumerate(days):
        j = dpos.get(day)
        if j is None or j < 1: continue
        p = j - 1                                            # previous session (closed)
        trend[di] = 1 if dc[p] > sma[200][p] else -1
        volhi[di] = 1 if rv[p] > rv_med[p] else 0
        first = pos.get((day, 0))
        for ti, tn in enumerate(TIMES):
            i = pos.get((day, SLOT[tn] - 1))                 # last closed 30-min bar
            if i is None or i < 60: continue
            out = sig[di, ti]; k = 0
            for f, s in ((5, 20), (9, 21), (20, 50)):
                out[k] = 1 if ema[f][i] > ema[s][i] else -1; k += 1
            for f, s in ((5, 20), (9, 21), (20, 50)):
                now, before = ema[f][i] - ema[s][i], ema[f][i - 2] - ema[s][i - 2]
                out[k] = 1 if now > 0 >= before else -1 if now < 0 <= before else 0; k += 1
            for n in (20, 50): out[k] = 1 if c[i] > ema[n][i] else -1; k += 1
            for kk in (0.0, 0.002, 0.004):
                out[k] = 1 if c[i] > vwap[i] * (1 + kk) else -1 if c[i] < vwap[i] * (1 - kk) else 0; k += 1
            for n in (2, 5, 14):
                for lo in (10, 20, 30):
                    out[k] = 1 if rsi[n][i] < lo else -1 if rsi[n][i] > 100 - lo else 0; k += 1   # reversion polarity
            for n in (4, 8, 13):
                out[k] = 1 if c[i] > h[i - n:i].max() else -1 if c[i] < l[i - n:i].min() else 0; k += 1
            body, pbody = c[i] - o[i], c[i - 1] - o[i - 1]
            out[k] = 1 if (body > 0 > pbody and c[i] >= o[i - 1] and o[i] <= c[i - 1]) else \
                -1 if (body < 0 < pbody and c[i] <= o[i - 1] and o[i] >= c[i - 1]) else 0; k += 1
            rng = h[i] - l[i]; lower = min(o[i], c[i]) - l[i]; upper = h[i] - max(o[i], c[i])
            out[k] = 0 if rng <= 0 else 1 if (lower > 2 * abs(body) and upper < 0.25 * rng) else \
                -1 if (upper > 2 * abs(body) and lower < 0.25 * rng) else 0; k += 1
            out[k] = 1 if c[i] > c[i - 1] > c[i - 2] > c[i - 3] else -1 if c[i] < c[i - 1] < c[i - 2] < c[i - 3] else 0; k += 1
            inside = h[i - 1] <= h[i - 2] and l[i - 1] >= l[i - 2]
            out[k] = 0 if not inside else 1 if c[i] > h[i - 1] else -1 if c[i] < l[i - 1] else 0; k += 1
            gap = (o[first] / dc[p] - 1) if first is not None else 0
            for g in (0.003, 0.006): out[k] = 1 if gap > g else -1 if gap < -g else 0; k += 1
            for lo in (10, 25): out[k] = 1 if drsi2[p] < lo else -1 if drsi2[p] > 100 - lo else 0; k += 1
            for n in (50, 200): out[k] = 1 if dc[p] > sma[n][p] else -1; k += 1
            out[k] = 1 if dema10[p] > dema30[p] else -1; k += 1
            ibs = (dc[p] - dlo[p]) / (dh[p] - dlo[p]) if dh[p] > dlo[p] else 0.5
            for lo in (0.2, 0.3): out[k] = 1 if ibs < lo else -1 if ibs > 1 - lo else 0; k += 1
            out[k] = 1 if dc[p] > dh[max(0, p - 20):p].max() else -1 if dc[p] < dlo[max(0, p - 20):p].min() else 0; k += 1
            out[k] = 1; k += 1
            assert k == nb
    return sig, trend, volhi
