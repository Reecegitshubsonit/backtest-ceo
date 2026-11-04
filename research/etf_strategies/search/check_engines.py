"""Fidelity check: fast search engines vs the exact engines used in rounds 2-5."""
import numpy as np, pandas as pd
import common as cm, families_daily as fd, families_intraday as fi

O, H, L, C = cm.panel(); D = cm.Daily(O, H, L, C)
sl = D.idx >= "2017-01-03"
def sh(ret): x = (ret - D.rf)[sl]; return cm.sharpe(x)
for name, F, p, ref in [
    ("SMA200 (round 2: 0.71)", fd.Trend, dict(signal="sma", L=200, weight="equal", rebal="daily", vt=None, univ="SPY"), 0.71),
    ("N1 vol target (round 3: 0.76)", fd.VolTarget, dict(tgt=0.15, est="sd21", cap=2.0, band=0.10, trend="none", rebal="daily"), 0.76),
    ("SPY B&H (0.73)", fd.Trend, dict(signal="sma", L=20, weight="equal", rebal="daily", vt=None, univ="SPY"), None)]:
    if ref is None:
        W = np.zeros((D.T, len(D.cols))); W[200:, D.ci["SPY"]] = 1
    else: W = F.weights(D, p)
    r, ch = D.run(W); print(f"{name}: fast-engine Sharpe {sh(r):.2f}")
for sym, F, p, ref in [("SPY", fi.NoiseBand, dict(look=14, mult=1.0, freq=6, stop="max", last=71, quiet=False, size="vol2", side="both", sym="SPY"), "I1b round 4: 0.69"),
                       ("QQQ", fi.ORB, dict(orbars=1, dir="both", entry="candle", stop="opp", target=10, quiet=False, gapf="none", size="risk1", sym="QQQ"), "I2b round 4: 0.57")]:
    B = fi.Bars(sym); pnl, n = F.pnl(B, p); x = pnl[pnl.index >= "2016-02-01"]
    print(f"{F.name} {sym}: fast-engine Sharpe {cm.sharpe(x):.2f}, trades {n} ({ref})")
