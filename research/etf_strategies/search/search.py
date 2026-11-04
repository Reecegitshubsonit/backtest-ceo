"""Run all 100,176 combinations on REAL or SHUFFLED data, checkpointed in chunks under data/search_ckpt/<mode>/.
Stores per combo: Sharpe (excess of T-bills) on the search and validate splits, trade counts, average exposure, and
float32 daily excess returns for search+validate days only. Holdout days are dropped before anything is stored.
Re-running skips finished chunks. Prints only summaries.
Usage: python3 search.py real | shuffled"""
import json, sys, time
from multiprocessing import Pool
import numpy as np
import pandas as pd
import common as cm
import families_daily as fd
import families_intraday as fi

MODE = sys.argv[1] if len(sys.argv) > 1 else "real"
SEED = 20261104
OUT = cm.CKPT / MODE; OUT.mkdir(parents=True, exist_ok=True)
CHUNK = 400
G = {}


def shuffled_panel(O, H, L, C, seed):
    """Luck benchmark for daily data: permute whole days (all ETFs together, so cross-asset correlation stays),
    rebuild prices from the permuted gap/intraday/high/low ratios."""
    rng = np.random.default_rng(seed)
    g = (O / C.shift(1)).values; i_ = (C / O).values; hb = (H / O).values; lb = (L / O).values
    T = len(C); p = np.r_[0, 1 + rng.permutation(T - 1)]
    g, i_, hb, lb = g[p], i_[p], hb[p], lb[p]
    c = np.empty_like(i_); o = np.empty_like(i_)
    o[0] = O.values[0]; c[0] = C.values[0]
    for t in range(1, T):
        o[t] = c[t - 1] * g[t]; c[t] = o[t] * i_[t]
        miss = np.isnan(o[t]); o[t][miss] = np.nan
        if np.isnan(c[t - 1]).any():   # asset not listed yet in the permuted order: start it at its original first price
            nw = np.isnan(c[t - 1]) & ~np.isnan(C.values[t]); o[t][nw] = O.values[t][nw]; c[t][nw] = C.values[t][nw]
    mk = lambda a: pd.DataFrame(a, index=C.index, columns=C.columns)
    return mk(o), mk(o * hb), mk(o * lb), mk(c)


def all_combos():
    out = []
    for F in fd.FAMILIES + fi.FAMILIES:
        for p in (fd.grid(F) if F in fd.FAMILIES else fi.grid(F)): out.append((F.name, p))
    return out


def setup():
    O, H, L, C = cm.panel()
    if MODE == "shuffled": O, H, L, C = shuffled_panel(O, H, L, C, SEED)
    D = cm.Daily(O, H, L, C)
    G["D"] = D
    G["B"] = {s: fi.Bars(s, shuffle_seed=(SEED + i if MODE == "shuffled" else None)) for i, s in enumerate(["SPY", "QQQ"])}
    G["fam"] = {F.name: F for F in fd.FAMILIES + fi.FAMILIES}
    G["combos"] = all_combos()
    a, b = D.sp["search"]; v0, v1 = D.sp["validate"]
    G["lo"], G["mid"], G["hi"] = a, v0, v1          # store [a, v1): search + validate only (holdout sealed)


def eval_one(name, p):
    D = G["D"]; F = G["fam"][name]
    if name.startswith("F"):
        W = F.weights(D, p); ret, ch = D.run(W)
        ex = ret - D.rf
        held = pd.DataFrame(W).ffill().fillna(0).values
        expo = np.abs(held).sum(1); expo = expo + held[:, D.ci["SSO"]]     # SSO counts double
        nch = int(ch[G["lo"]:G["mid"]].sum())
    else:
        pnl, _ = F.pnl(G["B"][p["sym"]], p)
        ex = pnl.reindex(D.idx).fillna(0.0).values
        expo = (ex != 0).astype(float)
        nch = int((ex[G["lo"]:G["mid"]] != 0).sum())
    x = ex[G["lo"]:G["hi"]]; m = G["mid"] - G["lo"]
    return x.astype(np.float32), (cm.sharpe(x[:m]), cm.sharpe(x[m:]), x[:m].std() * np.sqrt(252), nch, expo[G["lo"]:G["mid"]].mean())


def run_chunk(ci):
    f = OUT / f"chunk_{ci:05d}.npz"
    if f.exists(): return ci, 0.0
    t = time.time(); ids = list(range(ci * CHUNK, min((ci + 1) * CHUNK, len(G["combos"]))))
    R, S = [], []
    for i in ids:
        x, s = eval_one(*G["combos"][i]); R.append(x); S.append(s)
    np.savez(f.with_suffix(".tmp.npz"), ids=np.array(ids), ret=np.array(R), stats=np.array(S, dtype=np.float64))
    f.with_suffix(".tmp.npz").rename(f)
    return ci, time.time() - t


if __name__ == "__main__":
    t0 = time.time(); setup()
    combos = G["combos"]; n = len(combos); nch = (n + CHUNK - 1) // CHUNK
    (cm.CKPT / "combos.json").write_text(json.dumps(combos))
    D = G["D"]
    meta = {"n": n, "splits": {k: [str(D.idx[a].date()), str(D.idx[b - 1].date())] for k, (a, b) in D.sp.items()},
            "stored_days": [str(D.idx[G["lo"]].date()), str(D.idx[G["hi"] - 1].date())], "mode": MODE}
    (OUT / "meta.json").write_text(json.dumps(meta, indent=1))
    print(f"[{MODE}] {n} combos in {nch} chunks; splits {meta['splits']}; setup {time.time()-t0:.0f}s", flush=True)
    done = 0
    with Pool(4) as pool:
        for ci, dt in pool.imap_unordered(run_chunk, range(nch)):
            done += 1
            if done % max(1, nch // 10) == 0 or done == nch:
                print(f"[{MODE}] {done}/{nch} chunks ({time.time()-t0:.0f}s)", flush=True)
    print(f"[{MODE}] finished in {time.time()-t0:.0f}s", flush=True)
