"""100,000-combination strategy search with walk-forward splits, deflation, a luck benchmark and one holdout test.

Protocol
  * splits by resolution (close) date: first 60% of days = search, next 20% = validate, last 20% = holdout.
    A market belongs to exactly one split (it has one close time).
  * unit of evidence = an EVENT (markets in one event are correlated): per-trade returns are averaged per event.
  * search: score every combo on the search split (t-stat of event returns, >= 30 events, mean > 0).
  * validate: top 200 by search t -> keep val mean > 0 with >= 15 events, rank by min(search t, validation t).
  * robustness: reject a combo unless >= 70% of its one-step parameter neighbours are profitable on search+validate.
  * holdout: the first 10 survivors are tested on the holdout ONCE.
  * multiple testing: Deflated Sharpe Ratio (Bailey & Lopez de Prado) with N = number of combos tried.
  * luck benchmark: the identical pipeline on data whose outcomes were shuffled across markets (same features,
    same prices, no link between them and the result).
  * costs: taker fills at the ask (spread paid), Kalshi fee rounded up per order on entry and on early exits.
"""
from __future__ import annotations

import json
import math
import time
from pathlib import Path
from statistics import NormalDist

import numpy as np

from .features import EXITS, H, SIZES

SIDES = ["yes", "no", "fav", "long"]
EDGES = [0.02, 0.05, 0.10, 0.20, 0.35, 0.50, 0.65, 0.80, 0.90, 0.95, 0.98]
BANDS = [(i, j) for i in range(len(EDGES)) for j in range(i + 1, len(EDGES))]
VOLS = [0, 100, 1000, 10000]
SPREADS = [0.01, 0.02, 0.03, 0.05, 0.10]
MOMS = [("none", 0, 0.0), ("follow", 6, 0.02), ("follow", 6, 0.05), ("fade", 6, 0.02), ("fade", 6, 0.05),
        ("follow", 24, 0.05), ("fade", 24, 0.05), ("follow", 24, 0.10), ("fade", 24, 0.10)]
DIMS = None  # set by make_space: sizes of each parameter dimension
N_COMBOS = 100_000
MIN_EV_SEARCH, MIN_EV_VAL, TOP_VAL, FINAL = 30, 15, 200, 10


def make_space(cat_names: list[str], cat_counts: dict[int, int]) -> list[int]:
    top = sorted(cat_counts, key=lambda c: -cat_counts[c])[:8]
    global CATS, DIMS
    CATS = [None] + top  # None = all categories
    DIMS = [len(SIDES), len(BANDS), len(H), len(CATS), len(VOLS), len(SPREADS), len(MOMS), len(EXITS), len(SIZES)]
    return DIMS


def describe(c, cat_names) -> dict:
    s, b, h, cat, v, sp, mo, ex, sz = c
    lo, hi = EDGES[BANDS[b][0]], EDGES[BANDS[b][1]]
    return {"side": SIDES[s], "price": f"{lo:.2f}-{hi:.2f}", "hours_before_close": H[h],
            "category": "all" if CATS[cat] is None else str(cat_names[CATS[cat]]), "min_vol24": VOLS[v],
            "max_spread": SPREADS[sp], "momentum": "none" if MOMS[mo][0] == "none" else f"{MOMS[mo][0]} {MOMS[mo][2]:.2f}/{MOMS[mo][1]}h",
            "exit": "hold" if EXITS[ex][0] is None else f"tp {EXITS[ex][0]:.2f} / sl {EXITS[ex][1]:.2f}",
            "size": SIZES[sz]}


class Split:
    """Pre-sliced arrays per decision horizon for fast masking."""

    def __init__(self, d: dict, idx: np.ndarray):
        self.by_h = []
        for hi in range(len(H)):
            sel = idx[d["h"][idx] == hi]
            ev = d["event"][sel]
            uniq, inv = np.unique(ev, return_inverse=True)
            self.by_h.append({k: d[k][sel] for k in ("cat", "mid", "spread", "ask_yes", "ask_no", "vol24", "mom6", "mom24", "ret")}
                             | {"ev": inv, "n_ev": len(uniq)})

    def evaluate(self, c) -> tuple:
        s, b, h, cat, v, sp, mo, ex, sz = c
        a = self.by_h[h]
        if not len(a["mid"]):
            return 0, 0.0, 0.0, 0.0
        if SIDES[s] == "yes":
            side = np.zeros(len(a["mid"]), np.int8)
        elif SIDES[s] == "no":
            side = np.ones(len(a["mid"]), np.int8)
        else:
            fav_no = a["mid"] < 0.5
            side = fav_no.astype(np.int8) if SIDES[s] == "fav" else (~fav_no).astype(np.int8)
        price = np.where(side == 0, a["ask_yes"], a["ask_no"])
        lo, hi = EDGES[BANDS[b][0]], EDGES[BANDS[b][1]]
        m = (price >= lo) & (price < hi) & (a["spread"] <= SPREADS[sp] + 1e-9) & (a["vol24"] >= max(VOLS[v], 2 * SIZES[sz]))
        if CATS[cat] is not None:
            m &= a["cat"] == CATS[cat]
        kind, lag, x = MOMS[mo]
        if kind != "none":
            mom = a["mom6"] if lag == 6 else a["mom24"]
            mom_side = np.where(side == 0, mom, -mom)
            m &= (mom_side >= x) if kind == "follow" else (mom_side <= -x)
        if not m.any():
            return 0, 0.0, 0.0, 0.0
        r = a["ret"][m, side[m], ex, sz]
        ok = ~np.isnan(r)
        if not ok.any():
            return 0, 0.0, 0.0, 0.0
        ev = a["ev"][m][ok]
        sums = np.bincount(ev, weights=r[ok], minlength=a["n_ev"])
        cnt = np.bincount(ev, minlength=a["n_ev"])
        er = sums[cnt > 0] / cnt[cnt > 0]  # one return per event
        n = len(er)
        if n < 2:
            return n, float(er.mean()) if n else 0.0, 0.0, 0.0
        mu, sd = float(er.mean()), float(er.std(ddof=1))
        return n, mu, sd, (mu / sd * math.sqrt(n) if sd > 0 else 0.0)

    def event_returns(self, c) -> np.ndarray:
        """Same as evaluate but returns the per-event return series (for DSR moments)."""
        s, b, h, cat, v, sp, mo, ex, sz = c
        a = self.by_h[h]
        side_mode = SIDES[s]
        side = (np.zeros if side_mode == "yes" else np.ones)(len(a["mid"]), np.int8) if side_mode in ("yes", "no") else \
            ((a["mid"] < 0.5) if side_mode == "fav" else (a["mid"] >= 0.5)).astype(np.int8)
        price = np.where(side == 0, a["ask_yes"], a["ask_no"])
        lo, hi = EDGES[BANDS[b][0]], EDGES[BANDS[b][1]]
        m = (price >= lo) & (price < hi) & (a["spread"] <= SPREADS[sp] + 1e-9) & (a["vol24"] >= max(VOLS[v], 2 * SIZES[sz]))
        if CATS[cat] is not None:
            m &= a["cat"] == CATS[cat]
        kind, lag, x = MOMS[mo]
        if kind != "none":
            mom = a["mom6"] if lag == 6 else a["mom24"]
            ms = np.where(side == 0, mom, -mom)
            m &= (ms >= x) if kind == "follow" else (ms <= -x)
        r = a["ret"][m, side[m], ex, sz]
        ok = ~np.isnan(r)
        ev = a["ev"][m][ok]
        sums = np.bincount(ev, weights=r[ok], minlength=a["n_ev"])
        cnt = np.bincount(ev, minlength=a["n_ev"])
        return sums[cnt > 0] / cnt[cnt > 0]


def neighbours(c):
    s, b, h, cat, v, sp, mo, ex, sz = c
    out = []
    lo, hi = BANDS[b]
    for dlo, dhi in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        nb = (lo + dlo, hi + dhi)
        if nb in BANDS:
            out.append((s, BANDS.index(nb), h, cat, v, sp, mo, ex, sz))
    for dim, size in ((2, len(H)), (4, len(VOLS)), (5, len(SPREADS)), (8, len(SIZES))):
        for d in (-1, 1):
            x = list(c)
            x[dim] += d
            if 0 <= x[dim] < size:
                out.append(tuple(x))
    kind, lag, _ = MOMS[mo]
    if kind != "none":
        for j, (k2, l2, _) in enumerate(MOMS):
            if j != mo and k2 == kind and l2 == lag:
                x = list(c); x[6] = j; out.append(tuple(x))
    return out


def deflated_sharpe(er: np.ndarray, sr_trials: np.ndarray, n_trials: int) -> float:
    """Probability the true Sharpe exceeds what the best of n_trials pure-luck strategies would show."""
    n = len(er)
    if n < 3 or er.std(ddof=1) == 0:
        return 0.0
    sr = er.mean() / er.std(ddof=1)
    g3 = float(((er - er.mean()) ** 3).mean() / er.std() ** 3)
    g4 = float(((er - er.mean()) ** 4).mean() / er.std() ** 4)
    v = float(np.var(sr_trials))
    z = NormalDist().inv_cdf
    gamma = 0.5772156649
    sr0 = math.sqrt(v) * ((1 - gamma) * z(1 - 1 / n_trials) + gamma * z(1 - 1 / (n_trials * math.e)))
    denom = math.sqrt(max(1e-12, 1 - g3 * sr + (g4 - 1) / 4 * sr ** 2))
    return NormalDist().cdf((sr - sr0) * math.sqrt(n - 1) / denom)


def sample_combos(n: int, seed: int = 7) -> list[tuple]:
    rng = np.random.default_rng(seed)
    total = int(np.prod(DIMS))
    picks = set()
    while len(picks) < min(n, total):
        picks.update(int(x) for x in rng.integers(0, total, size=n))
    flat = sorted(picks)[:n] if len(picks) > n else sorted(picks)
    rng.shuffle(flat)
    combos = []
    for f in flat[:n]:
        c = []
        for size in reversed(DIMS):
            c.append(f % size)
            f //= size
        combos.append(tuple(reversed(c)))
    return combos


def search(split: Split, combos: list[tuple], ckpt: Path, label: str, log=print) -> np.ndarray:
    """Metrics [n_events, mean, sd, t] for every combo, checkpointed every 5,000."""
    res = np.full((len(combos), 4), np.nan)
    start = 0
    if ckpt.exists():
        z = np.load(ckpt)
        res[: len(z["res"])] = z["res"]
        start = int(z["done"])
    t0 = time.time()
    for i in range(start, len(combos)):
        res[i] = split.evaluate(combos[i])
        if (i + 1) % 5000 == 0 or i + 1 == len(combos):
            np.savez(ckpt, res=res[: i + 1], done=i + 1)
            ok = res[: i + 1, 0] >= MIN_EV_SEARCH
            best = np.nanmax(res[: i + 1, 3][ok]) if ok.any() else float("nan")
            log(f"  [{label}] {i + 1:,}/{len(combos):,} combos, best t so far {best:.2f}, {time.time() - t0:.0f}s")
    return res


def pipeline(d: dict, splits: dict[str, np.ndarray], combos, ckdir: Path, label: str, cat_names, log=print) -> dict:
    sp = {k: Split(d, v) for k, v in splits.items()}
    sv = Split(d, np.concatenate([splits["search"], splits["validate"]]))
    res = search(sp["search"], combos, ckdir / f"search_{label}.npz", label, log)
    ok = (res[:, 0] >= MIN_EV_SEARCH) & (res[:, 1] > 0)
    order = np.argsort(-np.where(ok, res[:, 3], -np.inf))[:TOP_VAL]
    val = []
    for i in order:
        if not ok[i]:
            break
        n, mu, sd, t = sp["validate"].evaluate(combos[i])
        if n >= MIN_EV_VAL and mu > 0:
            val.append((min(t, res[i, 3]), int(i), n, mu))  # rank by the weaker of search and validation t
    val.sort(reverse=True)
    finalists, rejected = [], 0
    for t, i, n, mu in val:
        nb = neighbours(combos[i])
        good = sum(1 for c in nb if (lambda r: r[0] >= MIN_EV_SEARCH and r[1] > 0)(sv.evaluate(c)))
        if nb and good / len(nb) >= 0.7:
            finalists.append(i)
        else:
            rejected += 1
        if len(finalists) == FINAL:
            break
    sr_trials = (res[ok, 1] / res[ok, 2])[np.isfinite(res[ok, 1] / res[ok, 2])]
    out = []
    for i in finalists:  # HOLDOUT: each finalist evaluated exactly once
        c = combos[i]
        hn, hmu, hsd, ht = sp["holdout"].evaluate(c)
        out.append({"params": describe(c, cat_names), "search": dict(zip(("events", "mean", "sd", "t"), map(float, res[i]))),
                    "validate": dict(zip(("events", "mean", "sd", "t"), map(float, sp["validate"].evaluate(c)))),
                    "holdout": {"events": int(hn), "mean": hmu, "t": ht},
                    "deflated_sharpe_search": deflated_sharpe(sp["search"].event_returns(c), sr_trials, len(combos))})
    return {"label": label, "combos": len(combos), "eligible_search": int(ok.sum()),
            "best_search_t": float(np.nanmax(res[ok, 3])) if ok.any() else None,
            "search_t_gt_3": int((res[ok, 3] > 3).sum()), "passed_validation": len(val),
            "rejected_by_neighbours": rejected, "finalists": out}


def baselines(d: dict, holdout: np.ndarray, cat_names) -> list[dict]:
    """Earlier strategies, fixed in advance (no search), on the same holdout."""
    sp = Split(d, holdout)
    cat = lambda name: next((j for j, c in enumerate(CATS) if c is not None and cat_names[c] == name), 0)
    band = lambda lo, hi: BANDS.index((EDGES.index(lo), EDGES.index(hi)))
    hix = lambda h: H.index(h)
    defs = {
        "favorite 80-95c, 24h, hold (kalshibot paper strategy, taker)": (2, band(0.80, 0.95), hix(24), 0, 1, 3, 0, 0, 1),
        "favorite 50-80c weather, 24h, hold (weather market-only idea)": (2, band(0.50, 0.80), hix(24), cat("Climate and Weather"), 0, 3, 0, 0, 1),
        "longshots 2-10c, 24h, hold (typical retail)": (3, band(0.02, 0.10), hix(24), 0, 0, 4, 0, 0, 0),
    }
    out = []
    for name, c in defs.items():
        n, mu, sd, t = sp.evaluate(c)
        out.append({"strategy": name, "holdout_events": int(n), "holdout_mean": mu, "holdout_t": t})
    return out


def run(data: Path, ckdir: Path, out: Path, log=print, n_combos: int = N_COMBOS) -> dict:
    z = np.load(data, allow_pickle=False)
    d = {k: z[k] for k in z.files if k != "cat_names"}
    cat_names = [str(x) for x in z["cat_names"]]
    days = np.unique(d["close"] // 86400)
    cut1, cut2 = days[int(len(days) * 0.6)], days[int(len(days) * 0.8)]
    day = d["close"] // 86400
    splits = {"search": np.where(day < cut1)[0], "validate": np.where((day >= cut1) & (day < cut2))[0],
              "holdout": np.where(day >= cut2)[0]}
    counts = {int(c): int((d["cat"][splits["search"]] == c).sum()) for c in np.unique(d["cat"])}
    make_space(cat_names, counts)
    combos = sample_combos(n_combos)
    ckdir.mkdir(parents=True, exist_ok=True)
    from datetime import datetime, timezone
    fmt = lambda x: datetime.fromtimestamp(int(x) * 86400, timezone.utc).date().isoformat()
    summary = {"rows": int(len(d["h"])), "space": int(np.prod(DIMS)), "dims": DIMS,
               "splits": {k: {"rows": int(len(v)), "events": int(len(np.unique(d["event"][v]))),
                              "from": fmt(day[v].min()) if len(v) else None, "to": fmt(day[v].max()) if len(v) else None}
                          for k, v in splits.items()}}
    log(f"rows {summary['rows']:,}; space {summary['space']:,} combos, sampling {len(combos):,}; splits {summary['splits']}")
    summary["real"] = pipeline(d, splits, combos, ckdir, "real", cat_names, log)
    rng = np.random.default_rng(11)
    shuf = dict(d)
    shuf["ret"] = d["ret"].copy()
    for v in splits.values():  # break every link between features/prices and outcomes, within each split
        for hi in range(len(H)):
            rows = v[d["h"][v] == hi]
            shuf["ret"][rows] = d["ret"][rng.permutation(rows)]
    summary["shuffled"] = pipeline(shuf, splits, combos, ckdir, "shuffled", cat_names, log)
    summary["baselines"] = baselines(d, splits["holdout"], cat_names)
    out.write_text(json.dumps(summary, indent=1, default=float))
    return summary
