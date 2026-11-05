"""124,416-combination search over Cameron-style momentum variants, with time-split validation, multiple-testing
correction and a shuffled-data luck benchmark. Prints summaries only.

Protocol (fixed before any results were seen)
  sessions 2016-01-04 .. 2026-11-03, split by time: first 60% search, next 20% validate, last 20% holdout
  1. search   all combinations on the search split; need >= 200 trades; rank by annualized daily Sharpe (R units)
  2. validate top 1,000 by search Sharpe; White's Reality Check (stationary bootstrap) on their validation series
  3. robust   keep combos with validation Sharpe > 0 whose one-step neighbours (each parameter moved one notch)
              mostly hold up: reject if >= 25% of neighbours have validation Sharpe <= 0
  4. holdout  top 10 survivors by validation Sharpe, run once on the holdout split
  deflated Sharpe ratio (Bailey & Lopez de Prado) for the winners with N = all combinations tried
  luck benchmark: the same pipeline with trade outcomes shuffled across events within each day

Trade model: first qualifying setup per symbol per day, at most 5 trades a day, $100 risk -> results in R.
Costs per side: modelled half-spread (from NBBO samples, by price / bar dollar volume / session) + 0.05% impact;
limit target exits pay no spread.

    python -m backtestceo.momentum.search run [--shuffle SEED]
"""
import argparse
import itertools
import json
import math
from pathlib import Path

import numpy as np

from .hist import ROOT, jload, sessions, START, END

GRID = {
    "gap": (10.0, 20.0, 40.0),
    "rvol": (2.0, 5.0, 10.0),
    "price": ((1.0, 10.0), (2.0, 20.0), (5.0, 20.0)),
    "catalyst": ("none", "any_news", "stock_specific"),
    "pattern": ("micro_pullback", "bull_flag", "first_pullback", "any"),
    "confirm": (0, 1),
    "vwap": (0, 1),
    "ema9": (0, 1),
    "window": ((420, 569), (570, 599), (570, 629), (570, 689)),
    "stop": ("pb", "fix2", "fix4"),
    "target": ("1R", "2R", "3R", "trail"),
}
SEL_KEYS = ("confirm", "pattern", "window", "price", "catalyst", "vwap", "ema9", "gap", "rvol")
OUT = ROOT / "search"


# ------------------------------------------------------------------ spread model
def spread_model():
    q = jload(ROOT / "quotes.json")
    pb = np.array([1, 2, 5, 10, 20, 1e9]); db = np.array([0, 1e4, 5e4, 2.5e5, 1e6, 1e18])
    cells = {}
    for r in q:
        k = (int(np.searchsorted(pb, r["price"], "right") - 1), int(np.searchsorted(db, r["bar_dollar_vol"], "right") - 1),
             int(r["m"] < 570))
        cells.setdefault(k, []).append(r["spread_pct"])
    coarse = {}
    for (a, b, s), v in cells.items():
        coarse.setdefault((a, s), []).extend(v)
    allmed = float(np.median([r["spread_pct"] for r in q]))
    table = np.full((5, 5, 2), allmed)
    for a in range(5):
        for b in range(5):
            for s in range(2):
                v = cells.get((a, b, s), [])
                table[a, b, s] = np.median(v) if len(v) >= 8 else (np.median(coarse[(a, s)]) if len(coarse.get((a, s), [])) >= 8 else allmed)
    return pb, db, table, len(q)


def cost_side(px, dv, m, model, impact=0.05):
    """Fraction of price paid per side: half spread + impact."""
    pb, db, table, _ = model
    a = np.clip(np.searchsorted(pb, px, "right") - 1, 0, 4)
    b = np.clip(np.searchsorted(db, dv, "right") - 1, 0, 4)
    s = (m < 570).astype(int)
    half = table[a, b, s] / 2.0
    return (half + impact) / 100.0


# ------------------------------------------------------------------ events
def load_events():
    p = ROOT / "events_all.npz"
    if p.exists():
        z = np.load(p)
        return {k: z[k] for k in z.files}
    parts = [np.load(f) for f in sorted((ROOT / "events").glob("*.npz"))]
    keys = [k for k in parts[0].files if k != "has_news"]
    E = {k: np.concatenate([z[k] for z in parts if len(z["sd"])]) for k in keys}
    o = np.lexsort((E["sd"], E["m"], E["day"]))
    E = {k: v[o] for k, v in E.items()}
    np.savez(p, **E)
    return E


def r_matrix(E, model):
    c_in = cost_side(E["fill"], E["dv_e"], E["m_e"], model)
    out = E["out"].reshape(len(E["fill"]), 12)
    xk = E["xkind"].reshape(-1, 12)
    dvx = E["dv_x"].reshape(-1, 12); mx = E["m_x"].reshape(-1, 12)
    c_out = np.where(xk == 1, 0.0, cost_side(out, dvx, mx, model))
    stop = np.repeat(E["stop"], 4, axis=1)
    fill = E["fill"][:, None]
    R = (out * (1 - c_out) - fill * (1 + c_in[:, None])) / (fill - stop)
    return R.astype(np.float32)


def splits():
    days = [d for d in sessions() if START <= d <= END]
    alld = sessions()
    n = len(days)
    a, b = int(n * 0.6), int(n * 0.8)
    idx = np.array([alld.index(d) for d in days])
    return {"search": idx[:a], "validate": idx[a:b], "holdout": idx[b:]}, days


# ------------------------------------------------------------------ evaluation
def masks(E):
    M = {}
    M["confirm"] = [E["mode"] == v for v in GRID["confirm"]]
    pat = E["pat"]
    M["pattern"] = [pat == 0, pat == 1, pat == 2, np.ones_like(pat, bool)]
    M["window"] = [(E["m"] >= a) & (E["m"] <= b) for a, b in GRID["window"]]
    M["price"] = [(E["px"] >= a) & (E["px"] <= b) for a, b in GRID["price"]]
    M["catalyst"] = [np.ones(len(pat), bool), E["news_any"] == 1, E["news_cat"] == 1]
    M["vwap"] = [np.ones(len(pat), bool), E["vwap"] == 1]
    M["ema9"] = [np.ones(len(pat), bool), E["ema"] == 1]
    M["gap"] = [E["gap"] >= g for g in GRID["gap"]]
    M["rvol"] = [E["rvol"] >= r for r in GRID["rvol"]]
    return M


def select(mask, E, cap=5):
    idx = np.flatnonzero(mask)
    if len(idx) == 0:
        return idx
    gid = E["day"][idx].astype(np.int64) * 100000 + E["sd"][idx]
    _, first = np.unique(gid, return_index=True)
    sel = idx[np.sort(first)]
    d = E["day"][sel]
    _, start, counts = np.unique(d, return_index=True, return_counts=True)
    rank = np.arange(len(d)) - np.repeat(start, counts)
    return sel[rank < cap]


def daily(sel, R, E, nd):
    """(nd, 12) daily R sums."""
    out = np.zeros((nd, R.shape[1]))
    np.add.at(out, E["day"][sel], R[sel])
    return out


def sharpe(x):
    s = x.std()
    return float(x.mean() / s * math.sqrt(252)) if s > 0 else 0.0


def combo_list():
    return [dict(zip(GRID, v)) for v in itertools.product(*[range(len(x)) for x in GRID.values()])]


def leaf_iter():
    """Yield selection keys (index tuples over SEL_KEYS)."""
    return itertools.product(*[range(len(GRID[k])) for k in SEL_KEYS])


def evaluate(E, R, M, keys_idx, period_days, nd):
    """Daily series (len(period_days), 12) for one selection."""
    mask = np.ones(len(E["day"]), bool)
    for k, i in zip(SEL_KEYS, keys_idx):
        mask &= M[k][i]
    pm = np.zeros(nd, bool); pm[period_days] = True
    mask &= pm[E["day"]]
    sel = select(mask, E)
    dly = daily(sel, R, E, nd)[period_days]
    return dly, len(sel), sel


def run_search(E, R, M, sp, nd, tag, log=print):
    f = OUT / f"search_{tag}.npz"
    if f.exists():
        z = np.load(f); return z["sr"], z["n"], z["meanr"]
    leaves = list(leaf_iter())
    sr = np.zeros((len(leaves), 12)); nt = np.zeros(len(leaves), int); mr = np.zeros((len(leaves), 12))
    ck = OUT / f"search_{tag}.partial.npz"
    start = 0
    if ck.exists():
        z = np.load(ck); sr, nt, mr, start = z["sr"], z["n"], z["meanr"], int(z["done"])
    pdays = sp["search"]
    for li in range(start, len(leaves)):
        dly, n, sel = evaluate(E, R, M, leaves[li], pdays, nd)
        nt[li] = n
        if n:
            s = dly.std(axis=0)
            sr[li] = np.where(s > 0, dly.mean(axis=0) / np.where(s > 0, s, 1) * math.sqrt(252), 0)
            mr[li] = R[sel].mean(axis=0)
        if (li + 1) % 1000 == 0:
            OUT.mkdir(parents=True, exist_ok=True)
            np.savez(ck, sr=sr, n=nt, meanr=mr, done=li + 1)
            log(f"  [{tag}] {li + 1}/{len(leaves)} selections")
    np.savez(f, sr=sr, n=nt, meanr=mr)
    ck.unlink(missing_ok=True)
    return sr, nt, mr


def neighbours(leaf, ti):
    """One-notch moves of each parameter (pattern is categorical: excluded). Returns [(leaf, ti)]."""
    out = []
    for k, i in enumerate(leaf):
        key = SEL_KEYS[k]
        if key == "pattern":
            continue
        for j in (i - 1, i + 1):
            if 0 <= j < len(GRID[key]):
                out.append((leaf[:k] + (j,) + leaf[k + 1:], ti))
    si, tj = divmod(ti, 4)
    for s2 in (si - 1, si + 1):
        if 0 <= s2 < 3:
            out.append((leaf, s2 * 4 + tj))
    for t2 in (tj - 1, tj + 1):
        if 0 <= t2 < 4:
            out.append((leaf, si * 4 + t2))
    return out


def describe(leaf, ti):
    d = {k: GRID[k][i] for k, i in zip(SEL_KEYS, leaf)}
    d["stop"], d["target"] = GRID["stop"][ti // 4], GRID["target"][ti % 4]
    d["window"] = f"{d['window'][0] // 60:02d}:{d['window'][0] % 60:02d}-{(d['window'][1] + 1) // 60:02d}:{(d['window'][1] + 1) % 60:02d}"
    d["price"] = f"${d['price'][0]:g}-{d['price'][1]:g}"
    return d


def white_rc(X, B=2000, p=0.2, seed=1):
    """White's Reality Check, stationary bootstrap. X: (T, K) daily returns. H0: no strategy beats zero."""
    rng = np.random.default_rng(seed)
    T, K = X.shape
    mu = X.mean(axis=0)
    V = math.sqrt(T) * mu.max()
    Xc = X - mu
    cnt = 0
    for _ in range(B):
        idx = np.empty(T, int)
        t = rng.integers(T)
        for i in range(T):
            if i == 0 or rng.random() < p:
                t = rng.integers(T)
            else:
                t = (t + 1) % T
            idx[i] = t
        Vb = math.sqrt(T) * Xc[idx].mean(axis=0).max()
        cnt += Vb >= V
    return V, cnt / B


def deflated_sharpe(x, sr_trials_daily, N):
    """Bailey & Lopez de Prado DSR. x: daily returns of the chosen strategy; sr_trials_daily: daily SRs of all trials."""
    from statistics import NormalDist
    nd_ = NormalDist()
    T = len(x)
    s = x.std()
    if s == 0:
        return 0.0, 0.0
    sr = x.mean() / s
    g3 = float(((x - x.mean()) ** 3).mean() / s ** 3)
    g4 = float(((x - x.mean()) ** 4).mean() / s ** 4)
    v = float(np.var(sr_trials_daily))
    emc = 0.5772156649
    sr0 = math.sqrt(v) * ((1 - emc) * nd_.inv_cdf(1 - 1 / N) + emc * nd_.inv_cdf(1 - 1 / (N * math.e)))
    z = (sr - sr0) * math.sqrt(T - 1) / math.sqrt(max(1e-12, 1 - g3 * sr + (g4 - 1) / 4 * sr ** 2))
    return nd_.cdf(z), sr0 * math.sqrt(252)


def pipeline(E, R, sp, nd, tag, log=print, top_validate=1000, min_trades=200):
    M = masks(E)
    sr, nt, mr = run_search(E, R, M, sp, nd, tag, log)
    leaves = list(leaf_iter())
    flat = sr.copy()
    flat[nt < min_trades] = -np.inf
    order = np.argsort(-flat, axis=None)
    tried = int(np.isfinite(flat).sum())
    top = [divmod(int(o), 12) for o in order[:top_validate]]
    cache = {}

    def val(li_leaf, ti):
        key = (li_leaf, ti)
        if key not in cache:
            dly, n, sel = evaluate(E, R, M, li_leaf, sp["validate"], nd)
            cache[(li_leaf, None)] = (dly, n)
            for t in range(12):
                cache[(li_leaf, t)] = (dly[:, t], n)
        return cache[key]

    Xv = np.column_stack([val(leaves[li], ti)[0] for li, ti in top])
    V, p_rc = white_rc(Xv)
    rows = []
    for (li, ti) in top:
        xv, nv = val(leaves[li], ti)
        svr = sharpe(xv)
        if svr <= 0:
            continue
        nb = neighbours(leaves[li], ti)
        nb_sr = [sharpe(val(l2, t2)[0]) for l2, t2 in nb]
        fail = sum(s <= 0 for s in nb_sr) / max(1, len(nb_sr))
        if fail >= 0.25:
            continue
        rows.append({"leaf": leaves[li], "ti": ti, "search_sr": float(sr[li, ti]), "search_n": int(nt[li]),
                     "search_meanR": float(mr[li, ti]), "val_sr": svr, "val_n": int(nv), "val_meanR": float(xv.sum() / max(1, nv)),
                     "neighbours": len(nb_sr), "neighbour_fail": fail, "neighbour_median_val_sr": float(np.median(nb_sr))})
    rows.sort(key=lambda r: -r["val_sr"])
    summary = {"tag": tag, "combos": len(leaves) * 12, "combos_with_min_trades": tried,
               "best_search_sr": float(flat.max()), "search_sr_p50": float(np.median(sr[nt >= min_trades])) if tried else None,
               "share_search_sr_positive": float((sr[nt >= min_trades] > 0).mean()) if tried else None,
               "validated": len(top), "val_sr_positive": int((np.array([sharpe(Xv[:, k]) for k in range(Xv.shape[1])]) > 0).sum()),
               "white_rc_p": p_rc, "survivors": len(rows)}
    return summary, rows, sr, nt


def holdout(E, R, sp, nd, rows, k=10):
    M = masks(E)
    res = []
    for r in rows[:k]:
        dly, n, sel = evaluate(E, R, M, tuple(r["leaf"]), sp["holdout"], nd)
        x = dly[:, r["ti"]]
        res.append({**{kk: v for kk, v in r.items() if kk != "leaf"}, "params": describe(tuple(r["leaf"]), r["ti"]),
                    "holdout_sr": sharpe(x), "holdout_n": int(n), "holdout_totalR": float(x.sum()),
                    "holdout_meanR": float(x.sum() / max(1, n)), "holdout_winrate": float((R[sel, r["ti"]] > 0).mean()) if n else 0})
    return res


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=("run",))
    ap.add_argument("--shuffles", type=int, default=2)
    a = ap.parse_args(argv)
    OUT.mkdir(parents=True, exist_ok=True)
    E = load_events()
    model = spread_model()
    R = r_matrix(E, model)
    sp, days = splits()
    nd = len(sessions())
    print(f"events {len(R):,}; sessions {len(days)}: search {days[0]}..{days[len(sp['search']) - 1]}, "
          f"validate ..{days[len(sp['search']) + len(sp['validate']) - 1]}, holdout ..{days[-1]}; spread samples {model[3]}")
    report = {"events": int(len(R)), "splits": {k: [str(sessions()[v[0]]), str(sessions()[v[-1]]), int(len(v))] for k, v in sp.items()},
              "spread_table_pct": model[2].tolist()}
    summ, rows, sr, nt = pipeline(E, R, sp, nd, "real")
    report["real"] = summ
    print("REAL:", json.dumps(summ))
    # deflated Sharpe for survivors (search split, N = all combos tried)
    M = masks(E)
    sr_daily = (sr[nt >= 200] / math.sqrt(252)).ravel()
    for r in rows[:10]:
        dly, n, _ = evaluate(E, R, M, tuple(r["leaf"]), sp["search"], nd)
        r["dsr"], r["sr0_annual"] = deflated_sharpe(dly[:, r["ti"]], sr_daily, summ["combos"])
    # luck benchmark: outcomes shuffled within day (search + validate only; holdout untouched)
    report["shuffled"] = []
    for s in range(a.shuffles):
        rng = np.random.default_rng(100 + s)
        Rs = R.copy()
        d = E["day"]
        starts = np.flatnonzero(np.r_[True, d[1:] != d[:-1]]); ends = np.r_[starts[1:], len(d)]
        for i0, i1 in zip(starts, ends):
            Rs[i0:i1] = Rs[i0:i1][rng.permutation(i1 - i0)]
        ss, srows, _, _ = pipeline(E, Rs, sp, nd, f"shuffle{s}")
        ss["top_survivor_val_sr"] = srows[0]["val_sr"] if srows else None
        report["shuffled"].append(ss)
        print(f"SHUFFLE {s}:", json.dumps(ss))
    report["survivors_top10"] = [{**{k: v for k, v in r.items() if k != "leaf"}, "params": describe(tuple(r["leaf"]), r["ti"])} for r in rows[:10]]
    (OUT / "pre_holdout.json").write_text(json.dumps(report, indent=1, default=str))
    if not rows:
        print("NOTHING SURVIVED validation + neighbour test; holdout not run.")
        return report
    hold = holdout(E, R, sp, nd, rows)
    report["holdout_top10"] = hold
    (OUT / "report.json").write_text(json.dumps(report, indent=1, default=str))
    for h in hold:
        print("HOLDOUT", json.dumps({k: h[k] for k in ("search_sr", "val_sr", "holdout_sr", "holdout_n", "holdout_meanR", "dsr")}), h["params"])
    return report


if __name__ == "__main__":
    from backtestceo.momentum.search import main as _m
    _m()


# ------------------------------------------------------------------ the earlier Cameron version on the same holdout
def cameron_holdout(slippage_pct=None):
    """Round-1 engine (backtest.run_day, default Config) on the holdout sessions, fed from the full-history store.

    Differences from round 1: universe = this pipeline's candidates (gappers from the corporate-action + news symbol
    list, not news-only), news from the symbol-filtered query. Returns stats in $ ($100 risk/trade) and R."""
    from datetime import datetime, timedelta
    from .backtest import run_day, stats
    from .config import Config
    from .data import ET
    sp, days = splits()
    alld = sessions()
    cfg = Config() if slippage_pct is None else Config().with_(slippage_pct=slippage_pct)
    trades, used = [], []
    for di in sp["holdout"]:
        d = alld[di]
        zf = ROOT / "min" / f"{d}.npz"
        if not zf.exists():
            continue
        z = np.load(zf)
        cands = {c["sym"]: c for c in jload(ROOT / "cands" / f"{d}.json")}
        nf = ROOT / "news" / f"{d}.json"
        news = jload(nf) if nf.exists() else []
        base = datetime(d.year, d.month, d.day, tzinfo=ET)
        nb = {}
        for s, mins, head, nsym in news:
            nb.setdefault(s, []).append((base + timedelta(minutes=mins), head, nsym))
        minute, cl = {}, []
        for j, s in enumerate(z["sym"]):
            a, b = int(z["off"][j]), int(z["off"][j + 1])
            if s not in cands or b - a == 0:
                continue
            rows = [{"t": (base + timedelta(minutes=int(m))).isoformat(), "o": float(o), "h": float(h), "l": float(l),
                     "c": float(c), "v": float(v)}
                    for m, o, h, l, c, v in zip(z["m"][a:b], z["o"][a:b], z["h"][a:b], z["l"][a:b], z["c"][a:b], z["v"][a:b])]
            minute[s] = rows
            cl.append((s, cands[s]["pc"], cands[s]["adv"], nb.get(s, [])))
        t, _, _ = run_day(d, cl, minute, cfg)
        trades += t
        used.append(d)
    st = stats(trades, used, cfg) if trades else {}
    rs = [t["r_multiple"] for t in trades]
    daily_ = {}
    for t in trades:
        daily_[t["date"]] = daily_.get(t["date"], 0.0) + t["r_multiple"]
    x = np.array([daily_.get(str(d), 0.0) for d in used])
    return {"sessions": len(used), "trades": len(trades), "net_pnl": st.get("net_pnl"), "profit_factor": st.get("profit_factor"),
            "win_rate": st.get("win_rate"), "mean_R": float(np.mean(rs)) if rs else None, "sharpe_R_daily": sharpe(x),
            "slippage_pct": cfg.slippage_pct}
