"""100,000-combination options strategy search with walk-forward discipline.

    python3 -m backtestceo.osearch.search search      # real + shuffled search (checkpointed), validation, finalists
    python3 -m backtestceo.osearch.search holdout     # one-shot: top 10 on the holdout (refuses to run twice)

Time split by entry day over all Alpaca options history (2024-02-01 .. 2026-11-02):
first 60% search, next 20% validate, last 20% holdout. A trade counts in a segment only if it is entered and
closed inside it. Parameters: entry signal (38 indicator/candle signals) x invert x daily-trend filter x vol-regime
filter x entry time (4) x DTE (0/1/7/30) x structure (credit/debit vertical, long option, iron condor, long
strangle) x delta (4) x wing (2) x profit target (4) x stop (4).

Multiple-testing control
  * Deflated Sharpe Ratio (Bailey & Lopez de Prado 2014) with N = trials actually evaluated.
  * Luck benchmark: identical search with every signal shuffled in time (per symbol, day order permuted),
    outcome tables unchanged.
  * Neighbour test: a winner is rejected unless >= 2/3 of its one-step parameter neighbours are profitable in
    both search and validation.
"""
import json, math, sys, time
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy.stats import norm, skew, kurtosis

from . import data as D, outcomes as O, signals as SG

N_CONFIGS = 100_000
SEED = 20261103
RUN = D.DIR / "search"
DOC = D.ROOT / "docs/backtests/options-search"
MIN_SEARCH_TRADES = 90          # ~30 expected in each later 20% segment
MIN_VAL_TRADES = 25
TOP_TO_VALIDATE = 1000
N_FINAL = 10

FAMS = [("credit", di, wi) for di in range(4) for wi in range(2)] + \
       [("debit", di, wi) for di in range(4) for wi in range(2)] + \
       [("long", di, 0) for di in range(4)] + \
       [("condor", di, wi) for di in range(4) for wi in range(2)] + \
       [("strangle", di, 0) for di in range(4)]
DIRECTIONAL = {"credit", "debit", "long"}
SIDX = {s: i for i, s in enumerate(O.STRUCTS)}
PARAMS = ["sig", "inv", "trend", "vol", "time", "bucket", "fam", "pt", "sl"]
SIZES = None


# ----------------------------------------------------------------- data
def load(shuffle=False):
    days = [d for d in (D.ts(r["t"]).date() for r in D.underlying("SPY")["1d"]) if D.FIRST_EXP <= d <= D.LAST_DAY]
    nd = len(days); seg = [0, int(nd * .6), int(nd * .8), nd]
    tables = {}
    sigs = {}
    rng = np.random.default_rng(SEED + 1)
    for si, s in enumerate(D.SYMBOLS):
        sig, trend, volhi = SG.compute(s, days)
        if shuffle:
            p = rng.permutation(nd); sig, trend, volhi = sig[p], trend[p], volhi[p]
        sigs[s] = (sig, trend, volhi)
    keys, pnl, ex, risk, symid = [], [], [], [], []
    for si, s in enumerate(D.SYMBOLS):
        z = np.load(O.OUT / f"{s}.npz")
        keys.append(z["key"]); pnl.append(z["pnl"]); ex.append(z["exit"]); risk.append(z["risk"])
        symid.append(np.full(len(z["key"]), si, np.int16))
    key = np.concatenate(keys); pnl = np.concatenate(pnl); ex = np.concatenate(ex); risk = np.concatenate(risk)
    symid = np.concatenate(symid)
    for b_i, b in enumerate(O.BUCKETS):
        for t in range(len(O.TIMES)):
            m = (key[:, 2] == b) & (key[:, 1] == t)
            day = key[m, 0].astype(np.int64); sy = symid[m]
            sg = np.stack([sigs[D.SYMBOLS[k]][0][d, t] for k, d in zip(sy, day)]) if m.any() else np.zeros((0, 38), np.int8)
            tr = np.array([sigs[D.SYMBOLS[k]][1][d] for k, d in zip(sy, day)], np.int8)
            vh = np.array([sigs[D.SYMBOLS[k]][2][d] for k, d in zip(sy, day)], np.int8)
            tables[(b_i, t)] = dict(day=day, sym=sy, sig=sg, trend=tr, volhi=vh, pnl=pnl[m], exit=ex[m].astype(np.int64),
                                    risk=risk[m])
    return days, seg, tables


def sizes():
    return dict(sig=len(SG.base_signals()), inv=2, trend=2, vol=3, time=len(O.TIMES), bucket=len(O.BUCKETS),
                fam=len(FAMS), pt=4, sl=4)


def sample_configs():
    sz = sizes(); rng = np.random.default_rng(SEED)
    total = int(np.prod(list(sz.values())))
    flat = rng.choice(total, N_CONFIGS, replace=False)
    out = np.zeros((N_CONFIGS, len(PARAMS)), np.int16)
    for j, p in enumerate(reversed(PARAMS)):
        out[:, len(PARAMS) - 1 - j] = flat % sz[p]; flat //= sz[p]
    return out, total


# ----------------------------------------------------------------- evaluation
def trades(cfg, tables, seg, lo_seg, hi_seg=None):
    """pnl, exit day, risk arrays for one config inside segments [lo_seg, hi_seg]."""
    hi_seg = lo_seg if hi_seg is None else hi_seg
    c = dict(zip(PARAMS, (int(x) for x in cfg)))
    tb = tables[(c["bucket"], c["time"])]
    if len(tb["day"]) == 0: return np.zeros(0), np.zeros(0, int), np.zeros(0)
    d0, d1 = seg[lo_seg], seg[hi_seg + 1]
    s = tb["sig"][:, c["sig"]].astype(np.int8)
    if c["inv"]: s = -s
    fam, di, wi = FAMS[c["fam"]]
    m = (s != 0) & (tb["day"] >= d0) & (tb["day"] < d1)
    if c["trend"]:
        m &= (tb["trend"] == s) if fam in DIRECTIONAL else (tb["trend"] == 1)
    if c["vol"] == 1: m &= tb["volhi"] == 0
    elif c["vol"] == 2: m &= tb["volhi"] == 1
    rows = np.nonzero(m)[0]
    if fam in DIRECTIONAL:
        up, dn = SIDX[(fam, 1, di, wi)], SIDX[(fam, -1, di, wi)]
        st = np.where(s[rows] > 0, up, dn)
    else:
        st = np.full(len(rows), SIDX[(fam, 0, di, wi)])
    k = c["pt"] * 4 + c["sl"]
    p = tb["pnl"][rows, st, k]; e = tb["exit"][rows, st, k]; r = tb["risk"][rows, st]
    ok = np.isfinite(p) & (e < d1)
    return p[ok], e[ok], r[ok]


def metrics(p, e, r, seg, lo_seg, hi_seg=None):
    hi_seg = lo_seg if hi_seg is None else hi_seg
    d0, d1 = seg[lo_seg], seg[hi_seg + 1]
    n = len(p)
    if n == 0: return dict(n=0, exp=0.0, win=0.0, sr=0.0, sharpe=0.0, mdd=0.0, total=0.0, ror=0.0)
    daily = np.bincount(e - d0, weights=p, minlength=d1 - d0)
    sd = daily.std(ddof=1)
    sr = daily.mean() / sd if sd > 0 else 0.0
    eq = np.cumsum(daily); mdd = float((eq - np.maximum.accumulate(np.maximum(eq, 0))).min())
    return dict(n=n, exp=float(p.mean()), win=float((p > 0).mean()), sr=float(sr), sharpe=float(sr * math.sqrt(252)),
                mdd=mdd, total=float(p.sum()), ror=float(p.sum() / max(r.mean(), 1)), daily=daily)


def evaluate_all(cfgs, tables, seg, lo_seg, ckpt_dir, label):
    """Checkpointed evaluation of many configs on one segment -> array [n, 6] (n, exp, win, sr, mdd, total)."""
    ckpt_dir.mkdir(parents=True, exist_ok=True)
    CH = 5000; out = np.zeros((len(cfgs), 6), np.float64); t0 = time.time()
    for ci in range(0, len(cfgs), CH):
        f = ckpt_dir / f"{label}-{ci // CH:03d}.npy"
        if f.exists(): out[ci:ci + CH] = np.load(f); continue
        part = np.zeros((min(CH, len(cfgs) - ci), 6))
        for j, cfg in enumerate(cfgs[ci:ci + CH]):
            m = metrics(*trades(cfg, tables, seg, lo_seg), seg, lo_seg)
            part[j] = (m["n"], m["exp"], m["win"], m["sr"], m["mdd"], m["total"])
        np.save(f, part); out[ci:ci + CH] = part
        done = ci + len(part)
        if (done // CH) % 4 == 0 or done == len(cfgs):
            print(f"  [{label}] {done:,}/{len(cfgs):,} configs, {(time.time()-t0)/60:.1f} min", flush=True)
    return out


# ----------------------------------------------------------------- multiple testing
def dsr(daily, sr_trials, n_trials):
    """Deflated Sharpe Ratio: P(true SR > 0) after selecting the best of n_trials with SR variance var(sr_trials)."""
    T = len(daily); sd = daily.std(ddof=1)
    if sd == 0 or T < 10: return 0.0
    sr = daily.mean() / sd; g3 = skew(daily); g4 = kurtosis(daily, fisher=False)
    v = np.var(sr_trials, ddof=1); emc = 0.5772156649
    sr0 = math.sqrt(v) * ((1 - emc) * norm.ppf(1 - 1 / n_trials) + emc * norm.ppf(1 - 1 / (n_trials * math.e)))
    den = math.sqrt(max(1e-12, 1 - g3 * sr + (g4 - 1) / 4 * sr * sr))
    return float(norm.cdf((sr - sr0) * math.sqrt(T - 1) / den))


def neighbours(cfg):
    sz = sizes(); out = []
    names = SG.base_signals()
    for j, p in enumerate(PARAMS):
        for step in (-1, 1):
            c = cfg.copy(); v = int(c[j]) + step
            if p == "sig":       # ordinal only within the same signal family
                if not (0 <= v < sz[p]) or names[v][0] != names[int(cfg[j])][0]: continue
            elif p == "fam":     # neighbour delta / wing inside the same structure family
                f0 = FAMS[int(cfg[j])]
                cands = [i for i, f in enumerate(FAMS) if f[0] == f0[0] and
                         ((f[1] == f0[1] + step and f[2] == f0[2]) or (f[2] == f0[2] + step and f[1] == f0[1]))]
                for i in cands:
                    cc = cfg.copy(); cc[j] = i; out.append(cc)
                continue
            elif p in ("inv", "trend", "vol"): continue          # categorical switches, not neighbours
            elif not (0 <= v < sz[p]): continue
            c[j] = v; out.append(c)
    return out


def describe(cfg):
    c = dict(zip(PARAMS, (int(x) for x in cfg)))
    f, v = SG.base_signals()[c["sig"]]
    fam, di, wi = FAMS[c["fam"]]
    credit = fam in ("credit", "condor")
    pt = (O.CREDIT_PT if credit else O.DEBIT_PT)[c["pt"]]; sl = (O.CREDIT_SL if credit else O.DEBIT_SL)[c["sl"]]
    sig = f"{f}{' ' + v if v else ''}{' inverted' if c['inv'] else ''}"
    filt = [x for x in ("trend-aligned" if c["trend"] else "", {0: "", 1: "low-vol", 2: "high-vol"}[c["vol"]]) if x]
    wing = f", wing -{O.DWS[wi]:.2f}d" if fam in ("credit", "debit", "condor") else ""
    return (f"{sig}{' [' + ', '.join(filt) + ']' if filt else ''} -> {O.BUCKETS[c['bucket']]}DTE {fam} "
            f"{O.DELTAS[di]:.2f}d{wing} @ {O.TIMES[c['time']]}, PT {pt if pt is None else f'{pt:g}x'}, SL {sl if sl is None else f'{sl:g}x'}")


# ----------------------------------------------------------------- pipeline
def pipeline(label, shuffle):
    days, seg, tables = load(shuffle)
    cfgs, total = sample_configs()
    print(f"[{label}] space {total:,} combos, sampled {len(cfgs):,}; segments: search {days[seg[0]]}..{days[seg[1]-1]}, "
          f"validate {days[seg[1]]}..{days[seg[2]-1]}, holdout {days[seg[2]]}..{days[seg[3]-1]}", flush=True)
    S = evaluate_all(cfgs, tables, seg, 0, RUN / label, "search")
    elig = np.nonzero(S[:, 0] >= MIN_SEARCH_TRADES)[0]
    sr_trials = S[elig, 3]
    top = elig[np.argsort(-S[elig, 3])][:TOP_TO_VALIDATE]
    V = evaluate_all(cfgs[top], tables, seg, 1, RUN / label, "validate")
    ok = (V[:, 0] >= MIN_VAL_TRADES) & (V[:, 1] > 0) & (V[:, 3] > 0)
    order = top[ok][np.argsort(-V[ok, 3])]
    vmap = {int(i): V[k] for k, i in enumerate(top)}
    finals, rejected_nb = [], 0
    for i in order:
        cfg = cfgs[i]; nb = neighbours(cfg)
        good = 0
        for c in nb:
            ms = metrics(*trades(c, tables, seg, 0), seg, 0); mv = metrics(*trades(c, tables, seg, 1), seg, 1)
            good += ms["exp"] > 0 and mv["exp"] > 0
        if not nb or good / len(nb) < 2 / 3: rejected_nb += 1; continue
        ms = metrics(*trades(cfg, tables, seg, 0), seg, 0); mv = metrics(*trades(cfg, tables, seg, 1), seg, 1)
        finals.append(dict(idx=int(i), cfg=[int(x) for x in cfg], desc=describe(cfg), nb_pass=f"{good}/{len(nb)}",
                           search={k: v for k, v in ms.items() if k != "daily"},
                           validate={k: v for k, v in mv.items() if k != "daily"},
                           dsr_search=dsr(ms["daily"], sr_trials, len(elig)),
                           dsr_validate=dsr(mv["daily"], V[:, 3], len(top))))
        if len(finals) == N_FINAL: break
    summary = dict(label=label, total_space=total, sampled=len(cfgs), eligible=int(len(elig)),
                   best_search_sharpe=float(S[elig, 3].max() * math.sqrt(252)) if len(elig) else 0,
                   p95_search_sharpe=float(np.percentile(S[elig, 3], 95) * math.sqrt(252)) if len(elig) else 0,
                   validated=int(ok.sum()), best_validate_sharpe=float(V[ok, 3].max() * math.sqrt(252)) if ok.any() else 0,
                   neighbour_rejects=rejected_nb, finals=finals,
                   segments=[str(days[seg[0]]), str(days[seg[1]]), str(days[seg[2]]), str(days[seg[3] - 1])])
    (RUN / label).mkdir(parents=True, exist_ok=True)
    (RUN / label / "finalists.json").write_text(json.dumps(summary, indent=1))
    print(f"[{label}] eligible {len(elig):,}; best search Sharpe {summary['best_search_sharpe']:.2f} "
          f"(95th pct {summary['p95_search_sharpe']:.2f}); validated {ok.sum()}/{len(top)}, best validate Sharpe "
          f"{summary['best_validate_sharpe']:.2f}; neighbour rejects {rejected_nb}; finalists {len(finals)}", flush=True)
    for f in finals:
        print(f"  {f['desc']} | search n={f['search']['n']} SR={f['search']['sharpe']:.2f} DSR={f['dsr_search']:.2f} | "
              f"val n={f['validate']['n']} SR={f['validate']['sharpe']:.2f} DSR={f['dsr_validate']:.2f} | nb {f['nb_pass']}",
              flush=True)
    return summary


def holdout(label, shuffle, mult_note=""):
    path = RUN / label / "holdout.json"
    if path.exists():
        print(f"[{label}] holdout already run once - refusing to run again; showing stored result")
        return json.loads(path.read_text())
    summ = json.loads((RUN / label / "finalists.json").read_text())
    days, seg, tables = load(shuffle)
    res = []
    for f in summ["finals"]:
        cfg = np.array(f["cfg"], np.int16)
        m = metrics(*trades(cfg, tables, seg, 2), seg, 2)
        d = m.pop("daily", np.zeros(1))
        t = d.mean() / d.std(ddof=1) * math.sqrt(len(d)) if len(d) > 1 and d.std() > 0 else 0
        res.append(dict(desc=f["desc"], cfg=f["cfg"], holdout=m, t_stat=float(t), p_one_sided=float(1 - norm.cdf(t)),
                        dsr_search=f["dsr_search"], dsr_validate=f["dsr_validate"], nb_pass=f["nb_pass"],
                        search=f["search"], validate=f["validate"]))
    path.write_text(json.dumps(res, indent=1))
    return res


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "search"
    if cmd == "search":
        pipeline("real", False); pipeline("shuffled", True)
    elif cmd == "holdout":
        for lab, sh in (("real", False), ("shuffled", True)):
            for r in holdout(lab, sh):
                h = r["holdout"]
                print(f"[{lab}] {r['desc']} | holdout n={h['n']} exp={h['exp']:.2f} SR={h['sharpe']:.2f} p={r['p_one_sided']:.3f}")
