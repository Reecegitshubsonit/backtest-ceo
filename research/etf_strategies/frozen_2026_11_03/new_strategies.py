"""Round 3: candidate strategies taken from research published BEFORE the 2017-2026 test window, with the papers'
default parameters (no tuning on this data). Same engine, costs, T-bill cash and bootstrap as backtest.py.
Leverage only through listed leveraged ETFs (SSO 2x, UPRO 3x S&P 500), so their fees, financing and daily-reset decay are in.

Run: python3 research/etf_strategies/new_strategies.py   -> new_results.md, new_results.csv
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import backtest as bt

LEV = ["SPY", "SSO", "UPRO"]


def sma_on(C):
    sma = C["SPY"].rolling(200).mean()
    on = (C["SPY"] > sma).astype(float)
    on[sma.isna()] = np.nan
    return on


def s_lev_trend(sym):
    """Gayed & Bilello (2016), 'Leverage for the Long Run': hold a leveraged S&P fund while SPY > its 200d SMA, else T-bills."""
    def f(C):
        on = sma_on(C)
        w = pd.DataFrame(0.0, index=C.index, columns=LEV)
        w[sym] = on
        w[on.isna()] = np.nan
        return w
    return f


def exposure_weights(e, idx):
    """Map S&P exposure e in [0, 2] onto SPY/SSO weights (no borrowing): e<=1 -> e SPY; e>1 -> (2-e) SPY + (e-1) SSO."""
    w = pd.DataFrame(0.0, index=idx, columns=LEV)
    w["SPY"] = np.where(e <= 1, e, 2 - e)
    w["SSO"] = np.where(e <= 1, 0.0, e - 1)
    return w


def banded(e, band=0.10):
    """Only re-trade when the target exposure moves more than `band` from the last traded exposure."""
    out = np.full(len(e), np.nan); last = None
    for i, x in enumerate(e):
        if np.isnan(x): continue
        if last is None or abs(x - last) > band or (x == 0) != (last == 0):
            out[i] = last = x
    return out


def vol_target(C, target=0.15, cap=2.0):
    r = C["SPY"].pct_change()
    sig = r.rolling(21).std() * np.sqrt(252)
    return (target / sig).clip(upper=cap)


def s_voltarget(C):
    """Harvey, Hoyle, Korgaonkar, Rattray, Sargaison, Van Hemert (2018, SSRN 2017) / Moreira & Muir (2017):
    S&P exposure = 15% / 21-day realized vol, capped at 2x (via SSO). Re-trade on a 10-point exposure move."""
    e = banded(vol_target(C).values)
    w = exposure_weights(np.nan_to_num(e), C.index)
    w[np.isnan(e)] = np.nan
    return w


def s_trend_voltarget(C):
    """Trend filter x vol target: the vol-target exposure while SPY > 200d SMA, else T-bills."""
    e = (vol_target(C) * sma_on(C)).values
    e = banded(e)
    w = exposure_weights(np.nan_to_num(e), C.index)
    w[np.isnan(e)] = np.nan
    return w


def s_tom(C, sym="SPY"):
    """Turn of the month, Lakonishok & Smidt (1988), McConnell & Xu (2008): hold over the last trading day of the
    month and the first 3 of the next; T-bills otherwise. Decided at the prior close (calendar known in advance),
    filled at the next open, so day -1's overnight gap is missed."""
    idx = C.index
    ym = idx.year * 12 + idx.month
    s = pd.Series(1, index=idx)
    from_start = s.groupby(ym).cumsum().values
    from_end = s[::-1].groupby(ym[::-1]).cumsum()[::-1].values
    hold = (from_end == 1) | (from_start <= 3)
    tgt = np.r_[hold[1:], False].astype(float)        # at close t, target = hold status of day t+1
    w = pd.DataFrame(0.0, index=idx, columns=LEV)
    w[sym] = tgt
    return w


def spy_bh(C):
    w = pd.DataFrame(0.0, index=C.index, columns=LEV); w["SPY"] = 1.0
    return w


STRATS = [
    (bt.BENCH, spy_bh),
    ("N1. Vol target 15%, SPY/SSO, cap 2x", s_voltarget),
    ("N2. 2x trend: SSO while SPY > 200d", s_lev_trend("SSO")),
    ("N3. 3x trend: UPRO while SPY > 200d", s_lev_trend("UPRO")),
    ("N4. Turn of month, SPY", s_tom),
    ("N5. 200d trend x vol target 15%", s_trend_voltarget),
]

# Every strategy/universe compared with SPY so far in this project (rounds 1-3), for the multiple-testing correction.
N_TESTS_SO_FAR = 5 + 2 + (len(STRATS) - 1)


def holm(pvals):
    order = np.argsort(pvals); m = len(pvals); adj = np.empty(m); run = 0
    for rank, i in enumerate(order):
        run = max(run, (m - rank) * pvals[i]); adj[i] = min(1.0, run)
    return adj


def main():
    syms = ["SPY", "SSO", "UPRO", bt.CASH]
    O, C = bt.daily_panel(syms)
    rf = (C[bt.CASH] / C[bt.CASH].shift(1) - 1).fillna(0.0)
    last = C.index[-1]
    two_y = C.index[C.index >= last - pd.Timedelta(days=730)][0]
    windows = [(f"2017–2026: {bt.SCORE_START} .. {last.date()}", pd.Timestamp(bt.SCORE_START), None),
               ("First half: 2017-01-03 .. 2021-12-31", pd.Timestamp(bt.SCORE_START), pd.Timestamp("2021-12-31")),
               (f"Second half: 2022-01-03 .. {last.date()}", pd.Timestamp("2022-01-03"), None),
               (f"Last 2 years: {two_y.date()} .. {last.date()}", two_y, None)]
    md = [f"Candidates from pre-2017 literature, default parameters. Costs {bt.COST_DAILY*1e4:.0f} bp/side, cash = BIL, "
          f"Sharpe in excess of BIL. Holm correction uses m = {N_TESTS_SO_FAR} (all strategies tested vs SPY in this project)."]
    flat = []
    for label, start, end in windows:
        res = bt.run_window(STRATS, O, C, rf, start)
        if end is not None:
            res = {k: (r.loc[:end], tr) for k, (r, tr) in res.items()}  # trade counts stay full-run in sub-windows
        text, rows = bt.report(res, rf, label)
        # Holm-adjusted one-sided p (H0: strategy Sharpe <= SPY Sharpe) with m = every test run so far. Earlier rounds'
        # tests are padded with p = 1 (all had p >= 0.30, so none could change the ranking of these).
        ps = np.array([r["p_boot_le0"] for r in rows if r["strategy"] != bt.BENCH])
        padded = np.r_[ps, np.ones(N_TESTS_SO_FAR - len(ps))]
        adj = holm(padded)[:len(ps)]
        text += "\n\n| Strategy | one-sided p | Holm-adjusted p |\n|---|---:|---:|\n" + "\n".join(
            f"| {r['strategy']} | {r['p_boot_le0']:.3f} | {a:.3f} |" for r, a in zip([r for r in rows if r["strategy"] != bt.BENCH], adj))
        if end is not None:
            text += "\n\n_(Trade counts in this sub-window are for the whole run from its start.)_"
        md.append(text); flat += rows
    out = "\n\n".join(md)
    print(out)
    (bt.HERE / "new_results.md").write_text(out + "\n")
    pd.DataFrame(flat).to_csv(bt.HERE / "new_results.csv", index=False, float_format="%.6f")


if __name__ == "__main__":
    main()
