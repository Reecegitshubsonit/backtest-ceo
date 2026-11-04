"""Intraday families on 5-min SIP RTH bars (SPY, QQQ: the instruments of the source papers). Vectorized across days.
Costs 0.5 bp/side x leverage. Flat every night. Returns daily P&L (excess of cash, which earns T-bills overnight)."""
import itertools
import warnings
warnings.filterwarnings("ignore", category=RuntimeWarning)
import numpy as np
import pandas as pd
from common import bt, COST_I, END, fetch

NB = 78


class Bars:
    def __init__(self, sym, shuffle_seed=None):
        d = fetch(sym, "5Min")
        d.index = d.index.tz_convert("America/New_York")
        d = d.between_time("09:30", "15:55")
        d = d[d.index.normalize().tz_localize(None) <= END]
        day = d.index.normalize().tz_localize(None)
        k = ((d.index.hour * 60 + d.index.minute) - 570) // 5
        days = pd.Index(sorted(set(day)))
        di = days.get_indexer(day)
        A = {f: np.full((len(days), NB), np.nan) for f in "ohlcv"}
        for f in "ohlcv": A[f][di, k] = d[f].values
        first_ok = ~np.isnan(A["o"][:, 0])
        for t in range(1, NB):     # forward-fill rare missing bars inside a session (flat bar at last close)
            m = np.isnan(A["c"][:, t]) & ~np.isnan(A["c"][:, t - 1]) & ~np.isnan(A["c"][:, t:]).all(1)
            for f in "ohlc": A[f][m, t] = A["c"][m, t - 1]
            A["v"][m, t] = 0
        nbar = (~np.isnan(A["c"])).sum(1)
        keep = first_ok & (nbar >= 40)
        self.days = days[keep]; self.o, self.h, self.l, self.c, self.v = (A[f][keep] for f in "ohlcv")
        self.nb = nbar[keep]
        if shuffle_seed is not None: self._shuffle(shuffle_seed)
        self._derive()

    def _shuffle(self, seed):
        """Luck benchmark: permute the order of sessions AND the order of 5-min bars inside each session, then rebuild
        prices from the permuted bar ratios. The overnight gap stays at the open (moving it into the session would hand
        intraday longs SPY's overnight drift: an artifact found and fixed on 2026-11-04). Keeps the return distribution,
        destroys intraday time structure."""
        rng = np.random.default_rng(seed); Dn = len(self.days)
        last = self.c[np.arange(Dn), self.nb - 1]; pc = np.r_[self.o[0, 0], last[:-1]]
        prevc = np.concatenate([pc[:, None], self.c[:, :-1]], 1)
        g, i_, hb, lb = self.o / prevc, self.c / self.o, self.h / self.o, self.l / self.o
        order = rng.permutation(Dn)
        g, i_, hb, lb, v, nb = g[order], i_[order], hb[order], lb[order], self.v[order], self.nb[order]
        for d in range(Dn):        # the overnight gap (g[:, 0]) stays at the open; in-session bars are permuted
            n = nb[d]; p = rng.permutation(n); q = 1 + rng.permutation(n - 1)
            for a in (i_, hb, lb, v): a[d, :n] = a[d, :n][p]
            g[d, 1:n] = g[d, q]
        o, c = np.full_like(g, np.nan), np.full_like(g, np.nan); prev = pc[0]
        for d in range(Dn):
            n = nb[d]
            for k in range(n):
                o[d, k] = prev * g[d, k]; c[d, k] = o[d, k] * i_[d, k]; prev = c[d, k]
        self.o, self.c, self.h, self.l, self.v, self.nb = o, c, o * hb, o * lb, v, nb

    def _derive(self):
        D = len(self.days); J = np.arange(NB)
        self.J = J
        self.last_c = self.c[np.arange(D), self.nb - 1]
        self.pc = np.r_[np.nan, self.last_c[:-1]]
        self.o0 = self.o[:, 0]
        self.gap = self.o0 / self.pc - 1
        dr = pd.Series(self.last_c).pct_change()
        self.sig_d = dr.rolling(14).std().shift(1).values                      # known before the open
        rng = (np.nanmax(self.h, 1) - np.nanmin(self.l, 1)) / self.last_c
        avg = pd.Series(rng).rolling(14).mean().shift(1)
        lo = avg.rolling(252, min_periods=126).quantile(1 / 3)
        self.quiet = (avg < lo).fillna(False).values                            # trailing-quiet regime, past data only
        tr = np.maximum(np.nanmax(self.h, 1), self.pc) - np.minimum(np.nanmin(self.l, 1), self.pc)
        self.atr = pd.Series(tr).rolling(14).mean().shift(1).values
        tp = (self.h + self.l + self.c) / 3
        self.vwap = np.nancumsum(tp * self.v, 1) / np.maximum(np.nancumsum(self.v, 1), 1)
        mv = np.abs(self.c / self.o0[:, None] - 1)
        self.sigt = {n: pd.DataFrame(mv).rolling(n, min_periods=n).mean().shift(1).values for n in (7, 10, 14, 21)}
        self.valid = ~np.isnan(self.pc) & ~np.isnan(self.sig_d) & ~np.isnan(self.atr)


class ORB:
    name = "I1_orb"
    PARAMS = {"orbars": [1, 2, 3, 6], "dir": ["both", "long", "short"], "entry": ["candle", "break"],
              "stop": ["opp", "mid", "atr05", "atr10", "atr25"], "target": [None, 2, 3, 5, 10], "quiet": [False, True],
              "gapf": ["none", "with", "against"], "size": ["1x", "risk1"], "sym": ["SPY", "QQQ"]}
    ORDINAL = {"orbars", "target", "stop"}

    @staticmethod
    def valid(p): return True

    @staticmethod
    def pnl(B, p):
        Dn = len(B.days); ar = np.arange(Dn); m = p["orbars"]
        orh = np.nanmax(B.h[:, :m], 1); orl = np.nanmin(B.l[:, :m], 1)
        if p["entry"] == "candle":
            side = np.sign(B.c[:, m - 1] - B.o0); ek = np.full(Dn, m); entry = B.o[:, m]
        else:
            after = (B.J[None, :] >= m) & (B.J[None, :] < B.nb[:, None])
            up = after & (B.h > orh[:, None]); dn = after & (B.l < orl[:, None])
            ku = np.where(up.any(1), up.argmax(1), 999); kd = np.where(dn.any(1), dn.argmax(1), 999)
            side = np.where(ku < kd, 1, np.where(kd < ku, -1, 0)); ek = np.minimum(ku, kd)
            eki = np.minimum(ek, NB - 1)
            entry = np.where(side == 1, np.maximum(B.o[ar, eki], orh), np.minimum(B.o[ar, eki], orl))
        if p["dir"] == "long": side = np.where(side > 0, side, 0)
        if p["dir"] == "short": side = np.where(side < 0, side, 0)
        if p["gapf"] == "with": side = np.where(np.sign(B.gap) == side, side, 0)
        if p["gapf"] == "against": side = np.where(np.sign(B.gap) == -side, side, 0)
        if p["quiet"]: side = np.where(B.quiet, 0, side)
        side = np.where(B.valid & (ek < B.nb - 1), side, 0)
        st = p["stop"]
        if st == "opp": stop = np.where(side > 0, orl, orh)
        elif st == "mid": stop = (orh + orl) / 2
        else: stop = entry - side * float(st[3:]) / 100 * B.atr
        R = (entry - stop) * side
        side = np.where(R > 0, side, 0); R = np.where(R > 0, R, np.nan)
        tgt = entry + side * p["target"] * R if p["target"] else np.full(Dn, np.nan)
        eki = np.minimum(ek, NB - 1)
        live = (B.J[None, :] >= eki[:, None]) & (B.J[None, :] < B.nb[:, None])
        # Candle entries (at a bar open): stop and target checked from the entry bar, stop wins ties (conservative).
        # Stop-entry breakouts: the trigger bar is resolved with the standard OHLC path convention (up bar O-L-H-C,
        # down bar O-H-L-C). For a long, the target counts if the bar's high reaches it; otherwise the stop counts only
        # if the path reaches it after the entry (up bar: close at/below stop; down bar: low at/below stop). Shorts mirror.
        # Later bars: stop wins ties. (A first version took the worst case on the trigger bar and pushed tight-stop
        # breakouts to Sharpe -11: lows printed before the breakout were counted as stops after it.)
        L_ = side[:, None] > 0
        if p["entry"] == "candle":
            live_n = live
        else:
            live_n = live & (B.J[None, :] > eki[:, None])
        hs = live_n & np.where(L_, B.l <= stop[:, None], B.h >= stop[:, None])
        ht = live_n & np.where(L_, B.h >= tgt[:, None], B.l <= tgt[:, None])
        if p["entry"] == "break":
            to, th, tl, tc = B.o[ar, eki], B.h[ar, eki], B.l[ar, eki], B.c[ar, eki]
            upbar = tc > to
            t_hit = np.where(side > 0, th >= tgt, tl <= tgt)
            s_hit = np.where(side > 0, np.where(upbar, tc <= stop, tl <= stop), np.where(upbar, th >= stop, tc >= stop))
            ht[ar, eki] |= t_hit & (side != 0)
            hs[ar, eki] |= s_hit & ~t_hit & (side != 0)
        ks = np.where(hs.any(1), hs.argmax(1), 999); kt = np.where(ht.any(1), ht.argmax(1), 999)
        ksi, kti = np.minimum(ks, NB - 1), np.minimum(kt, NB - 1)
        sx = np.where(side > 0, np.minimum(B.o[ar, ksi], stop), np.maximum(B.o[ar, ksi], stop))
        sx = np.where(ksi == eki, stop, sx)                       # stop on the entry bar fills at the stop
        tx = np.where(side > 0, np.maximum(B.o[ar, kti], tgt), np.minimum(B.o[ar, kti], tgt))
        tx = np.where(kti == eki, tgt, tx)
        ex = np.where((ks < 999) & (ks <= kt), sx, np.where(kt < 999, tx, B.last_c))
        lev = np.where(side != 0, 1.0 if p["size"] == "1x" else np.minimum(4, 0.01 / (R / entry)), 0)
        lev = np.nan_to_num(lev)
        r = np.where(side != 0, lev * side * (ex / entry - 1) - 2 * COST_I * lev, 0.0)
        return pd.Series(np.nan_to_num(r), index=B.days), int((side != 0).sum())


class NoiseBand:
    name = "I2_noiseband"
    PARAMS = {"look": [7, 10, 14, 21], "mult": [0.75, 1.0, 1.25, 1.5], "freq": [3, 6, 12], "stop": ["band", "vwap", "max"],
              "last": [35, 71], "quiet": [False, True], "size": ["1x", "vol2"], "side": ["both", "long"], "sym": ["SPY", "QQQ"]}
    ORDINAL = {"look", "mult", "freq"}

    @staticmethod
    def valid(p): return True

    @staticmethod
    def pnl(B, p):
        Dn = len(B.days)
        s = B.sigt[p["look"]] * p["mult"]
        ub = np.maximum(B.o0, B.pc)[:, None] * (1 + s); lb = np.minimum(B.o0, B.pc)[:, None] * (1 - s)
        lev = np.ones(Dn) if p["size"] == "1x" else np.minimum(4, 0.02 / B.sig_d)
        ok = B.valid & ~np.isnan(s[:, 5]) & ~(B.quiet if p["quiet"] else np.zeros(Dn, bool))
        pos = np.zeros(Dn); entry = np.zeros(Dn); pnl = np.zeros(Dn); n = 0
        for k in range(5, NB - 1):
            if (k + 1) % p["freq"] != 0: continue
            act = ok & (k < B.nb - 1)
            c, u, l_, vw = B.c[:, k], ub[:, k], lb[:, k], B.vwap[:, k]
            lstop = {"band": u, "vwap": vw, "max": np.maximum(u, vw)}[p["stop"]]
            sstop = {"band": l_, "vwap": vw, "max": np.minimum(l_, vw)}[p["stop"]]
            new = pos.copy()
            new = np.where((pos == 1) & (c < lstop), 0, new); new = np.where((pos == -1) & (c > sstop), 0, new)
            can = (new == 0) & (k <= p["last"])
            new = np.where(can & (c > u), 1, new)
            if p["side"] == "both": new = np.where(can & (c < l_), -1, new)
            new = np.where(act, new, pos)
            px = B.o[:, k + 1]
            closing = act & (new != pos) & (pos != 0)
            pnl += np.where(closing, lev * pos * (px / entry - 1) - 2 * COST_I * lev, 0)
            opening = act & (new != pos) & (new != 0)
            n += int(opening.sum())
            entry = np.where(opening, px, entry); pos = np.where(act, new, pos)
        pnl += np.where(pos != 0, lev * pos * (B.last_c / entry - 1) - 2 * COST_I * lev, 0)
        return pd.Series(np.nan_to_num(pnl), index=B.days), n


FAMILIES = [ORB, NoiseBand]


def grid(F):
    keys = list(F.PARAMS)
    for vals in itertools.product(*[F.PARAMS[k] for k in keys]):
        p = dict(zip(keys, vals))
        if F.valid(p): yield p


if __name__ == "__main__":
    for F in FAMILIES: print(F.name, sum(1 for _ in grid(F)))
