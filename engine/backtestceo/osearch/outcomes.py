"""Precompute every trade outcome the search can ask for.

For every entry (symbol, day, entry time, DTE bucket) and every structure (spread type x side x delta x wing)
the position is simulated once on 30-min option bars; the 16 profit-target x stop combinations are resolved
from the same mark path. The search then only gathers rows from these tables.

Fills: buy at modelled ask, sell at modelled bid (trade-bar VWAP +- half-spread from spread.json; Alpaca has no
historical option quotes). Marks for target/stop decisions use the last trade price. Exits fill on the next
30-min bar. Positions not closed earlier settle at intrinsic on the expiry close (no exit cost).
Commission $0.65 + $0.03 regulatory per contract per side.

    python3 -m backtestceo.osearch.outcomes      # checkpointed per symbol; prints one line per symbol
"""
import json, math, sys, time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from datetime import date, datetime, timedelta

import numpy as np

from . import data as D

OUT = D.DIR / "outcomes"
TIMES = ["10:00", "12:00", "14:00", "15:30"]
SLOT = {t: (int(t[:2]) * 60 + int(t[3:]) - 570) // 30 for t in TIMES}       # 30-min slot index 0..12
BUCKETS = [0, 1, 7, 30]
DELTAS = [0.15, 0.25, 0.35, 0.50]
DWS = [0.05, 0.10]
FEE = 0.68
R = 0.045
CREDIT_PT, CREDIT_SL = [None, .25, .5, .75], [None, 1., 2., 3.]
DEBIT_PT, DEBIT_SL = [None, .5, 1., 2.], [None, .3, .5, .7]

# structure index table: (family, side, delta_i, dw_i)
STRUCTS = []
for fam in ("credit", "debit"):
    for side in (1, -1):
        for di in range(4):
            for wi in range(2): STRUCTS.append((fam, side, di, wi))
for side in (1, -1):
    for di in range(4): STRUCTS.append(("long", side, di, 0))
for di in range(4):
    for wi in range(2): STRUCTS.append(("condor", 0, di, wi))
for di in range(4): STRUCTS.append(("strangle", 0, di, 0))
NS = len(STRUCTS)


SPREAD_MULT = float(__import__("os").environ.get("SPREAD_MULT", 1))


def spread_model():
    """Half-spread (bid/ask) model. Alpaca has no historical option quotes and this account only sees the
    'indicative' feed, whose snapshot quotes are post-close and modified (see spread_model.md), so a fixed
    conservative rule is used: index ETFs max($0.01, 1% of price); single stocks max($0.02, 2% of price)."""
    def hs(sym, bucket, px):
        if sym in D.INDEX: h = np.maximum(0.01, 0.01 * px)
        else: h = np.maximum(0.02, 0.02 * px)
        return h * SPREAD_MULT
    return hs


# ------------------------------------------------------------- Black-Scholes
def _ncdf(x): return 0.5 * (1 + np.vectorize(math.erf)(x / math.sqrt(2))) if np.ndim(x) else 0.5 * (1 + math.erf(x / math.sqrt(2)))


try:
    from scipy.special import ndtr as ncdf
except Exception:                                    # pragma: no cover
    ncdf = _ncdf


def bs_price(S, K, T, sig, call):
    sq = sig * np.sqrt(T); d1 = (np.log(S / K) + (R + 0.5 * sig * sig) * T) / sq; d2 = d1 - sq
    c = S * ncdf(d1) - K * np.exp(-R * T) * ncdf(d2)
    return np.where(call, c, c - S + K * np.exp(-R * T))


def implied_delta(S, K, T, px, call):
    """Vectorised bisection IV -> BS delta. NaN where price is outside no-arbitrage bounds."""
    lo, hi = np.full(K.shape, 0.01), np.full(K.shape, 5.0)
    for _ in range(40):
        mid = (lo + hi) / 2; up = bs_price(S, K, T, mid, call) > px
        hi = np.where(up, mid, hi); lo = np.where(up, lo, mid)
    sig = (lo + hi) / 2
    ok = (sig > 0.011) & (sig < 4.9)
    d1 = (np.log(S / K) + (R + 0.5 * sig * sig) * T) / (sig * np.sqrt(T))
    delta = np.where(call, ncdf(d1), ncdf(d1) - 1)
    return np.where(ok, delta, np.nan)


# ------------------------------------------------------------- per expiry tape
class Tape:
    def __init__(self, raw, days):
        """days: trading days covered (window start .. expiry). Grid = days x 13 slots."""
        self.days = days; self.dpos = {d: i for i, d in enumerate(days)}
        n = len(days) * 13
        self.sym, self.right, self.strike, vw, cl = [], [], [], [], []
        base = {}
        for i, d in enumerate(days):
            t0 = int(datetime(d.year, d.month, d.day, 9, 30, tzinfo=D.NY).timestamp() // 60)
            base[t0] = i
        day0 = {}
        for s, rows in raw.items():
            if not rows: continue
            v = np.full(n, np.nan); c = np.full(n, np.nan)
            for t, o, h, l, cc, vol, w in rows:
                dt = datetime.fromtimestamp(t * 60, D.NY)
                i = self.dpos.get(dt.date())
                if i is None: continue
                sl = (dt.hour * 60 + dt.minute - 570) // 30
                if 0 <= sl < 13: v[i * 13 + sl] = w; c[i * 13 + sl] = cc
            if np.isnan(c).all(): continue
            self.sym.append(s); self.right.append(s[-9] == "C"); self.strike.append(int(s[-8:]) / 1000)
            vw.append(v); cl.append(c)
        if not self.sym: self.n = 0; return
        self.n = len(self.sym)
        self.right = np.array(self.right); self.strike = np.array(self.strike)
        self.vw = np.array(vw); cl = np.array(cl)
        # forward-filled close = mark
        idx = np.where(~np.isnan(cl), np.arange(n), 0); np.maximum.accumulate(idx, axis=1, out=idx)
        self.mark = cl[np.arange(self.n)[:, None], idx]
        self.mark[:, :][np.isnan(cl[np.arange(self.n)[:, None], idx])] = np.nan
        # price we can fill at on slot t: that slot's VWAP, else the last mark
        self.fillpx = np.where(np.isnan(self.vw), self.mark, self.vw)


# ------------------------------------------------------------- simulation
def resolve(pnl_mark, exit_pnl, settle_pnl, scale, pts, sls):
    """pnl_mark[t]: mark P&L after slot t; exit_pnl[t]: realised P&L if trigger at t (fill on t+1).
    Returns (16,) pnl and (16,) exit slot offset (-1 = settled)."""
    n = len(pnl_mark)
    first = lambda m: int(np.argmax(m)) if m.any() else n
    ipt = [n if k is None else first(pnl_mark >= k * scale) for k in pts]
    isl = [n if k is None else first(pnl_mark <= -k * scale) for k in sls]
    out = np.empty(16, np.float32); ex = np.empty(16, np.int32)
    for a in range(4):
        for b in range(4):
            j = min(ipt[a], isl[b])
            if j >= n - 1: out[a * 4 + b] = settle_pnl; ex[a * 4 + b] = -1
            else: out[a * 4 + b] = exit_pnl[j]; ex[a * 4 + b] = j + 1
    return out, ex


def run_symbol(sym):
    path = OUT / f"{sym}.npz"
    if path.exists(): return sym, "cached"
    hs = spread_model()
    u = D.underlying(sym)
    tdays_all = [D.ts(r["t"]).date() for r in D.underlying("SPY")["1d"]]
    tidx_all = {d: i for i, d in enumerate(tdays_all)}
    days = [d for d in tdays_all if D.FIRST_EXP <= d <= D.LAST_DAY]
    gidx = {d: i for i, d in enumerate(days)}
    exps = D.expiries(sym, tdays_all)
    # split factor raw/adjusted per day: skip positions whose life spans a split (contracts get renamed)
    adjc = {D.ts(r["t"]).date(): r["c"] for r in u["1d"]}
    fac = {D.ts(r["t"]).date(): r["c"] / adjc[D.ts(r["t"]).date()] for r in u["1d-raw"] if D.ts(r["t"]).date() in adjc}
    bars = defaultdict(dict)
    for r in u["30m"]:
        t = D.ts(r["t"]); sl = (t.hour * 60 + t.minute - 570) // 30
        if 0 <= sl < 13: bars[t.date()][sl] = r
    # group entries by expiry
    work = defaultdict(list)
    for d in days:
        if len(bars[d]) < 12: continue
        for b in BUCKETS:
            e = D.bucket_expiry(sym, d, b, exps, tidx_all)
            if e is None or e > D.LAST_DAY: continue
            if abs(fac.get(d, 1) / fac.get(e, 1) - 1) > 0.01: continue
            work[e].append((d, b))
    rows_key, rows_pnl, rows_exit, rows_risk = [], [], [], []
    for e in sorted(work):
        f = D.DIR / f"opt/{sym}/{e}.json.gz"
        if not f.exists(): continue
        raw = D.load_json(f)
        start = min(d for d, _ in work[e])
        tdays = [d for d in days if start <= d <= e]
        if not tdays or tdays[-1] != e: continue
        tape = Tape(raw, tdays)
        if tape.n < 4: continue
        settle_px = bars[e].get(12, {}).get("c")
        if settle_px is None: continue
        intrinsic = np.where(tape.right, np.maximum(settle_px - tape.strike, 0), np.maximum(tape.strike - settle_px, 0))
        for d, b in work[e]:
            for ti, tname in enumerate(TIMES):
                sl = SLOT[tname]
                if sl - 1 not in bars[d]: continue
                S = bars[d][sl - 1]["c"]
                g = tape.dpos[d] * 13 + sl
                px = tape.fillpx[:, g]
                # don't fill on a print older than this session
                fresh = ~np.isnan(tape.vw[:, tape.dpos[d] * 13: g + 1]).all(axis=1)
                ok = ~np.isnan(px) & fresh & (px > 0)
                if ok.sum() < 4: continue
                mins_left = (13 - sl) * 30 + 390 * (len(tdays) - 1 - tape.dpos[d])
                T = max(mins_left, 15) / (390 * 252)
                delta = np.full(tape.n, np.nan)
                delta[ok] = implied_delta(S, tape.strike[ok], T, px[ok], tape.right[ok])
                half = hs(sym, b, np.nan_to_num(px))
                key = (sym, gidx[d], ti, b)
                res = simulate(tape, g, delta, px, half, intrinsic, b, sym, hs)
                if res is None: continue
                pnl, ex, risk = res
                # exit slot -> global day index
                exd = np.where(ex < 0, gidx[e], 0)
                for k in np.argwhere(ex >= 0): exd[tuple(k)] = gidx[tape.days[(g + ex[tuple(k)]) // 13]]
                rows_key.append(key[1:]); rows_pnl.append(pnl); rows_exit.append(exd.astype(np.int16)); rows_risk.append(risk)
    OUT.mkdir(parents=True, exist_ok=True)
    key = np.array(rows_key, np.int16).reshape(-1, 3)
    np.savez_compressed(path, key=key, pnl=np.array(rows_pnl, np.float32).reshape(-1, NS, 16),
                        exit=np.array(rows_exit, np.int16).reshape(-1, NS, 16),
                        risk=np.array(rows_risk, np.float32).reshape(-1, NS))
    return sym, f"{len(rows_key)} entries"


def pick(delta, right, target, call):
    """index of contract whose |delta| is closest to target on the given side; None if > max(0.07, 40%) away."""
    m = (right == call) & ~np.isnan(delta)
    if not m.any(): return None
    cand = np.where(m)[0]; err = np.abs(np.abs(delta[cand]) - target)
    j = cand[np.argmin(err)]
    return int(j) if err.min() <= max(0.07, 0.4 * target) else None


def simulate(tape, g, delta, px, half, intrinsic, bucket, sym, hs):
    """All NS structures for one entry. Returns pnl (NS,16), exit offset (NS,16), risk (NS,)."""
    pnl = np.full((NS, 16), np.nan, np.float32); ex = np.full((NS, 16), -1, np.int32); risk = np.full(NS, np.nan, np.float32)
    end = tape.mark.shape[1]
    mk = tape.mark[:, g:end]; fp = tape.fillpx[:, g:end]
    cache = {}
    def leg(call, tgt):
        k = (call, tgt)
        if k not in cache: cache[k] = pick(delta, tape.right, tgt, call)
        return cache[k]
    for si, (fam, side, di, wi) in enumerate(STRUCTS):
        d0, dw = DELTAS[di], DWS[wi]
        legs = []                                              # (contract index, qty)
        if fam == "credit":
            call = side == -1; a, bb = leg(call, d0), leg(call, max(d0 - dw, 0.03))
            if a is None or bb is None or a == bb: continue
            if (tape.strike[bb] > tape.strike[a]) != call: continue
            legs = [(a, -1), (bb, 1)]
        elif fam == "debit":
            call = side == 1; a, bb = leg(call, d0), leg(call, max(d0 - dw, 0.03))
            if a is None or bb is None or a == bb: continue
            if (tape.strike[bb] > tape.strike[a]) != call: continue
            legs = [(a, 1), (bb, -1)]
        elif fam == "long":
            a = leg(side == 1, d0)
            if a is None: continue
            legs = [(a, 1)]
        elif fam == "condor":
            ps, pl, cs, cl = leg(False, d0), leg(False, max(d0 - dw, .03)), leg(True, d0), leg(True, max(d0 - dw, .03))
            if None in (ps, pl, cs, cl) or len({ps, pl, cs, cl}) < 4: continue
            if not (tape.strike[pl] < tape.strike[ps] and tape.strike[cl] > tape.strike[cs]): continue
            legs = [(ps, -1), (pl, 1), (cs, -1), (cl, 1)]
        else:
            a, bb = leg(True, d0), leg(False, d0)
            if a is None or bb is None: continue
            legs = [(a, 1), (bb, 1)]
        idx = np.array([l[0] for l in legs]); q = np.array([l[1] for l in legs], float)
        mid0 = px[idx]
        efill = mid0 + q * half[idx]                       # buy at ask (q>0), sell at bid (q<0)
        net0 = float((q * mid0).sum())                     # >0 debit, <0 credit
        credit_fam = fam in ("credit", "condor")
        scale = (-net0 if credit_fam else net0) * 100
        if scale <= 1.0: continue
        m = np.where(np.isnan(mk[idx]), mid0[:, None], mk[idx])
        pnl_mark = ((m - mid0[:, None]) * q[:, None]).sum(0) * 100
        # exit at t -> fill on t+1 (last slot: use own mark)
        nf = np.concatenate([fp[idx][:, 1:], fp[idx][:, -1:]], axis=1)
        nf = np.where(np.isnan(nf), m, nf)
        hx = hs(sym, bucket, np.maximum(nf, 0.0))
        xfill = np.maximum(nf - q[:, None] * hx, 0)        # close long at bid, short at ask
        fees_in = FEE * len(legs)
        exit_pnl = ((xfill - efill[:, None]) * q[:, None]).sum(0) * 100 - fees_in - FEE * len(legs)
        settle = float(((intrinsic[idx] - efill) * q).sum() * 100 - fees_in)
        pts, sls = (CREDIT_PT, CREDIT_SL) if credit_fam else (DEBIT_PT, DEBIT_SL)
        p, e = resolve(pnl_mark, exit_pnl, settle, scale, pts, sls)
        pnl[si], ex[si] = p, np.where(e < 0, -1, e)
        if fam == "credit": risk[si] = abs(tape.strike[legs[0][0]] - tape.strike[legs[1][0]]) * 100 - scale
        elif fam == "condor":
            risk[si] = max(tape.strike[ps] - tape.strike[pl], tape.strike[cl] - tape.strike[cs]) * 100 - scale
        else: risk[si] = scale
        risk[si] = max(risk[si], 1.0)
    if np.isnan(pnl).all(): return None
    return pnl, ex, risk


def main():
    t0 = time.time()
    with ProcessPoolExecutor(4) as exe:
        for sym, msg in exe.map(run_symbol, sorted(D.SYMBOLS, key=lambda s: s not in D.INDEX)):
            print(f"{sym}: {msg} ({(time.time()-t0)/60:.1f} min)", flush=True)


if __name__ == "__main__":
    main()
