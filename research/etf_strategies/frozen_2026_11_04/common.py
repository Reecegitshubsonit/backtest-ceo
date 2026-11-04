"""Shared data, splits and fast (vectorized) engines for the 100k-combination search.
Search engines approximate the exact drift engine (weights held at target between rebalances); finalists are rerun
on the exact engine for the holdout. Holdout days are never stored or printed by the search (sealed)."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import backtest as bt  # noqa: E402

CKPT = ROOT.parent.parent.parent / "data" / "search_ckpt_frozen"   # gitignored
CKPT.mkdir(parents=True, exist_ok=True)
COST_D, COST_I = 0.0003, 0.00005
SCORE_START = "2017-02-01"
END = "2026-11-03"          # last complete session; fixed for reproducibility      # 252+21-day lookbacks need 2016 as warm-up

# ETF universes, each fixed by a rule that predates the data
UNIVERSES = {
    "SPY": ["SPY"],
    "SECT10": ["XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY", "XLRE"],  # Select Sector SPDRs listed before 2016
    "GTAA5": ["SPY", "EFA", "IEF", "VNQ", "DBC"],    # Faber (2007)
    "GEM3": ["SPY", "VEU", "AGG"],                     # Antonacci (2014) dual momentum
}
UNIVERSES["ALL16"] = UNIVERSES["SECT10"] + ["EFA", "IEF", "VNQ", "DBC", "VEU", "AGG"]
SYMS = sorted(set(sum(UNIVERSES.values(), [])) | {"SPY", "SSO", "BIL"})


def fetch(sym, tf):
    """Use any cached full-history file fetched on/after END (data is cut at END anyway), else fetch."""
    import glob, json as _j
    fs = sorted(glob.glob(str(bt.CACHE / f"{sym}_{tf}_2016-01-01_now_*.json")))
    fs = [f for f in fs if f.rsplit("_", 1)[1][:10] >= END]
    if fs:
        df = pd.DataFrame(_j.loads(Path(fs[-1]).read_text())); df["t"] = pd.to_datetime(df["t"], utc=True)
        return df.set_index("t")[["o", "h", "l", "c", "v"]]
    return bt.fetch(sym, tf, "2016-01-01")


def panel():
    o, h, l, c = {}, {}, {}, {}
    for s in SYMS:
        d = fetch(s, "1Day")
        d.index = d.index.tz_convert("America/New_York").normalize().tz_localize(None)
        o[s], h[s], l[s], c[s] = d["o"], d["h"], d["l"], d["c"]
    O, H, L, C = (pd.DataFrame(x) for x in (o, h, l, c))
    idx = C["SPY"].dropna().index
    idx = idx[idx <= END]
    return O.reindex(idx), H.reindex(idx), L.reindex(idx), C.reindex(idx)


def splits(idx):
    s = np.where(idx >= SCORE_START)[0]
    n = len(s); a, b = s[0] + int(n * 0.6), s[0] + int(n * 0.8)
    return {"search": (s[0], a), "validate": (a, b), "holdout": (b, len(idx))}


class Daily:
    """Precomputed daily arrays/features. Columns follow SYMS."""

    def __init__(self, O, H, L, C):
        self.idx = C.index; self.cols = list(C.columns); self.ci = {s: i for i, s in enumerate(self.cols)}
        self.O, self.H, self.L, self.C = (x.values.astype(float) for x in (O, H, L, C))
        self.gap = np.nan_to_num(self.O / np.vstack([np.full(len(self.cols), np.nan), self.C[:-1]]) - 1)
        self.intra = np.nan_to_num(self.C / self.O - 1)
        self.r = np.nan_to_num(C.pct_change().values)
        self.rf = self.r[:, self.ci["BIL"]].copy()
        self.T = len(self.idx); self.sp = splits(self.idx)
        self._cache = {}
        d = pd.Series(self.idx)
        wk = d.dt.isocalendar().week.values.astype(int); mo = d.dt.month.values.astype(int)
        last_wk = wk != np.r_[wk[1:], -1]; last_mo = mo != np.r_[mo[1:], -1]
        self.mask = {"daily": np.ones(self.T, bool), "weekly": last_wk, "monthly": last_mo,
                     "quarterly": last_mo & np.isin(mo, [3, 6, 9, 12])}

    def f(self, key, fn):
        if key not in self._cache: self._cache[key] = fn()
        return self._cache[key]

    def sma(self, n): return self.f(("sma", n), lambda: pd.DataFrame(self.C).rolling(n).mean().values)
    def vol(self, n): return self.f(("vol", n), lambda: pd.DataFrame(self.r).rolling(n).std().values * np.sqrt(252))

    def rsi(self, n):
        def g():
            d = pd.DataFrame(self.C).diff()
            up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean(); dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
            return (100 - 100 / (1 + up / dn)).values
        return self.f(("rsi", n), g)

    def z(self, n):
        return self.f(("z", n), lambda: ((pd.DataFrame(self.C) - pd.DataFrame(self.C).rolling(n).mean()) / pd.DataFrame(self.C).rolling(n).std()).values)

    def run(self, W, cost=COST_D):
        """W: T x N target weights decided at each close (NaN rows -> carry). Executed next open; returns daily total return."""
        W = pd.DataFrame(W).ffill().fillna(0.0).values
        held = np.vstack([np.zeros((1, W.shape[1])), W[:-1]]); prev = np.vstack([np.zeros((1, W.shape[1])), held[:-1]])
        turn = np.abs(held - prev).sum(1)
        ret = (prev * self.gap).sum(1) + (held * self.intra).sum(1) + (1 - held.sum(1)) * self.rf - cost * turn
        changes = ((held > 1e-9) != (prev > 1e-9)).sum(1)
        return ret, changes


def mom_fix(D, n, skip):
    """Return from t-n to t-skip, NaN where history is missing (np.roll wraps, so blank the first n rows)."""
    key = ("momf", n, skip)
    if key not in D._cache:
        C = D.C
        a = np.full_like(C, np.nan); a[n:] = C[n - skip:len(C) - skip] / C[:len(C) - n] - 1 if skip else C[n:] / C[:-n] - 1
        D._cache[key] = a
    return D._cache[key]


def sharpe(x):
    s = x.std()
    return x.mean() / s * np.sqrt(252) if s > 0 else 0.0


def stats_split(ret_ex, rng):
    a, b = rng; x = ret_ex[a:b]
    return sharpe(x)
