"""Selection on search + validate splits only (holdout sealed). Pre-declared rules:
 1. Eligible: >= 10 position changes / trade days in the search split, mean exposure >= 5%, and testable at 5-min
    resolution (ORB stops of 0.05x/0.10x ATR are not: they fit inside one bar).
 2. Top 500 by search-split Sharpe (excess of T-bills).
 3. Neighbor robustness: neighbors = same family, one ORDINAL parameter moved one step. Pass if
    median neighbor search Sharpe >= 0.7 x own AND median neighbor validate Sharpe > 0.
 4. Rank survivors by validate Sharpe; top 10 with at most 2 per (family, universe/symbol). If the cap leaves fewer
    than 10 (real data: 6, because the shortlist is almost all intraday), fill with the next survivors, uncapped.
Multiple-testing correction:
 - Deflated Sharpe (Bailey & Lopez de Prado 2014) on the search split with N = all combinations tried, both on excess
   returns (vs 0) and on the differential vs vol-matched SPY (vs SPY).
 - White's Reality Check, studentized, stationary bootstrap (mean block 21, B = 500): H0 = no combination beats
   vol-matched SPY on the search split. Same test on validate across the 500 shortlisted.
Usage: python3 select_top.py real | shuffled   -> selection_<mode>.json, selection_<mode>.md"""
import json, sys
import numpy as np
from statistics import NormalDist
_N = NormalDist()


class norm:
    cdf = staticmethod(_N.cdf); ppf = staticmethod(_N.inv_cdf)


def skew(x):
    z = (x - x.mean()) / x.std(); return float((z ** 3).mean())


def kurtosis(x, fisher=False):
    z = (x - x.mean()) / x.std(); return float((z ** 4).mean()) - (3 if fisher else 0)
import common as cm
import search as S

MODE = sys.argv[1] if len(sys.argv) > 1 else "real"
OUT = cm.CKPT / MODE
TOPN, B, BLOCK = 500, 500, 21


def load():
    fs = sorted(OUT.glob("chunk_*.npz"))
    ids, R, st = [], [], []
    for f in fs:
        z = np.load(f); ids.append(z["ids"]); R.append(z["ret"]); st.append(z["stats"])
    return np.concatenate(ids), np.concatenate(R), np.concatenate(st)


def spy_ex():
    O, H, L, C = cm.panel()
    if MODE == "shuffled": O, H, L, C = S.shuffled_panel(O, H, L, C, S.SEED)
    D = cm.Daily(O, H, L, C)
    W = np.zeros((D.T, len(D.cols))); W[:, D.ci["SPY"]] = 1.0
    r, _ = D.run(W); ex = r - D.rf
    a, _ = D.sp["search"]; v0, v1 = D.sp["validate"]
    return ex[a:v1].astype(np.float32), v0 - a


def dsr(x, sr_all_daily, N):
    """Deflated Sharpe: P(true SR > expected max SR of N unskilled trials). Per-period Sharpe throughout."""
    sr = x.mean() / x.std(); T = len(x); g = 0.5772156649
    V = np.var(sr_all_daily)
    sr0 = np.sqrt(V) * ((1 - g) * norm.ppf(1 - 1 / N) + g * norm.ppf(1 - 1 / (N * np.e)))
    den = np.sqrt(1 - skew(x) * sr + (kurtosis(x, fisher=False) - 1) / 4 * sr ** 2)
    return float(norm.cdf((sr - sr0) * np.sqrt(T - 1) / den)), float(sr0 * np.sqrt(252))


def reality_check(Dm, seed=1):
    """Studentized White RC over rows of Dm (combos x days), stationary bootstrap via resample counts."""
    n = Dm.shape[1]; mu = Dm.mean(1); sd = Dm.std(1); sd[sd == 0] = np.inf
    stat = np.sqrt(n) * (mu / sd).max()
    rng = np.random.default_rng(seed); mx = np.empty(B)
    for b in range(B):
        idx = np.empty(n, int); t = rng.integers(n)
        for i in range(n):
            if i and rng.random() < 1 / BLOCK: t = rng.integers(n)
            idx[i] = t; t = (t + 1) % n
        w = np.bincount(idx, minlength=n).astype(np.float32) / n
        mx[b] = (np.sqrt(n) * ((Dm @ w) - mu) / sd).max()
    return float((mx >= stat).mean()), float(stat)


def main():
    combos = json.loads((cm.CKPT / "combos.json").read_text())
    ids, R, st = load()
    assert len(ids) == len(combos), f"search incomplete: {len(ids)}/{len(combos)}"
    o = np.argsort(ids); ids, R, st = ids[o], R[o], st[o]
    spy, m = spy_ex()
    sh_s, sh_v, vol_s, nch, expo = st.T
    # ORB stops of 0.05x / 0.10x ATR (~0.05-0.10% of price) are no wider than one median 5-min bar (0.086%): whether
    # stop or target hit first is decided inside a bar, so 5-min data cannot test them. Ineligible; still counted in N.
    unres = np.array([c[0] == "I1_orb" and c[1]["stop"] in ("atr05", "atr10") for c in combos])
    elig = (nch >= 10) & (expo >= 0.05) & np.isfinite(sh_s) & np.isfinite(sh_v) & ~unres
    spy_s, spy_v = cm.sharpe(spy[:m]), cm.sharpe(spy[m:])
    # vol-matched-SPY differentials on the search split
    Rs = R[:, :m]; ss = spy[:m]
    k = (Rs.std(1) / ss.std()).astype(np.float32)
    Dm = Rs - k[:, None] * ss[None, :]
    N = len(combos)
    sr_daily = sh_s[elig] / np.sqrt(252)
    # 2-3. shortlist + neighbors
    key = {(c[0], tuple(c[1].values())): i for i, c in enumerate(combos)}
    fams = {F.name: F for F in S.fd.FAMILIES + S.fi.FAMILIES}
    cand = np.where(elig)[0][np.argsort(-sh_s[elig])][:TOPN]
    rows = []
    for i in cand:
        name, p = combos[i]; F = fams[name]; nb = []
        for kp in F.ORDINAL:
            vals = F.PARAMS[kp]; j = vals.index(p[kp])
            for jj in (j - 1, j + 1):
                if 0 <= jj < len(vals):
                    q = dict(p); q[kp] = vals[jj]; t = key.get((name, tuple(q.values())))
                    if t is not None: nb.append(t)
        ok = bool(nb) and np.median(sh_s[nb]) >= 0.7 * sh_s[i] and np.median(sh_v[nb]) > 0
        rows.append((int(i), ok, len(nb), float(np.median(sh_s[nb])) if nb else np.nan, float(np.median(sh_v[nb])) if nb else np.nan))
    surv = [r for r in rows if r[1]]
    surv.sort(key=lambda r: -sh_v[r[0]])
    top, cnt = [], {}
    for r in surv:
        name, p = combos[r[0]]; g = (name, p.get("univ", p.get("sym", "SPY")))
        if cnt.get(g, 0) >= 2: continue
        cnt[g] = cnt.get(g, 0) + 1; top.append(r)
        if len(top) == 10: break
    capped = len(top)
    for r in surv:                       # cap left fewer than 10: fill with the next survivors by validate Sharpe (labelled)
        if len(top) == 10: break
        if r not in top: top.append(r)
    # multiple testing
    rc_p, rc_stat = reality_check(Dm[elig])
    Dv = R[cand][:, m:] - (R[cand][:, m:].std(1) / spy[m:].std())[:, None] * spy[m:][None, :]
    rcv_p, _ = reality_check(Dv, seed=2)
    out = {"mode": MODE, "N": N, "eligible": int(elig.sum()), "spy_sharpe": {"search": spy_s, "validate": spy_v},
           "best_search_sharpe": float(sh_s[elig].max()), "rc_search_p": rc_p, "rc_validate_p_shortlist": rcv_p,
           "shortlist": TOPN, "neighbor_survivors": len(surv), "top10": []}
    for i, ok, nn, ms, mv in top:
        d_s, sr0 = dsr(R[i, :m], sr_daily, N)
        d_rel, _ = dsr(Dm[i], (Dm[elig].mean(1) / Dm[elig].std(1)), N)
        out["top10"].append({"id": i, "family": combos[i][0], "params": combos[i][1], "search_sharpe": float(sh_s[i]),
                             "validate_sharpe": float(sh_v[i]), "neighbors": nn, "nb_med_search": ms, "nb_med_validate": mv,
                             "dsr_vs_zero": d_s, "dsr_vs_volmatched_spy": d_rel, "sr0_expected_max_annual": sr0,
                             "search_trades": int(nch[i])})
    (cm.ROOT / f"selection_{MODE}.json").write_text(json.dumps(out, indent=1, default=str))
    L = [f"## Selection, {MODE} data", "",
         f"Combinations tried: {N:,}; eligible: {out['eligible']:,}. SPY Sharpe (xs T-bill): search {spy_s:.2f}, validate {spy_v:.2f}.",
         f"Best search-split Sharpe of any combination: {out['best_search_sharpe']:.2f}. Expected max Sharpe of {N:,} unskilled "
         f"trials (deflated-Sharpe hurdle): {out['top10'][0]['sr0_expected_max_annual'] if out['top10'] else float('nan'):.2f}.",
         f"White's Reality Check (H0: nothing beats vol-matched SPY): search split p = {rc_p:.3f}; validate split over the "
         f"{TOPN} shortlisted p = {rcv_p:.3f}.",
         f"Shortlist {TOPN} → {len(surv)} pass the neighbor test → top {len(top)} ({capped} under the 2-per-group cap, {len(top)-capped} filled uncapped).", "",
         "| # | Family | Params | Search Sharpe | Validate Sharpe | Neighbors (median search / validate) | DSR vs 0 | DSR vs vol-matched SPY |",
         "|---|---|---|---:|---:|---|---:|---:|"]
    for j, t in enumerate(out["top10"], 1):
        ps = ", ".join(f"{k}={v}" for k, v in t["params"].items())
        L.append(f"| {j} | {t['family']} | {ps} | {t['search_sharpe']:.2f} | {t['validate_sharpe']:.2f} | {t['neighbors']} ({t['nb_med_search']:.2f} / {t['nb_med_validate']:.2f}) | {t['dsr_vs_zero']:.3f} | {t['dsr_vs_volmatched_spy']:.3f} |")
    # family-level summary
    L += ["", "| Family | Combos | Eligible | Median search Sharpe | Best search Sharpe | Median validate Sharpe | Share beating SPY on both splits |", "|---|---:|---:|---:|---:|---:|---:|"]
    names = np.array([c[0] for c in combos])
    for f in sorted(set(names)):
        sel = (names == f); e = sel & elig
        both = ((sh_s > spy_s) & (sh_v > spy_v) & e).sum() / max(e.sum(), 1)
        L.append(f"| {f} | {sel.sum():,} | {e.sum():,} | {np.median(sh_s[e]):.2f} | {sh_s[e].max():.2f} | {np.median(sh_v[e]):.2f} | {both*100:.1f}% |")
    text = "\n".join(L); print(text); (cm.ROOT / f"selection_{MODE}.md").write_text(text + "\n")


if __name__ == "__main__":
    main()
