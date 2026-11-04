"""Round 4: walk-forward search, scored on alpha over buy & hold, low turnover, maker-order costs.

Changes vs crypto_search.py (round 3):
  - cost 0.30% round trip (Alpaca maker 0.15% per side, limit orders; fill risk not modelled)
  - 4h and 1d bars only; a combo is eligible only if it trades <= 15 times a year per coin
  - score = alpha information ratio: daily strategy returns regressed on buy & hold, annualised residual mean / sd
  - walk-forward: train on all years before Y (expanding), pick the top 10 neighbour-robust combos (BTC+ETH pooled),
    trade them as an equal-weight basket in year Y; Y = 2023, 2024, 2025, 2026 (to 2026-11-02)
  - luck benchmark: the identical procedure on 5 bar-shuffled datasets
NOTE: Sep 2025 - Nov 2026 was already seen in round 3's holdout, and this design was chosen after it. The 2025/2026
folds are therefore not clean. The real test is forward paper trading.
Run: python engine/scripts/crypto_search_wf.py --end 2026-11-02 --out docs/crypto-search-wf-tables.md
"""
import argparse
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from numba import njit, prange

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import crypto_search as cs  # noqa: E402
from crypto_edge_backtest import fetch, seg_run, tsmom  # noqa: E402

SIDE = 0.0015
N = 100_000
SEED = 20261104
MAX_TPY = 15
TEST_YEARS = (2023, 2024, 2025, 2026)
TOP = 10
SYMS = ["BTC/USD", "ETH/USD"]


@njit(parallel=True, cache=True)
def run_moments(F, o, h, l, c, atr, day, gap, combos, i1, side, n_days, yid, bday, n_years):
    """Per combo per year: [n days, sum r, sum r^2, sum r*b, trades, sum trade ret, wins]."""
    K = combos.shape[0]
    out = np.zeros((K, n_years, 7))
    for j in prange(K):
        tr = np.empty(len(o))
        ent = np.empty(len(o), dtype=np.int64)
        dl, nt = cs._run(F, o, h, l, c, atr, day, gap, combos[j], 1, i1, side, n_days, tr, ent)
        for d in range(n_days):
            y = yid[d]
            r = np.exp(dl[d]) - 1.0
            out[j, y, 0] += 1
            out[j, y, 1] += r
            out[j, y, 2] += r * r
            out[j, y, 3] += r * bday[d]
        for k in range(nt):
            y = yid[day[ent[k]]]
            out[j, y, 4] += 1
            out[j, y, 5] += tr[k]
            if tr[k] > 0:
                out[j, y, 6] += 1
    return out


def alpha_ir(m, bm):
    """m: [..., years, 7] summed over chosen years -> alpha IR; bm: [years, 3] (n, sum b, sum b^2) summed."""
    n = m[..., 0]
    mr, mb = m[..., 1] / n, bm[1] / bm[0]
    vr = m[..., 2] / n - mr ** 2
    vb = bm[2] / bm[0] - mb ** 2
    cov = m[..., 3] / n - mr * mb
    beta = cov / vb
    a = mr - beta * mb
    va = np.maximum(vr - beta ** 2 * vb, 1e-18)
    return a / np.sqrt(va) * np.sqrt(365), beta


class Data:
    def __init__(self, h1, start, end):
        self.U = cs.Universe(h1, start, end)
        n_days = self.U.n_days
        days = pd.date_range(start, periods=n_days, freq="D")
        self.yid = (days.year - 2021).values.astype(np.int64)
        self.n_years = int(self.yid.max()) + 1
        self.bday, self.bm = {}, {}
        for s, df in h1.items():
            d = cs.resample(df, "1D")["c"]
            ret = d.pct_change()
            ret[d.index.to_series().diff() > pd.Timedelta(days=2)] = 0.0  # never book a return across a data hole
            b = ret.reindex(days).fillna(0).values
            self.bday[s] = b.astype(np.float64)
            self.bm[s] = np.array([[(self.yid == y).sum(), b[self.yid == y].sum(), (b[self.yid == y] ** 2).sum()]
                                   for y in range(self.n_years)])

    def moments(self, P, syms):
        out = np.zeros((len(P), len(syms), self.n_years, 7))
        for ti in (1, 2):
            m = P[:, 0] == ti
            if not m.any():
                continue
            tf = cs.TFS[ti]
            for si, s in enumerate(syms):
                D = self.U.d[(s, tf)]
                out[m, si] = run_moments(D["F"], D["o"], D["h"], D["l"], D["c"], D["atr"], D["day"], D["gap"],
                                         cs.to_kernel(P[m], D["names"]), len(D["o"]), SIDE, self.U.n_days,
                                         self.yid, self.bday[s], self.n_years)
        return out


def draw(rng):
    dims = (len(cs.ENTRIES), len(cs.TREND), len(cs.VOLAT), len(cs.VOLUME), len(cs.TOD), len(cs.DOW), len(cs.HOLDS), len(cs.STOPS), len(cs.TPS))
    seen, out = set(), []
    while len(out) < N:
        tf = int(rng.integers(1, 3))
        x = (tf,) + tuple(int(rng.integers(0, n)) for n in dims)
        if tf == 2:
            x = x[:5] + (0,) + x[6:]
        if x not in seen:
            seen.add(x)
            out.append(x)
    return np.array(out, dtype=np.int64)


def fold_scores(M, D, train_years):
    """Pooled BTC/ETH alpha IR on train years + eligibility (<= 15 trades/yr and >= 10 trades per coin)."""
    ys = list(train_years)
    irs, ok = [], np.ones(len(M), bool)
    for si, s in enumerate(SYMS):
        m = M[:, si, ys].sum(axis=1)
        ir, _ = alpha_ir(m, D.bm[s][ys].sum(axis=0))
        irs.append(ir)
        tpy = m[:, 4] / (m[:, 0] / 365.25)
        ok &= (tpy <= MAX_TPY) & (m[:, 4] >= 10) & (ir > 0)
    sc = np.mean(irs, axis=0)
    return np.where(ok, sc, -np.inf)


def select(P, M, D, train_years, label):
    sc = fold_scores(M, D, train_years)
    order = [k for k in np.argsort(-sc)[:2000] if np.isfinite(sc[k])]
    index = {tuple(x): k for k, x in enumerate(map(tuple, P))}
    chosen = []
    for k in order:
        nb = [x for x in cs.neighbours(tuple(P[k])) if not (x[0] == 2 and x[5] != 0)]
        new = np.array([x for x in nb if x not in index], dtype=np.int64).reshape(-1, 10)
        nm = D.moments(new, SYMS) if len(new) else np.zeros((0, 2, D.n_years, 7))
        nmap = {tuple(x): nm[i] for i, x in enumerate(map(tuple, new))}
        good = 0
        for x in nb:
            mm = M[index[x]] if x in index else nmap[x]
            irs = [alpha_ir(mm[si, list(train_years)].sum(axis=0), D.bm[s][list(train_years)].sum(axis=0))[0] for si, s in enumerate(SYMS)]
            good += np.mean(irs) > 0
        if good >= np.ceil(2 / 3 * len(nb)):
            chosen.append(k)
        if len(chosen) == TOP:
            break
    return chosen, int(np.isfinite(sc).sum())


def basket_daily(D, P, chosen, sym, y):
    """Equal-weight daily returns of the chosen combos on one coin in year y (signals warm from prior bars)."""
    days = pd.date_range("2021-01-01", periods=D.U.n_days, freq="D", tz="UTC")
    d0 = int(np.searchsorted(days, pd.Timestamp(f"{y}-01-01", tz="UTC")))
    d1 = int(np.searchsorted(days, pd.Timestamp(f"{y + 1}-01-01", tz="UTC")))
    rets, trades = [], []
    for k in chosen:
        st, dr = cs.period(D.U, tuple(P[k]), sym, d0, d1)
        rets.append(dr)
        trades.append(st)
    return np.mean(rets, axis=0), trades, days[d0:d1]


def stats(r):
    r = np.asarray(r)
    eq = np.cumprod(1 + r)
    sd = r.std()
    return {"return%": 100 * (eq[-1] - 1), "sharpe": r.mean() / sd * np.sqrt(365) if sd > 0 else np.nan,
            "maxDD%": 100 * (eq / np.maximum.accumulate(eq) - 1).min()}


def procedure(h1, start, end, P, label, with_sol):
    t0 = time.time()
    D = Data(h1, start, end)
    M = D.moments(P, SYMS)
    rows, picks, oos = [], {}, {s: [] for s in h1}
    for y in TEST_YEARS:
        train = range(0, y - 2021)
        chosen, n_ok = select(P, M, D, train, label)
        picks[y] = chosen
        for s in h1:
            if not with_sol and s not in SYMS:
                continue
            r, trs, idx = basket_daily(D, P, chosen, s, y)
            b = D.bday[s][(D.yid == y - 2021)][:len(r)]
            oos[s].append((r, b))
            n = sum(t["trades"] for t in trs)
            wins = sum(t["trades"] * t["win"] for t in trs)
            ex = sum(t["trades"] * t["exp"] for t in trs) / n if n else np.nan
            mom = np.array([[len(r), r.sum(), (r ** 2).sum(), (r * b).sum(), 0, 0, 0]])
            ir, beta = alpha_ir(mom[0], np.array([len(b), b.sum(), (b ** 2).sum()]))
            rows.append({"run": label, "test year": y, "symbol": s, "eligible": n_ok, "picked": len(chosen),
                         "trades (all picks)": n, "win%": 100 * wins / n if n else np.nan, "exp%/trade": 100 * ex,
                         **stats(r), "alpha IR": ir, "beta": beta, "B&H return%": stats(b)["return%"], "B&H sharpe": stats(b)["sharpe"]})
    summ = {}
    for s, lst in oos.items():
        if not lst:
            continue
        r = np.concatenate([a for a, _ in lst])
        b = np.concatenate([x for _, x in lst])
        ir, beta = alpha_ir(np.array([len(r), r.sum(), (r ** 2).sum(), (r * b).sum(), 0, 0, 0]), np.array([len(b), b.sum(), (b ** 2).sum()]))
        summ[s] = dict(alpha_ir=ir, beta=beta, **stats(r), r=r, b=b)
    print(f"  {label}: done in {time.time() - t0:.0f}s; OOS alpha IR " +
          ", ".join(f"{s.split('/')[0]} {v['alpha_ir']:.2f}" for s, v in summ.items()), flush=True)
    return rows, summ, picks, D


def boot_ci(r, b, reps=2000, block=20, seed=3):
    n = len(r)
    rng = np.random.default_rng(seed)
    k = int(np.ceil(n / block))
    out = np.empty(reps)
    for i in range(reps):
        idx = (rng.integers(0, n, k)[:, None] + np.arange(block)).ravel()[:n] % n
        x, y = r[idx], b[idx]
        out[i] = alpha_ir(np.array([n, x.sum(), (x ** 2).sum(), (x * y).sum(), 0, 0, 0]), np.array([n, y.sum(), (y ** 2).sum()]))[0]
    return np.percentile(out, 2.5), np.percentile(out, 97.5)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--end", default="2026-11-02")
    ap.add_argument("--shuffles", type=int, default=5)
    ap.add_argument("--out")
    a = ap.parse_args()
    end = datetime.fromisoformat(a.end).replace(tzinfo=timezone.utc) + timedelta(days=1) - timedelta(seconds=1)
    start = pd.Timestamp("2021-01-01", tz="UTC")
    cache = HERE.parent / ".cache" / "crypto_edge"
    h1 = {s: fetch(s, "1Hour", datetime(2021, 1, 1, tzinfo=timezone.utc), end, cache) for s in ["BTC/USD", "ETH/USD", "SOL/USD"]}
    P = draw(np.random.default_rng(SEED))
    rows, real, picks, D = procedure(h1, start, pd.Timestamp(end), P, "real", True)
    luck = []
    for k in range(a.shuffles):
        sh = cs.shuffle_1h([h1[s] for s in SYMS], start, pd.Timestamp(end) + pd.Timedelta(seconds=1), SEED + 100 + k)
        _, s_summ, _, _ = procedure({"BTC/USD": sh[0], "ETH/USD": sh[1]}, start, pd.Timestamp(end), P, f"shuffled_{k}", False)
        luck.append(s_summ)

    R = pd.DataFrame(rows)
    S = []
    for s, v in real.items():
        lo, hi = boot_ci(v["r"], v["b"])
        sh = [L[s]["alpha_ir"] for L in luck if s in L]
        bs = stats(v["b"])
        S.append({"symbol": s, "OOS 2023-2026 return%": v["return%"], "sharpe": v["sharpe"], "maxDD%": v["maxDD%"],
                  "alpha IR": v["alpha_ir"], "alpha IR 95% CI": f"[{lo:.2f}, {hi:.2f}]", "beta": v["beta"],
                  "shuffled alpha IR mean": np.mean(sh) if sh else np.nan, "shuffles >= real": f"{sum(x >= v['alpha_ir'] for x in sh)}/{len(sh)}" if sh else "",
                  "B&H return%": bs["return%"], "B&H sharpe": bs["sharpe"], "B&H maxDD%": bs["maxDD%"]})
    S = pd.DataFrame(S)
    # TSMOM 28d reference over the same OOS years, 0.30% round trip
    T = []
    for s in h1:
        dd = cs.resample(h1[s], "1D")
        _, td, _ = seg_run(dd, tsmom, SIDE, "next_open")  # per contiguous segment (SOL data hole)
        x = td[td.index >= pd.Timestamp("2023-01-01", tz="UTC")].values
        T.append({"symbol": s, **{f"TSMOM28 {k}": v for k, v in stats(x).items()}})
    T = pd.DataFrame(T)
    # forward candidates: picks trained on ALL data through the end date
    allyears = range(0, D.n_years)
    final, _ = select(P, D.moments(P, SYMS), D, allyears, "final")
    F = pd.DataFrame([{"#": i + 1, "strategy": cs.describe(tuple(P[k]))} for i, k in enumerate(final)])

    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 30)
    pd.set_option("display.max_colwidth", 100)
    print("\n== OOS summary (2023 -> 2026-11-02, walk-forward baskets)\n", S.round(2).to_string(index=False))
    print("\n== TSMOM 28d, same period\n", T.round(2).to_string(index=False))
    print("\n== Per fold\n", R.round(2).to_string(index=False))
    print("\n== Forward paper-trade candidates (trained on all data)\n", F.to_string(index=False))
    if a.out:
        def md(df):
            r = df.round(2).astype(object).where(df.notna(), "")
            cols = list(df.columns)
            return "\n".join(["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)] + ["| " + " | ".join(str(v) for v in x) + " |" for x in r.values])
        Path(a.out).write_text("\n\n".join(["### OOS summary\n\n" + md(S), "### TSMOM 28d\n\n" + md(T),
                                            "### Per fold\n\n" + md(R), "### Forward candidates\n\n" + md(F)]) + "\n")


if __name__ == "__main__":
    main()
