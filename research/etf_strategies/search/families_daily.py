"""Daily strategy families and their parameter grids. Each family: PARAMS (ordered name -> values), ORDINAL (params whose
neighbors are the adjacent values), valid(p), weights(D, p) -> T x N target weights (columns = D.cols)."""
import itertools
import warnings
warnings.filterwarnings("ignore", category=RuntimeWarning)
import numpy as np
import pandas as pd
from common import UNIVERSES, mom_fix

LOOKS = [20, 50, 100, 150, 200, 252]
ROT_LOOKS = [21, 63, 126, 189, 252]
ROT_SETS = [c for k in range(1, 6) for c in itertools.combinations(ROT_LOOKS, k)]   # 31 blends


def _uidx(D, u): return [D.ci[s] for s in UNIVERSES[u]]


def _voltarget(D, W, tgt, cap=1.0, n=63):
    """Scale the whole book so its trailing realized vol (of the unscaled weights) is <= tgt (cap 1 = no leverage)."""
    if tgt is None: return W
    pr = np.nan_to_num((np.vstack([np.zeros((1, W.shape[1])), W[:-1]]) * D.r).sum(1))
    sig = pd.Series(pr).rolling(n).std().values * np.sqrt(252)
    k = np.clip(tgt / np.where(sig > 0, sig, np.nan), 0, cap)
    return W * np.nan_to_num(k, nan=0.0)[:, None]


def _rebal(D, W, freq):
    W = W.copy(); W[~D.mask[freq]] = np.nan
    return W


def _inv_vol(D, cols, sel):
    v = D.vol(63)[:, cols]; iv = np.where(v > 0, 1 / v, np.nan) * sel
    s = np.nansum(iv, 1, keepdims=True)
    return np.nan_to_num(np.where(s > 0, iv / s, 0.0))


class Trend:
    name = "F1_trend"
    PARAMS = {"signal": ["sma", "mom0", "mom21", "cross10", "cross20", "cross50"], "L": LOOKS,
              "weight": ["equal", "invvol"], "rebal": ["daily", "weekly", "monthly", "quarterly"],
              "vt": [None, 0.08, 0.10, 0.12, 0.15], "univ": ["SPY", "SECT10", "GTAA5", "GEM3", "ALL16"]}
    ORDINAL = {"L", "vt", "rebal"}

    @staticmethod
    def valid(p):
        if p["signal"].startswith("cross") and int(p["signal"][5:]) >= p["L"]: return False
        if p["signal"] == "mom21" and p["L"] <= 21: return False
        if p["univ"] == "SPY" and p["weight"] == "invvol": return False
        return True

    @staticmethod
    def weights(D, p):
        cols = _uidx(D, p["univ"]); C = D.C[:, cols]; L = p["L"]; sg = p["signal"]
        if sg == "sma": on = C > D.sma(L)[:, cols]
        elif sg.startswith("mom"): on = mom_fix(D, L, int(sg[3:]))[:, cols] > 0
        else: on = D.sma(int(sg[5:]))[:, cols] > D.sma(L)[:, cols]
        on = on & ~np.isnan(D.sma(L)[:, cols])
        w = on / len(cols) if p["weight"] == "equal" else _inv_vol(D, cols, np.ones_like(on, float)) * on
        W = np.zeros((D.T, len(D.cols))); W[:, cols] = w
        return _rebal(D, _voltarget(D, W, p["vt"]), p["rebal"])


class Rotation:
    name = "F2_rotation"
    PARAMS = {"looks": list(range(len(ROT_SETS))), "skip": [0, 21], "K": [1, 2, 3, 4, 5], "absf": ["none", "pos", "cash"],
              "weight": ["equal", "invvol"], "rebal": ["weekly", "monthly", "quarterly"], "vt": [None, 0.10, 0.15],
              "univ": ["SECT10", "GTAA5", "GEM3", "ALL16"]}
    ORDINAL = {"skip", "K", "rebal", "vt"}

    @staticmethod
    def valid(p): return p["K"] < len(UNIVERSES[p["univ"]])

    @staticmethod
    def weights(D, p):
        cols = _uidx(D, p["univ"]); looks = ROT_SETS[p["looks"]]
        sc = np.mean([mom_fix(D, n + p["skip"], p["skip"])[:, cols] for n in looks], 0)
        bil = D.ci["BIL"]
        cash = np.mean([mom_fix(D, n + p["skip"], p["skip"])[:, bil] for n in looks], 0)
        valid = ~np.isnan(sc).any(1)
        rank = np.argsort(np.argsort(-np.nan_to_num(sc, nan=-9), 1), 1)
        sel = (rank < p["K"]).astype(float)
        if p["absf"] == "pos": sel *= sc > 0
        elif p["absf"] == "cash": sel *= sc > cash[:, None]
        if p["weight"] == "equal": w = sel / p["K"]
        else:
            top = (rank < p["K"]).astype(float); w = _inv_vol(D, cols, top) * sel
        w[~valid] = 0
        W = np.zeros((D.T, len(D.cols))); W[:, cols] = w
        return _rebal(D, _voltarget(D, W, p["vt"]), p["rebal"])


IND = [("rsi2", 5), ("rsi2", 10), ("rsi2", 15), ("rsi2", 20), ("rsi2", 25), ("rsi3", 10), ("rsi3", 15), ("rsi3", 20), ("rsi3", 25),
       ("rsi5", 20), ("rsi5", 25), ("rsi5", 30), ("rsi14", 25), ("rsi14", 30), ("rsi14", 35)] + \
      [(f"z{n}", t) for n in (5, 10, 20) for t in (-1.0, -1.5, -2.0, -2.5)] + [("ibs", t) for t in (0.10, 0.15, 0.20, 0.25)] + \
      [("cdd", k) for k in (2, 3, 4, 5)]


class MeanRev:
    name = "F3_meanrev"
    PARAMS = {"ind": list(range(len(IND))), "exit": ["sma5", "revert", "upclose"], "maxhold": [2, 3, 5, 10, 20],
              "trend": ["none", "sma200", "sma100"], "sizing": ["slot", "allin"], "univ": ["SPY", "SECT10", "GTAA5", "ALL16"]}
    ORDINAL = {"ind", "maxhold"}

    @staticmethod
    def valid(p): return not (p["univ"] == "SPY" and p["sizing"] == "allin")

    @staticmethod
    def weights(D, p):
        cols = _uidx(D, p["univ"]); C = D.C[:, cols]; kind, th = IND[p["ind"]]
        H, L = D.H[:, cols], D.L[:, cols]
        if kind.startswith("rsi"): x = D.rsi(int(kind[3:]))[:, cols]; ent = x < th; rev = x > 50
        elif kind.startswith("z"): x = D.z(int(kind[1:]))[:, cols]; ent = x < th; rev = x > 0
        elif kind == "ibs": x = (C - L) / np.where(H > L, H - L, np.nan); ent = x < th; rev = x > 0.7
        else:
            dn = np.vstack([np.zeros((1, len(cols)), bool), C[1:] < C[:-1]])
            cnt = np.zeros(dn.shape)
            for t in range(1, D.T): cnt[t] = (cnt[t - 1] + 1) * dn[t]
            ent = cnt >= th; rev = np.vstack([np.zeros((1, len(cols)), bool), C[1:] > C[:-1]])
        up = np.vstack([np.zeros((1, len(cols)), bool), C[1:] > C[:-1]])
        ex = {"sma5": C > D.sma(5)[:, cols], "revert": rev, "upclose": up}[p["exit"]]
        if p["trend"] != "none": ent = ent & (C > D.sma(int(p["trend"][3:]))[:, cols])
        ent = ent & ~np.isnan(D.sma(200)[:, cols])
        pos = np.zeros(ent.shape); inpos = np.zeros(len(cols), bool); age = np.zeros(len(cols))
        for t in range(D.T):
            age = np.where(inpos, age + 1, 0)
            out = inpos & (ex[t] | (age >= p["maxhold"]))
            inpos = (inpos & ~out) | (~inpos & ent[t])
            age = np.where(out, 0, age); pos[t] = inpos
        if p["sizing"] == "slot": w = pos / len(cols)
        else:
            n = pos.sum(1, keepdims=True); w = np.where(n > 0, pos / np.maximum(n, 1), 0)
        W = np.zeros((D.T, len(D.cols))); W[:, cols] = w
        return W


PATTERNS = ["bull_engulf", "hammer", "inside_up", "nr7_up", "gap_reversal", "outside_up", "three_down_lowibs"]


class Candles:
    name = "F4_candles"
    PARAMS = {"pattern": PATTERNS, "hold": [1, 2, 3, 5, 10], "trend": ["none", "above200", "below200"],
              "sizing": ["slot", "allin"], "univ": ["SPY", "SECT10", "GTAA5", "ALL16"]}
    ORDINAL = {"hold"}

    @staticmethod
    def valid(p): return not (p["univ"] == "SPY" and p["sizing"] == "allin")

    @staticmethod
    def weights(D, p):
        cols = _uidx(D, p["univ"]); O, H, L, C = (x[:, cols] for x in (D.O, D.H, D.L, D.C))
        sh = lambda x, k=1: np.vstack([np.full((k, x.shape[1]), np.nan), x[:-k]])
        body = np.abs(C - O); rng = H - L
        pt = p["pattern"]
        with np.errstate(invalid="ignore"):
            if pt == "bull_engulf": s = (sh(C) < sh(O)) & (C > O) & (O <= sh(C)) & (C >= sh(O))
            elif pt == "hammer": s = ((np.minimum(O, C) - L) >= 2 * body) & ((H - np.maximum(O, C)) <= body) & (rng > 0)
            elif pt == "inside_up": s = (H < sh(H)) & (L > sh(L)) & (C > O)
            elif pt == "nr7_up": s = (rng <= pd.DataFrame(rng).rolling(7).min().values) & (C > O)
            elif pt == "gap_reversal": s = (O < sh(L)) & (C > O)
            elif pt == "outside_up": s = (H > sh(H)) & (L < sh(L)) & (C > sh(H))
            else: s = (C < sh(C)) & (sh(C) < sh(C, 2)) & (sh(C, 2) < sh(C, 3)) & ((C - L) / np.where(rng > 0, rng, np.nan) < 0.3)
            if p["trend"] == "above200": s = s & (C > D.sma(200)[:, cols])
            if p["trend"] == "below200": s = s & (C < D.sma(200)[:, cols])
        s = np.nan_to_num(s.astype(float)) * ~np.isnan(D.sma(200)[:, cols])
        pos = pd.DataFrame(s).rolling(p["hold"], min_periods=1).max().values > 0
        if p["sizing"] == "slot": w = pos / len(cols)
        else:
            n = pos.sum(1, keepdims=True); w = np.where(n > 0, pos / np.maximum(n, 1), 0)
        W = np.zeros((D.T, len(D.cols))); W[:, cols] = w
        return W


class VolTarget:
    name = "F5_voltarget"
    PARAMS = {"tgt": [0.08, 0.10, 0.12, 0.15, 0.18, 0.20, 0.25], "est": ["sd10", "sd21", "sd42", "sd63", "ew94", "ew97"],
              "cap": [1.0, 1.25, 1.5, 2.0], "band": [0.0, 0.05, 0.10, 0.20], "trend": ["none", "sma100", "sma200", "mom252", "cross50_200"],
              "rebal": ["daily", "weekly", "monthly"]}
    ORDINAL = {"tgt", "cap", "band", "rebal"}

    @staticmethod
    def valid(p): return True

    @staticmethod
    def weights(D, p):
        spy = D.ci["SPY"]; r = pd.Series(D.r[:, spy])
        e = p["est"]
        sig = (r.rolling(int(e[2:])).std() if e.startswith("sd") else np.sqrt((r ** 2).ewm(alpha=1 - int(e[2:]) / 100).mean())).values * np.sqrt(252)
        expo = np.clip(p["tgt"] / np.where(sig > 0, sig, np.nan), 0, p["cap"])
        c = D.C[:, spy]
        tr = {"none": np.ones(D.T, bool), "sma100": c > D.sma(100)[:, spy], "sma200": c > D.sma(200)[:, spy],
              "mom252": mom_fix(D, 252, 0)[:, spy] > 0, "cross50_200": D.sma(50)[:, spy] > D.sma(200)[:, spy]}[p["trend"]]
        expo = np.where(np.isnan(D.sma(200)[:, spy]) | np.isnan(expo), np.nan, expo * tr)
        out = np.full(D.T, np.nan); last = None
        m = D.mask[p["rebal"]]
        for t in range(D.T):
            x = expo[t]
            if np.isnan(x) or not m[t]: continue
            if last is None or abs(x - last) > p["band"] or ((x == 0) != (last == 0)): out[t] = last = x
        W = np.full((D.T, len(D.cols)), np.nan)
        ok = ~np.isnan(out)
        W[ok] = 0.0
        W[ok, spy] = np.where(out[ok] <= 1, out[ok], 2 - out[ok]); W[ok, D.ci["SSO"]] = np.where(out[ok] <= 1, 0, out[ok] - 1)
        return W


FAMILIES = [Trend, Rotation, MeanRev, Candles, VolTarget]


def grid(F):
    keys = list(F.PARAMS)
    for vals in itertools.product(*[F.PARAMS[k] for k in keys]):
        p = dict(zip(keys, vals))
        if F.valid(p): yield p


if __name__ == "__main__":
    tot = 0
    for F in FAMILIES:
        n = sum(1 for _ in grid(F)); tot += n; print(F.name, n)
    print("daily total", tot)
