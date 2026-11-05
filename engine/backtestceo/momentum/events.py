"""Pullback-setup events and their trade outcomes, precomputed once so the 124,416-combination search is cheap.

For every candidate symbol-day (hist.py) and every 1-min bar closing 07:00-11:30 where the stock is >= +10% vs the
previous close and $1-20, a setup is found when the same structure as engine.SymbolState.setup() holds (leg >= 4%
to the high of day within 15 bars, 1-5 bar pullback, retrace <= 50%, a red or lower-low candle). Pattern:
  first_pullback  the first leg high of the day that produced a setup
  micro_pullback  1-bar pullback
  bull_flag       2-5 bar pullback on lighter volume than the leg
Entry modes: A = buy-stop at the setup candle high +1c on the next bar (stop-limit, limit +0.5%);
             B = candle confirmation: next bar must close above the trigger in the top half of its range, buy the
                 open after it.
Outcomes for 3 stops (pullback low, capped at 8% / fixed 2% / fixed 4%) x 4 targets (1R / 2R / 3R / trail the
prior bar low after +1R), with a 30-minute maximum hold. Costs are applied later from the spread model.
"""
import json
import re
from multiprocessing import Pool
from pathlib import Path

import numpy as np
from numba import njit

from .hist import ROOT, jload, sessions, START

STOPS = ("pb", "fix2", "fix4")
TARGETS = ("1R", "2R", "3R", "trail")
MAX_HOLD = 30
ROUNDUP = re.compile(r"stocks? moving|movers|gainers|losers|mid-?day|pre-?market session|after-?market session|"
                     r"transcript|stock market today|futures|\b\d+ stocks\b|top \d+|stocks to watch|market clubhouse|"
                     r"most active|biggest|unusual options|halt|resumes? trad|circuit breaker", re.I)


@njit(cache=True)
def _ema(x, n):
    out = np.empty_like(x)
    k = 2.0 / (n + 1)
    a = x[0]
    for i in range(len(x)):
        a = x[i] if i == 0 else a + k * (x[i] - a)
        out[i] = a
    return out


@njit(cache=True)
def _exits(m, o, h, l, c, e, fill, stop0, tgt_r, trail, maxhold):
    """Simulate one long from entry bar e. Returns (exit_px, exit_idx, kind) kind 0 stop, 1 target, 2 time."""
    n = len(m)
    r = fill - stop0
    stop = stop0
    tgt = fill + tgt_r * r if tgt_r > 0 else 1e18
    armed = False
    last = min(n - 1, e + maxhold)
    for j in range(e, last + 1):
        if l[j] <= stop:
            px = stop if j == e else min(o[j], stop)
            return px, j, 0
        if j > e and h[j] >= tgt + 0.01:
            return tgt, j, 1
        if trail:
            if h[j] >= fill + r:
                armed = True
            if armed and j > e:
                s2 = l[j] - 0.01
                if s2 > stop:
                    stop = s2
    return c[last], last, 2


@njit(cache=True)
def symday_events(m, o, h, l, c, v, pc, adv):
    n = len(m)
    cap = n * 2
    # per event outputs
    ev_i = np.empty(cap, np.int32); ev_mode = np.empty(cap, np.int8); ev_pat = np.empty(cap, np.int8)
    ev_gap = np.empty(cap); ev_rvol = np.empty(cap); ev_px = np.empty(cap)
    ev_vwap = np.empty(cap, np.int8); ev_ema = np.empty(cap, np.int8)
    ev_e = np.empty(cap, np.int32); ev_fill = np.empty(cap)
    ev_stop = np.empty((cap, 3)); ev_out = np.empty((cap, 3, 4)); ev_xi = np.empty((cap, 3, 4), np.int32)
    ev_xk = np.empty((cap, 3, 4), np.int8)
    if n < 20:
        return 0, ev_i, ev_mode, ev_pat, ev_gap, ev_rvol, ev_px, ev_vwap, ev_ema, ev_e, ev_fill, ev_stop, ev_out, ev_xi, ev_xk
    e9 = _ema(c, 9)
    vw = np.empty(n); cum = np.empty(n); hod = np.empty(n)
    pv = 0.0; cv = 0.0; hh = 0.0
    for i in range(n):
        tp = (h[i] + l[i] + c[i]) / 3.0
        pv += tp * v[i]; cv += v[i]
        vw[i] = pv / cv if cv > 0 else c[i]
        cum[i] = cv
        hh = h[i] if i == 0 else max(hh, h[i])
        hod[i] = hh
    first_j = -1
    k = 0
    for i in range(5, n - 2):
        if m[i] < 420 or m[i] > 690:
            continue
        gap = (c[i] / pc - 1.0) * 100.0
        if gap < 10.0 or c[i] < 1.0 or c[i] > 20.0:
            continue
        # leg high j in [i-5, i-1]
        j = i - 5
        for q in range(i - 5, i):
            if h[q] >= h[j]:
                j = q
        H = h[j]
        if h[i] >= H or H < hod[j]:
            continue
        ok = False
        PL = 1e18
        for q in range(j + 1, i + 1):
            if c[q] < o[q] or l[q] < l[q - 1]:
                ok = True
            if l[q] < PL:
                PL = l[q]
        if not ok:
            continue
        s0 = max(0, j - 15)
        S = 1e18; sidx = s0
        for q in range(s0, j + 1):
            if l[q] < S:
                S = l[q]; sidx = q
        if S <= 0 or H <= S or (H - S) / S * 100.0 < 4.0 or (H - PL) / (H - S) > 0.5:
            continue
        npb = i - j
        if first_j < 0:
            first_j = j
        if j == first_j:
            pat = 2
        elif npb == 1:
            pat = 0
        else:
            pat = 1
        if pat != 0 and npb >= 2:
            pvol = 0.0
            for q in range(j + 1, i + 1):
                pvol += v[q]
            lvol = 0.0; ln = 0
            for q in range(sidx + 1, j + 1):
                lvol += v[q]; ln += 1
            if ln == 0:
                lvol = v[j]; ln = 1
            if pvol / npb >= lvol / ln:  # bull flag / first pullback need a lighter-volume pullback
                continue
        trig = np.floor(h[i] * 100 + 0.5) / 100 + 0.01
        limit = trig * 1.005
        mins = m[i] + 1 - 570
        fr = max(30.0, mins) / 390.0
        if fr > 1.0:
            fr = 1.0
        rv = cum[i] / (adv * fr) if adv > 0 else 0.0
        for mode in range(2):
            if mode == 0:
                e = i + 1
                if h[e] < trig:
                    continue
                if o[e] > limit:
                    if l[e] > limit:
                        continue
                    fill = limit
                else:
                    fill = max(o[e], trig)
            else:
                b = i + 1
                rng = h[b] - l[b]
                if not (h[b] >= trig and c[b] >= trig and (rng <= 0 or (c[b] - l[b]) / rng >= 0.5)):
                    continue
                e = i + 2
                if e >= n:
                    continue
                fill = o[e]
            stops = np.empty(3)
            stops[0] = max(PL - 0.01, fill * 0.92)
            stops[1] = fill * 0.98
            stops[2] = fill * 0.96
            if stops[0] >= fill - 0.01:
                continue
            ev_i[k] = i; ev_mode[k] = mode; ev_pat[k] = pat; ev_gap[k] = gap; ev_rvol[k] = rv; ev_px[k] = c[i]
            ev_vwap[k] = 1 if c[i] > vw[i] else 0
            ev_ema[k] = 1 if c[i] > e9[i] else 0
            ev_e[k] = e; ev_fill[k] = fill
            for si in range(3):
                ev_stop[k, si] = stops[si]
                for ti in range(4):
                    tr = ti == 3
                    tg = 0.0 if tr else float(ti + 1)
                    px, xi, kind = _exits(m, o, h, l, c, e, fill, stops[si], tg, tr, 30)
                    ev_out[k, si, ti] = px; ev_xi[k, si, ti] = xi; ev_xk[k, si, ti] = kind
            k += 1
    return k, ev_i, ev_mode, ev_pat, ev_gap, ev_rvol, ev_px, ev_vwap, ev_ema, ev_e, ev_fill, ev_stop, ev_out, ev_xi, ev_xk


def _news_flags(rows, sym, minute):
    """(any headline, stock-specific catalyst) published from prev 16:00 up to `minute` (minutes of day d, ET)."""
    anyn = cat = False
    for s, t, head, nsym in rows:
        if s != sym or t > minute:
            continue
        anyn = True
        if nsym <= 2 and not ROUNDUP.search(head or ""):
            cat = True
    return anyn, cat


def day_events(args):
    di, d = args
    f = ROOT / "events" / f"{d}.npz"
    if f.exists():
        return str(f)
    zf = ROOT / "min" / f"{d}.npz"
    if not zf.exists():
        return None
    z = np.load(zf)
    cands = {c["sym"]: c for c in jload(ROOT / "cands" / f"{d}.json")}
    newsf = ROOT / "news" / f"{d}.json"
    news = jload(newsf) if newsf.exists() else None
    by_sym = {}
    if news is not None:
        for r in news:
            by_sym.setdefault(r[0], []).append(r)
    cols = {k: [] for k in ("sd", "m", "mode", "pat", "gap", "rvol", "px", "vwap", "ema", "news_any", "news_cat",
                            "fill", "stop", "out", "xkind", "dv_e", "dv_x", "m_e", "m_x")}
    for j, sym in enumerate(z["sym"]):
        a, b = int(z["off"][j]), int(z["off"][j + 1])
        if b - a < 20 or sym not in cands:
            continue
        mm = z["m"][a:b].astype(np.int64)
        oo, hh, ll, cc, vv = (z[x][a:b].astype(np.float64) for x in ("o", "h", "l", "c", "v"))
        cd = cands[sym]
        k, ei, mode, pat, gap, rv, px, vw, em, ee, fill, stp, out, xi, xk = symday_events(mm, oo, hh, ll, cc, vv, cd["pc"], cd["adv"])
        for q in range(k):
            i = int(ei[q])
            an, ca = _news_flags(by_sym.get(sym, []), sym, int(mm[i])) if news is not None else (False, False)
            cols["sd"].append(j); cols["m"].append(int(mm[i])); cols["mode"].append(mode[q]); cols["pat"].append(pat[q])
            cols["gap"].append(gap[q]); cols["rvol"].append(rv[q]); cols["px"].append(px[q]); cols["vwap"].append(vw[q])
            cols["ema"].append(em[q]); cols["news_any"].append(an); cols["news_cat"].append(ca)
            cols["fill"].append(fill[q]); cols["stop"].append(stp[q]); cols["out"].append(out[q]); cols["xkind"].append(xk[q])
            e = int(ee[q])
            cols["dv_e"].append(cc[e] * vv[e]); cols["m_e"].append(int(mm[e]))
            cols["dv_x"].append(cc[xi[q]] * vv[xi[q]]); cols["m_x"].append(mm[xi[q]])
    f.parent.mkdir(parents=True, exist_ok=True)
    n = len(cols["sd"])
    np.savez(f, day=np.full(n, di, np.int32), sd=np.array(cols["sd"], np.int32), m=np.array(cols["m"], np.int16),
             mode=np.array(cols["mode"], np.int8), pat=np.array(cols["pat"], np.int8),
             gap=np.array(cols["gap"], np.float32), rvol=np.array(cols["rvol"], np.float32), px=np.array(cols["px"], np.float32),
             vwap=np.array(cols["vwap"], np.int8), ema=np.array(cols["ema"], np.int8),
             news_any=np.array(cols["news_any"], np.int8), news_cat=np.array(cols["news_cat"], np.int8),
             has_news=np.int8(news is not None),
             fill=np.array(cols["fill"], np.float64), stop=np.array(cols["stop"], np.float64).reshape(n, 3),
             out=np.array(cols["out"], np.float64).reshape(n, 3, 4), xkind=np.array(cols["xkind"], np.int8).reshape(n, 3, 4),
             dv_e=np.array(cols["dv_e"], np.float32), m_e=np.array(cols["m_e"], np.int16),
             dv_x=np.array(cols["dv_x"], np.float32).reshape(n, 3, 4), m_x=np.array(cols["m_x"], np.int16).reshape(n, 3, 4))
    return str(f)


def build(workers=3):
    days = sessions()
    todo = [(i, d) for i, d in enumerate(days) if d >= START]
    with Pool(workers) as p:
        done = sum(1 for r in p.imap_unordered(day_events, todo, chunksize=4) if r)
    print("event days:", done)


if __name__ == "__main__":
    from backtestceo.momentum.events import build as _b
    _b()
