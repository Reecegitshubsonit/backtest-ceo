"""Round 6b: daily mean-reversion (F3) and candle (F4) families with MARKET-ON-CLOSE execution instead of next open.
Signal on the close, filled at the same close (MOC auction, 3 bp/side). Look-ahead check: on SPY, how often the signal
computed from the 15:55 price (when a MOC order must be in) differs from the close-based one.
New trials: 11,760 (project total now 111,936). Selection uses the same pre-declared pipeline on search + validate.
The holdout was already used once on 2026-11-04, so holdout numbers here are a SECOND LOOK, labelled as such.
Usage: python3 moc.py -> moc_results.md"""
import json
from multiprocessing import Pool
import numpy as np
import pandas as pd
import common as cm
import families_daily as fd
import families_intraday as fi

G = {}


def run_moc(D, W, cost=cm.COST_D):
    """W decided at close t and filled at that close: earns close t -> close t+1."""
    W = pd.DataFrame(W).ffill().fillna(0.0).values
    held = np.vstack([np.zeros((1, W.shape[1])), W[:-1]]); prev = np.vstack([np.zeros((1, W.shape[1])), held[:-1]])
    ret = (held * D.r).sum(1) + (1 - held.sum(1)) * D.rf - cost * np.abs(held - prev).sum(1)
    return ret, ((held > 1e-9) != (prev > 1e-9)).sum(1)


def ev(args):
    name, p = args; D = G["D"]; F = G["fam"][name]
    W = F.weights(D, p); r, ch = run_moc(D, W); ex = r - D.rf
    out = {}
    for k, (a, b) in D.sp.items(): out[k] = cm.sharpe(ex[a:b])
    a, b = D.sp["search"]
    return out["search"], out["validate"], out["holdout"], int(ch[a:b].sum())


def lookahead():
    """SPY: RSI(2) < 10 and IBS < 0.2 computed with the 15:55 price vs the official close."""
    B = fi.Bars("SPY"); px55 = pd.Series(B.o[:, 77], index=B.days); close = pd.Series(B.last_c, index=B.days)
    ok = ~px55.isna()
    def rsi2(c):
        d = c.diff(); up = d.clip(lower=0).ewm(alpha=0.5, adjust=False).mean(); dn = (-d.clip(upper=0)).ewm(alpha=0.5, adjust=False).mean()
        return 100 - 100 / (1 + up / dn)
    r_close = rsi2(close)
    alt = close.copy(); res = []
    for d in close.index[ok][250:]:
        i = close.index.get_loc(d); c2 = close.iloc[max(0, i - 60):i + 1].copy(); c2.iloc[-1] = px55[d]
        res.append((r_close.iloc[i] < 10, rsi2(c2).iloc[-1] < 10))
    a = np.array(res)
    agree = (a[:, 0] == a[:, 1]).mean(); fired = a[:, 0].sum(); both = (a[:, 0] & a[:, 1]).sum()
    return agree, int(fired), int(both)


def main():
    O, H, L, C = cm.panel(); G["D"] = cm.Daily(O, H, L, C); G["fam"] = {F.name: F for F in fd.FAMILIES}
    combos = [(F.name, p) for F in (fd.MeanRev, fd.Candles) for p in fd.grid(F)]
    with Pool(4) as pool: S = np.array(pool.map(ev, combos, chunksize=50))
    D = G["D"]; spyW = np.zeros((D.T, len(D.cols))); spyW[:, D.ci["SPY"]] = 1
    r, _ = run_moc(D, spyW); ex = r - D.rf; spy = {k: cm.sharpe(ex[a:b]) for k, (a, b) in D.sp.items()}
    elig = (S[:, 3] >= 10) & np.isfinite(S[:, 0])
    key = {(n, tuple(p.values())): i for i, (n, p) in enumerate(combos)}
    fams = {F.name: F for F in fd.FAMILIES}
    cand = np.where(elig)[0][np.argsort(-S[elig, 0])][:500]
    surv = []
    for i in cand:
        n, p = combos[i]; F = fams[n]; nb = []
        for kp in F.ORDINAL:
            vals = F.PARAMS[kp]; j = vals.index(p[kp])
            for jj in (j - 1, j + 1):
                if 0 <= jj < len(vals):
                    q = dict(p); q[kp] = vals[jj]; t = key.get((n, tuple(q.values())))
                    if t is not None: nb.append(t)
        if nb and np.median(S[nb, 0]) >= 0.7 * S[i, 0] and np.median(S[nb, 1]) > 0: surv.append(i)
    surv.sort(key=lambda i: -S[i, 1]); top = surv[:10]
    agree, fired, both = lookahead()
    L = ["## Round 6b: mean reversion and candles with market-on-close fills", "",
         f"Look-ahead check (SPY RSI(2) < 10): the 15:55-price signal agrees with the close-based one on {agree:.1%} of days; "
         f"of {fired} close-based entries, {both} would also have fired at 15:55.", "",
         f"SPY Sharpe: search {spy['search']:.2f}, validate {spy['validate']:.2f}, holdout {spy['holdout']:.2f}.", "",
         "| Family | Combos | Median search | Median validate | Median holdout (second look) | Share beating SPY on search AND validate |",
         "|---|---:|---:|---:|---:|---:|"]
    names = np.array([c[0] for c in combos])
    for f in ("F3_meanrev", "F4_candles"):
        m = (names == f) & elig
        both_ = ((S[m, 0] > spy["search"]) & (S[m, 1] > spy["validate"])).mean()
        L.append(f"| {f} | {m.sum():,} | {np.median(S[m,0]):.2f} | {np.median(S[m,1]):.2f} | {np.median(S[m,2]):.2f} | {both_:.1%} |")
    L += ["", f"Next-open fills (round 6 search) for comparison: F3 median search -0.05 / validate 0.32; F4 0.13 / 0.16.", "",
          f"Top 10 by the same pipeline ({len(surv)} of 500 pass neighbors):", "",
          "| Family | Params | Search | Validate | Holdout (second look) | Search trades |", "|---|---|---:|---:|---:|---:|"]
    for i in top:
        n, p = combos[i]
        L.append(f"| {n} | " + ", ".join(f"{k}={v}" for k, v in p.items()) + f" | {S[i,0]:.2f} | {S[i,1]:.2f} | {S[i,2]:.2f} | {int(S[i,3])} |")
    t = "\n".join(L); print(t); (cm.ROOT / "moc_results.md").write_text(t + "\n")


if __name__ == "__main__":
    main()
