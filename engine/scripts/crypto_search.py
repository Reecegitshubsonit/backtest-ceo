"""100,000-combination crypto strategy search on BTC + ETH (SOL shown separately), Alpaca bars, 0.60% round trip.

Space (per combo): timeframe {1h, 4h, 1d} x entry signal (30: momentum, MA cross, breakouts, RSI, Bollinger, z-score,
candle patterns, volume spike) x trend filter (4) x volatility filter (3) x volume filter (3) x time-of-day (4, intraday
only) x day-of-week (3) x max holding period (6) x ATR stop (4) x ATR take-profit (3)  ~= 2.1M; 100,000 drawn at random.
Long only (Alpaca spot). Signal at bar close, fill at next bar open; stops/targets intrabar (stop checked first).

Protocol (all bars 2021-01-01 .. last full day, split by time): first 60% search, next 20% validate, last 20% holdout.
  1. search: score = mean daily Sharpe of BTC and ETH; >= 30 trades per coin required.
  2. validate: top 1,000 by search score -> both coins Sharpe > 0 and >= 30 trades in validation; rank by validation score.
  3. neighbours: one-step changes of hold / stop / target / entry lookback, and dropping each filter; >= 2/3 must be
     positive in search and validation, else rejected.
  4. top 10 robust -> holdout once (BTC, ETH, SOL). Deflated Sharpe (N = 100,000 on search; N = 10 on holdout).
  5. luck benchmark: identical pipeline on bar-shuffled data (search + validation bars permuted jointly for BTC/ETH).
No Level 2: Alpaca serves only the latest order-book snapshot (historical endpoint 404), so no order-book features.

Checkpoints: engine/.cache/crypto_search/<run>/chunk_*.npy (5,000 combos each); rerun resumes. Prints summaries only.
Run: python engine/scripts/crypto_search.py --out docs/crypto-search-results-tables.md
"""
import argparse
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import NormalDist

import numpy as np
import pandas as pd
from numba import njit, prange

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from crypto_edge_backtest import fetch, segments, simulate, tsmom  # noqa: E402

SIDE = 0.003          # 0.25% fee + 0.05% slippage per side = 0.60% round trip
N_COMBOS = 100_000
CHUNK = 5_000
SEED = 20261103
MIN_TRADES = 30
N01 = NormalDist()
TFS = ("1h", "4h", "1d")
HOLDS = (1, 3, 6, 12, 24, 48)
STOPS = (0.0, 1.0, 2.0, 3.0)
TPS = (0.0, 2.0, 4.0)

# entry families: (family, [param values]); each (family, value) is one entry signal
ENTRY_FAMS = [("tsmom", [12, 24, 48, 96, 192]), ("ema_cross", [(5, 20), (10, 50), (20, 100), (50, 200)]),
              ("donchian", [10, 20, 55, 100]), ("rsi14_below", [25, 30]), ("rsi2_below", [5, 10]),
              ("rsi14_above", [60, 70]), ("bb_lower", [2.0]), ("bb_upper", [2.0]), ("z50_below", [-2.0]),
              ("engulfing", [0]), ("hammer", [0]), ("inside_breakout", [0]), ("down3", [0]), ("up3", [0]),
              ("big_bar_up", [2.0]), ("volume_spike_up", [3.0])]
ENTRIES = [(f, i, v) for f, vals in ENTRY_FAMS for i, v in enumerate(vals)]  # 30
TREND = ("none", "above_sma50", "above_sma200", "below_sma200")
VOLAT = ("none", "atr_low", "atr_high")
VOLUME = ("none", "vol_above_avg", "vol_below_avg")
TOD = ("none", "00-08", "08-16", "16-24")
DOW = ("none", "weekdays", "weekend")


# ---------------- data ----------------
def load_1h(sym, end, cache):
    return fetch(sym, "1Hour", datetime(2021, 1, 1, tzinfo=timezone.utc), end, cache)


def resample(df, rule):
    r = df.resample(rule, label="left", closed="left")
    out = pd.DataFrame({"o": r["o"].first(), "h": r["h"].max(), "l": r["l"].min(), "c": r["c"].last(), "v": r["v"].sum()})
    return out.dropna()


def shuffle_1h(dfs, lo, hi, seed):
    """Permute bar shapes (gap, h, l, c relative to open, volume) inside [lo, hi) with ONE permutation shared by all
    coins on their common timestamps, rebuild prices. Kills any time structure, keeps the return distribution."""
    common = dfs[0].index
    for d in dfs[1:]:
        common = common.intersection(d.index)
    sel = common[(common >= lo) & (common < hi)]
    perm = np.random.default_rng(seed).permutation(len(sel))
    out = []
    for d in dfs:
        d = d.copy()
        x = d.loc[sel]
        prev_c = d["c"].shift(1).loc[sel].fillna(x["o"].iloc[0])
        shapes = np.c_[np.log(x["o"] / prev_c), np.log(x["h"] / x["o"]), np.log(x["l"] / x["o"]), np.log(x["c"] / x["o"]), x["v"]][perm]
        c0 = prev_c.iloc[0]
        o = np.empty(len(sel)); c = np.empty(len(sel))
        for k in range(len(sel)):
            o[k] = c0 * np.exp(shapes[k, 0])
            c[k] = o[k] * np.exp(shapes[k, 3])
            c0 = c[k]
        d.loc[sel, "o"], d.loc[sel, "c"] = o, c
        d.loc[sel, "h"], d.loc[sel, "l"] = o * np.exp(shapes[:, 1]), o * np.exp(shapes[:, 2])
        d.loc[sel, "v"] = shapes[:, 4]
        # rescale everything after hi so the series stays continuous
        after = d.index >= hi
        if after.any():
            k = d.loc[sel[-1], "c"] / x["c"].iloc[-1]
            d.loc[after, ["o", "h", "l", "c"]] *= k
        out.append(d)
    return out


# ---------------- features ----------------
def rsi(c, n):
    dd = c.diff()
    up = dd.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-dd.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn)


def features(df):
    """Boolean feature matrix (n_feat x n) evaluated at each bar's close, plus ATR. Row order: ENTRIES, then filters."""
    o, h, l, c, v = (df[k] for k in "ohlcv")
    pc = c.shift()
    tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1 / 14, adjust=False).mean()
    body = (c - o).abs()
    rows = []
    for fam, _, p in ENTRIES:
        if fam == "tsmom":
            x = c.pct_change(p) > 0
        elif fam == "ema_cross":
            x = c.ewm(span=p[0], adjust=False).mean() > c.ewm(span=p[1], adjust=False).mean()
        elif fam == "donchian":
            x = c > h.rolling(p).max().shift(1)
        elif fam == "rsi14_below":
            x = rsi(c, 14) < p
        elif fam == "rsi2_below":
            x = rsi(c, 2) < p
        elif fam == "rsi14_above":
            x = rsi(c, 14) > p
        elif fam in ("bb_lower", "bb_upper"):
            m, sd = c.rolling(20).mean(), c.rolling(20).std()
            x = c < m - p * sd if fam == "bb_lower" else c > m + p * sd
        elif fam == "z50_below":
            x = (c - c.rolling(50).mean()) / c.rolling(50).std() < p
        elif fam == "engulfing":
            x = (c > o) & (o.shift() > c.shift()) & (c >= o.shift()) & (o <= c.shift())
        elif fam == "hammer":
            lw = pd.concat([o, c], axis=1).min(axis=1) - l
            x = (lw > 2 * body) & (c > l + 2 / 3 * (h - l)) & (h > l)
        elif fam == "inside_breakout":
            inside = (h.shift() < h.shift(2)) & (l.shift() > l.shift(2))
            x = inside & (c > h.shift())
        elif fam == "down3":
            x = (c < pc) & (pc < pc.shift()) & (pc.shift() < pc.shift(2))
        elif fam == "up3":
            x = (c > pc) & (pc > pc.shift()) & (pc.shift() > pc.shift(2))
        elif fam == "big_bar_up":
            x = ((h - l) > p * atr.shift()) & (c > o)
        elif fam == "volume_spike_up":
            x = (v > p * v.rolling(20).mean().shift()) & (c > o)
        rows.append(x)
    atrp = atr / c
    med = atrp.rolling(500, min_periods=100).median()
    va = v.rolling(20).mean().shift()
    hr = df.index.hour
    dow = df.index.dayofweek
    filt = {"above_sma50": c > c.rolling(50).mean(), "above_sma200": c > c.rolling(200).mean(),
            "below_sma200": c < c.rolling(200).mean(), "atr_low": atrp < med, "atr_high": atrp > med,
            "vol_above_avg": v > va, "vol_below_avg": v < va,
            "00-08": pd.Series(hr < 8, df.index), "08-16": pd.Series((hr >= 8) & (hr < 16), df.index),
            "16-24": pd.Series(hr >= 16, df.index), "weekdays": pd.Series(dow < 5, df.index), "weekend": pd.Series(dow >= 5, df.index)}
    names = [f"{f}:{p}" for f, _, p in ENTRIES] + list(filt)
    F = np.vstack([np.asarray(x.fillna(False), dtype=np.bool_) for x in rows + list(filt.values())])
    return F, atr.values.astype(np.float64), names


def filter_row(names, key):
    return -1 if key == "none" else names.index(key)


# ---------------- kernel ----------------
@njit(cache=True)
def _run(F, o, h, l, c, atr, day, gap, cb, i0, i1, side, n_days, out_tr, out_ent):
    """One combo over bars [i0, i1). cb = [entry, trend, volat, volume, tod, dow, hold, stop*10, tp*10] (rows or -1).
    Returns (daily log-return array, n_trades). Trade returns / entry bars written to out_tr / out_ent."""
    dl = np.zeros(n_days)
    e, ft, fv, fq, fh, fd, hold = cb[0], cb[1], cb[2], cb[3], cb[4], cb[5], cb[6]
    sm, tm = cb[7] / 10.0, cb[8] / 10.0
    pos = False
    entry = prev = stp = tpp = 0.0
    held = 0
    nt = 0
    lc = np.log(1.0 - side)
    for i in range(max(i0, 1), i1):
        if not pos:
            k = i - 1
            if (F[e, k] and (ft < 0 or F[ft, k]) and (fv < 0 or F[fv, k]) and (fq < 0 or F[fq, k])
                    and (fh < 0 or F[fh, k]) and (fd < 0 or F[fd, k]) and atr[k] > 0 and not gap[i]):
                pos = True
                entry = o[i]
                prev = entry
                held = 0
                stp = entry - sm * atr[k] if sm > 0 else -1.0
                tpp = entry + tm * atr[k] if tm > 0 else 1e300
                dl[day[i]] += lc
                out_ent[nt] = i
        if pos:
            px = -1.0
            if stp > 0 and l[i] <= stp:
                px = min(stp, o[i])
            elif h[i] >= tpp:
                px = max(tpp, o[i])
            else:
                held += 1
                if held >= hold or i == i1 - 1 or (i + 1 < len(gap) and gap[i + 1]):
                    px = c[i]
            if px > 0:
                dl[day[i]] += np.log(px / prev) + lc
                out_tr[nt] = px / entry * (1.0 - side) ** 2 - 1.0
                nt += 1
                pos = False
            else:
                dl[day[i]] += np.log(c[i] / prev)
                prev = c[i]
    return dl, nt


@njit(cache=True)
def _seg_stats(dl, tr, ent_day, nt, d0, d1):
    """trades, mean trade, win rate, daily Sharpe (ann.), max DD for days [d0, d1) (trades by entry day)."""
    n = 0
    s = 0.0
    w = 0
    for k in range(nt):
        if d0 <= ent_day[k] < d1:
            n += 1
            s += tr[k]
            if tr[k] > 0:
                w += 1
    m = 0.0
    q = 0.0
    eq = 1.0
    pk = 1.0
    mdd = 0.0
    for d in range(d0, d1):
        r = np.exp(dl[d]) - 1.0
        m += r
        q += r * r
        eq *= 1.0 + r
        pk = max(pk, eq)
        mdd = min(mdd, eq / pk - 1.0)
    T = d1 - d0
    mu = m / T
    var = q / T - mu * mu
    sh = mu / np.sqrt(var) * np.sqrt(365.0) if var > 1e-18 else 0.0
    return n, (s / n if n else 0.0), (w / n if n else 0.0), sh, mdd


@njit(parallel=True, cache=True)
def run_batch(F, o, h, l, c, atr, day, gap, combos, i1, d_bounds, side, n_days):
    """Search+validation stats for many combos on one coin/timeframe. Out: [K, 2 segments, 5 stats]."""
    K = combos.shape[0]
    out = np.zeros((K, 2, 5))
    for j in prange(K):
        tr = np.empty(len(o))
        ent = np.empty(len(o), dtype=np.int64)
        dl, nt = _run(F, o, h, l, c, atr, day, gap, combos[j], 1, i1, side, n_days, tr, ent)
        ed = np.empty(nt, dtype=np.int64)
        for k in range(nt):
            ed[k] = day[ent[k]]
        for sgi in range(2):
            a0, a1, a2, a3, a4 = _seg_stats(dl, tr, ed, nt, d_bounds[sgi], d_bounds[sgi + 1])
            out[j, sgi, 0] = a0
            out[j, sgi, 1] = a1
            out[j, sgi, 2] = a2
            out[j, sgi, 3] = a3
            out[j, sgi, 4] = a4
    return out


# ---------------- combos ----------------
def draw_combos(rng):
    """Unique random combos as dict-able int tuples: (tf, entry, trend, volat, volume, tod, dow, hold_i, stop_i, tp_i)."""
    dims = (len(TFS), len(ENTRIES), len(TREND), len(VOLAT), len(VOLUME), len(TOD), len(DOW), len(HOLDS), len(STOPS), len(TPS))
    seen, out = set(), []
    while len(out) < N_COMBOS:
        x = tuple(int(rng.integers(0, n)) for n in dims)
        if TFS[x[0]] == "1d" and x[5] != 0:
            x = x[:5] + (0,) + x[6:]   # no time-of-day on daily bars
        if x not in seen:
            seen.add(x)
            out.append(x)
    return np.array(out, dtype=np.int64)


def to_kernel(P, names):
    """Parameter tuples -> kernel rows for one timeframe's feature names."""
    rows = np.empty((len(P), 9), dtype=np.int64)
    for k, x in enumerate(P):
        rows[k] = (x[1], filter_row(names, TREND[x[2]]), filter_row(names, VOLAT[x[3]]), filter_row(names, VOLUME[x[4]]),
                   filter_row(names, TOD[x[5]]), filter_row(names, DOW[x[6]]), HOLDS[x[7]], int(STOPS[x[8]] * 10), int(TPS[x[9]] * 10))
    return rows


def describe(x):
    f, _, p = ENTRIES[x[1]]
    parts = [TFS[x[0]], f"{f}({p})" if p != 0 else f]
    for lab, vals, i in (("trend", TREND, x[2]), ("vol", VOLAT, x[3]), ("volume", VOLUME, x[4]), ("tod", TOD, x[5]), ("dow", DOW, x[6])):
        if vals[i] != "none":
            parts.append(vals[i])
    parts.append(f"hold {HOLDS[x[7]]}")
    if STOPS[x[8]]:
        parts.append(f"stop {STOPS[x[8]]:g}ATR")
    if TPS[x[9]]:
        parts.append(f"tp {TPS[x[9]]:g}ATR")
    return " | ".join(parts)


def neighbours(x):
    out = []
    x = list(x)
    for dim, n in ((7, len(HOLDS)), (8, len(STOPS)), (9, len(TPS))):
        for s in (-1, 1):
            if 0 <= x[dim] + s < n:
                y = x[:]; y[dim] += s; out.append(tuple(y))
    fam, idx, _ = ENTRIES[x[1]]
    for s in (-1, 1):
        j = [k for k, (f, i, _) in enumerate(ENTRIES) if f == fam and i == idx + s]
        if j:
            y = x[:]; y[1] = j[0]; out.append(tuple(y))
    for dim in (2, 3, 4, 5, 6):
        if x[dim] != 0:
            y = x[:]; y[dim] = 0; out.append(tuple(y))
    return out


# ---------------- universe ----------------
class Universe:
    """Per coin per timeframe: arrays + features; day ids from 2021-01-01; split boundaries by calendar day."""

    def __init__(self, h1, start, end):
        self.start = start
        self.n_days = (end.normalize() - start).days + 1
        self.d = {}
        for sym, df in h1.items():
            for tf in TFS:
                x = df if tf == "1h" else resample(df, "4h" if tf == "4h" else "1D")
                F, atr, names = features(x)
                day = ((x.index - start).days).values.astype(np.int64)
                gap = np.r_[False, np.diff(x.index.values).astype("timedelta64[h]").astype(np.int64) > 48]
                self.d[(sym, tf)] = dict(F=F, atr=atr, names=names, day=day, gap=gap, idx=x.index,
                                         **{k: x[k].values.astype(np.float64) for k in "ohlc"})

    def bar_at_day(self, sym, tf, dayid):
        return int(np.searchsorted(self.d[(sym, tf)]["day"], dayid))


def search(U, P, syms, bounds, ckdir, label):
    """Run all combos for syms; checkpoints per chunk. Returns stats [K, coin, seg, 5]."""
    ckdir.mkdir(parents=True, exist_ok=True)
    res = np.zeros((len(P), len(syms), 2, 5))
    t0 = time.time()
    for ci in range(0, len(P), CHUNK):
        f = ckdir / f"chunk_{ci // CHUNK:03d}.npy"
        if f.exists():
            res[ci:ci + CHUNK] = np.load(f)
            continue
        part = P[ci:ci + CHUNK]
        out = np.zeros((len(part), len(syms), 2, 5))
        for ti, tf in enumerate(TFS):
            m = part[:, 0] == ti
            if not m.any():
                continue
            for si, s in enumerate(syms):
                D = U.d[(s, tf)]
                i1 = U.bar_at_day(s, tf, bounds[2])
                out[m, si] = run_batch(D["F"], D["o"], D["h"], D["l"], D["c"], D["atr"], D["day"], D["gap"],
                                       to_kernel(part[m], D["names"]), i1, np.array(bounds[:3], dtype=np.int64), SIDE, U.n_days)
        np.save(f, out)
        res[ci:ci + CHUNK] = out
        done = ci + len(part)
        if done == len(P):
            print(f"  [{label}] {done:>7,}/{len(P):,} combos  {time.time() - t0:6.0f}s", flush=True)
    return res


def score(res):
    """Per combo: search score, validation score, eligibility flags (BTC+ETH)."""
    sh = res[:, :, :, 3]
    nt = res[:, :, :, 0]
    s_ok = (nt[:, :, 0] >= MIN_TRADES).all(axis=1)
    v_ok = (nt[:, :, 1] >= MIN_TRADES).all(axis=1) & (sh[:, :, 1] > 0).all(axis=1) & (sh[:, :, 0] > 0).all(axis=1)
    return sh[:, :, 0].mean(axis=1), sh[:, :, 1].mean(axis=1), s_ok, v_ok


def pipeline(U, P, res, syms, bounds, ckdir, label, n_top_search=1000, n_final=10):
    s_sc, v_sc, s_ok, v_ok = score(res)
    order = np.argsort(-np.where(s_ok, s_sc, -np.inf))[:n_top_search]
    cand = [k for k in order if v_ok[k]]
    cand.sort(key=lambda k: -v_sc[k])
    index = {tuple(x): k for k, x in enumerate(map(tuple, P))}
    chosen, checked = [], []
    for k in cand:
        nb = neighbours(tuple(P[k]))
        new = [x for x in nb if x not in index]
        nres = {}
        if new:
            arr = np.array(new, dtype=np.int64)
            r = _direct(U, arr, syms, bounds)
            for x, rr in zip(new, r):
                nres[x] = rr
        good = 0
        for x in nb:
            rr = res[index[x]] if x in index else nres[x]
            if (rr[:, 0, 3].mean() > 0) and (rr[:, 1, 3].mean() > 0):
                good += 1
        ok = good >= np.ceil(2 / 3 * len(nb))
        checked.append((k, good, len(nb), ok))
        if ok:
            chosen.append(k)
        if len(chosen) == n_final:
            break
    return dict(s_sc=s_sc, v_sc=v_sc, s_ok=s_ok, v_ok=v_ok, top_search=order, cand=cand, chosen=chosen, checked=checked)


def _direct(U, arr, syms, bounds):
    out = np.zeros((len(arr), len(syms), 2, 5))
    for ti, tf in enumerate(TFS):
        m = arr[:, 0] == ti
        if not m.any():
            continue
        for si, s in enumerate(syms):
            D = U.d[(s, tf)]
            out[m, si] = run_batch(D["F"], D["o"], D["h"], D["l"], D["c"], D["atr"], D["day"], D["gap"],
                                   to_kernel(arr[m], D["names"]), U.bar_at_day(s, tf, bounds[2]),
                                   np.array(bounds[:3], dtype=np.int64), SIDE, U.n_days)
    return out


def period(U, x, sym, d0, d1):
    """Run one combo over days [d0, d1) (signals warm from all prior bars). Returns stats dict and daily returns."""
    tf = TFS[x[0]]
    D = U.d[(sym, tf)]
    kb = to_kernel(np.array([x]), D["names"])[0]
    n = len(D["o"])
    tr, ent = np.empty(n), np.empty(n, dtype=np.int64)
    i0, i1 = U.bar_at_day(sym, tf, d0), U.bar_at_day(sym, tf, d1)
    dl, nt = _run(D["F"], D["o"], D["h"], D["l"], D["c"], D["atr"], D["day"], D["gap"], kb, i0, i1, SIDE, U.n_days, tr, ent)
    ed = D["day"][ent[:nt]]
    st = _seg_stats(dl, tr, ed, nt, d0, d1)
    return dict(zip(("trades", "exp", "win", "sharpe", "maxdd"), st)), np.exp(dl[d0:d1]) - 1


def holdout(U, x, sym, bounds):
    return period(U, x, sym, bounds[2], bounds[3])


def dsr(daily, n_trials, sr_var_daily):
    x = np.asarray(daily)
    T = len(x)
    if T < 30 or x.std() == 0:
        return np.nan
    sr = x.mean() / x.std()
    g = 0.5772156649
    sr0 = np.sqrt(sr_var_daily) * ((1 - g) * N01.inv_cdf(1 - 1 / n_trials) + g * N01.inv_cdf(1 - 1 / (n_trials * np.e))) if n_trials > 1 else 0.0
    s = pd.Series(x)
    den = np.sqrt(max(1 - s.skew() * sr + (s.kurt() + 2) / 4 * sr ** 2, 1e-12))
    return N01.cdf((sr - sr0) * np.sqrt(T - 1) / den)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out")
    ap.add_argument("--cache", default=str(HERE.parent / ".cache"))
    ap.add_argument("--shuffles", type=int, default=10, help="independent shuffled-data luck benchmarks")
    ap.add_argument("--end", default=None, help="last full UTC day YYYY-MM-DD (default: yesterday)")
    a = ap.parse_args()
    cache = Path(a.cache)
    end = (datetime.fromisoformat(a.end).replace(tzinfo=timezone.utc) + timedelta(days=1) if a.end else
           datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)) - timedelta(seconds=1)
    start = pd.Timestamp("2021-01-01", tz="UTC")
    syms_all = ["BTC/USD", "ETH/USD", "SOL/USD"]
    h1 = {s: load_1h(s, end, cache / "crypto_edge") for s in syms_all}
    n_days = (pd.Timestamp(end).normalize() - start).days + 1
    b1, b2 = int(round(0.6 * n_days)), int(round(0.8 * n_days))
    bounds = (0, b1, b2, n_days)
    day = lambda k: (start + pd.Timedelta(days=k)).date()
    print(f"bars 2021-01-01 -> {end.date()} ({n_days} days). search -> {day(b1 - 1)}, validate -> {day(b2 - 1)}, holdout -> {end.date()}")
    print("Level 2: not used - Alpaca has no historical order-book data (latest snapshot only).")
    P = draw_combos(np.random.default_rng(SEED))
    space = len(TFS[:2]) * len(ENTRIES) * len(TREND) * len(VOLAT) * len(VOLUME) * len(TOD) * len(DOW) * len(HOLDS) * len(STOPS) * len(TPS) \
        + len(ENTRIES) * len(TREND) * len(VOLAT) * len(VOLUME) * len(DOW) * len(HOLDS) * len(STOPS) * len(TPS)
    print(f"space {space:,} combos; drawn {len(P):,} (seed {SEED})")
    syms = ["BTC/USD", "ETH/USD"]
    tag = f"s{SEED}_n{N_COMBOS}_{end:%Y%m%d}"
    report = {}
    for label in ["real"] + [f"shuffled_{k}" for k in range(a.shuffles)]:
        data = h1
        if label != "real":
            lo, hi = start, start + pd.Timedelta(days=b2)
            sh = shuffle_1h([h1[s] for s in syms], lo, hi, SEED + 1 + int(label.split("_")[1]))
            data = {"BTC/USD": sh[0], "ETH/USD": sh[1]}
        t0 = time.time()
        U = Universe(data, start, pd.Timestamp(end))
        print(f"[{label}] features built in {time.time() - t0:.0f}s")
        res = search(U, P, syms, bounds, cache / "crypto_search" / f"{tag}_{label}", label)
        pl = pipeline(U, P, res, syms, bounds, cache / "crypto_search" / f"{tag}_{label}", label)
        s_sc, v_sc = pl["s_sc"], pl["v_sc"]
        elig = pl["s_ok"]
        print(f"[{label}] eligible (>= {MIN_TRADES} trades both coins in search): {elig.sum():,}; "
              f"best search score {np.nanmax(np.where(elig, s_sc, np.nan)):.2f}; "
              f"search score p99 {np.nanpercentile(np.where(elig, s_sc, np.nan), 99):.2f}; "
              f"top-1000 passing validation: {len(pl['cand'])}; neighbour-checked {len(pl['checked'])}, robust {len(pl['chosen'])}")
        report[label] = dict(U=U if label == "real" else None, res=res if label == "real" else None, pl=pl)

    # ---- holdout: real top 10 only, once ----
    R = report["real"]
    U = R["U"]  # real universe includes SOL
    res, pl = R["res"], R["pl"]
    elig = pl["s_ok"]
    sr_var = np.nanvar(np.where(elig, pl["s_sc"], np.nan) / np.sqrt(365))
    # The holdout is evaluated once: results are written immediately and reused (never recomputed) on any rerun.
    hfile = cache / "crypto_search" / f"{tag}_HOLDOUT.csv"
    if hfile.exists():
        print(f"holdout already evaluated once -> reusing {hfile.name} (not recomputed)")
        H = pd.read_csv(hfile)
    else:
        rows = []
        for rank, k in enumerate(pl["chosen"], 1):
            x = tuple(P[k])
            # DSR of the search-period Sharpe against all 100k trials (BTC/ETH 50/50 daily returns)
            sd = np.mean([period(U, x, s, 0, b1)[1] for s in syms], axis=0)
            dsr_search = dsr(sd, N_COMBOS, sr_var)
            for s in syms_all:
                st, daily = holdout(U, x, s, bounds)
                rows.append({"rank": rank, "strategy": describe(x), "symbol": s,
                             "search sharpe": res[k, syms.index(s), 0, 3] if s in syms else np.nan,
                             "valid sharpe": res[k, syms.index(s), 1, 3] if s in syms else np.nan,
                             "H trades": st["trades"], "H win%": 100 * st["win"], "H exp%": 100 * st["exp"],
                             "H maxDD%": 100 * st["maxdd"], "H sharpe": st["sharpe"], "DSR search (N=100k)": dsr_search,
                             "DSR holdout (N=10)": dsr(daily, 10, sr_var)})
        H = pd.DataFrame(rows, columns=["rank", "strategy", "symbol", "search sharpe", "valid sharpe", "H trades", "H win%",
                                        "H exp%", "H maxDD%", "H sharpe", "DSR search (N=100k)", "DSR holdout (N=10)"])
        H.to_csv(hfile, index=False)

    # ---- references on the holdout: buy & hold and TSMOM 28d (daily bars from the same 1h data) ----
    refs = []
    for s in syms_all:
        dd = resample(h1[s], "1D")
        hstart = start + pd.Timedelta(days=b2)
        bh = dd["c"].pct_change().fillna(0)
        bh = bh[bh.index >= hstart]
        eq = (1 + bh).cumprod()
        _, tsd, held = simulate(dd, tsmom(dd), SIDE, "next_open")
        x = tsd[tsd.index >= hstart]
        ex = (1 + x).cumprod()
        ntr = int(((held.diff() != 0) & (held != 0) & (held.index >= hstart)).sum())
        refs.append({"symbol": s, "B&H sharpe": bh.mean() / bh.std() * np.sqrt(365), "B&H maxDD%": 100 * (eq / eq.cummax() - 1).min(),
                     "B&H return%": 100 * (eq.iloc[-1] - 1), "TSMOM28 trades": ntr,
                     "TSMOM28 sharpe": x.mean() / x.std() * np.sqrt(365), "TSMOM28 maxDD%": 100 * (ex / ex.cummax() - 1).min(),
                     "TSMOM28 return%": 100 * (ex.iloc[-1] - 1)})
    REF = pd.DataFrame(refs)

    # ---- verdicts ----
    V = []
    for rank, g in H.groupby("rank"):
        be = g[g["symbol"].isin(syms)]
        ok_t = (be["H trades"] >= MIN_TRADES).all()
        ok_p = ((be["H sharpe"] > 0) & (be["H exp%"] > 0)).all()
        beats = all(r["H sharpe"] > REF.set_index("symbol").loc[r["symbol"], "TSMOM28 sharpe"] and
                    r["H sharpe"] > REF.set_index("symbol").loc[r["symbol"], "B&H sharpe"] for _, r in be.iterrows())
        sig = (be["DSR holdout (N=10)"] >= 0.95).all()
        v = ("REJECT: < 30 holdout trades" if not ok_t else "REJECT: holdout loses on BTC or ETH" if not ok_p else
             ("SURVIVES: positive, beats B&H and TSMOM28, DSR >= 0.95" if beats and sig else
              "WEAK: positive on BTC+ETH but " + ("not significant (DSR < 0.95)" if beats else "does not beat B&H/TSMOM28")))
        V.append({"rank": rank, "strategy": g["strategy"].iloc[0], "verdict": v})
    V = pd.DataFrame(V, columns=["rank", "strategy", "verdict"])

    # ---- luck benchmark summary ----
    L = []
    for label in report:
        p = report[label]["pl"]
        e = p["s_ok"]
        topv = sorted([p["v_sc"][k] for k in p["chosen"]], reverse=True)
        L.append({"data": label, "eligible combos": int(e.sum()), "best search score": np.nanmax(np.where(e, p["s_sc"], np.nan)),
                  "search p99": np.nanpercentile(np.where(e, p["s_sc"], np.nan), 99),
                  "top-1000 pass validation": len(p["cand"]), "robust found": len(p["chosen"]),
                  "median valid score of top 10": np.median(topv) if topv else np.nan,
                  "best valid score": topv[0] if topv else np.nan})
    L = pd.DataFrame(L)
    sh = L[L["data"] != "real"]
    real = L[L["data"] == "real"].iloc[0]
    LS = pd.DataFrame([{"metric": m, "real": real[m], "shuffled mean": sh[m].mean(), "shuffled max": sh[m].max(),
                        "share of shuffles >= real": (sh[m] >= real[m]).mean()}
                       for m in ("best search score", "search p99", "top-1000 pass validation", "robust found",
                                 "median valid score of top 10", "best valid score")])
    # search-score DSR of the 100k-search winner(s) (search period, BTC/ETH mean daily returns)
    NB = pd.DataFrame([{"rank": i + 1, "strategy": describe(tuple(P[k])), "neighbours ok": f"{g}/{n}", "robust": ok}
                       for i, (k, g, n, ok) in enumerate(R["pl"]["checked"])])

    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 30)
    pd.set_option("display.max_colwidth", 90)
    print("\n== Luck benchmark (same 100k combos, same pipeline)\n", LS.round(3).to_string(index=False))
    print(f"\n== Neighbour checks (validation-ranked candidates, in order): {len(NB)} checked, {int(NB['robust'].sum()) if len(NB) else 0} robust")
    print("\n== Holdout (once), top 10 robust\n", H.round(2).to_string(index=False))
    print("\n== Holdout references\n", REF.round(2).to_string(index=False))
    print("\n== Verdicts\n", V.to_string(index=False))
    if a.out:
        def md(df):
            r = df.round(2).astype(object).where(df.notna(), "")
            cols = list(df.columns)
            return "\n".join(["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)] + ["| " + " | ".join(str(v) for v in x) + " |" for x in r.values])
        Path(a.out).write_text("\n\n".join([
            f"Split: search 2021-01-01 -> {day(b1 - 1)}, validate -> {day(b2 - 1)}, holdout {day(b2)} -> {end.date()}. "
            f"Space {space:,}; drawn {N_COMBOS:,}; cost 0.60% round trip.",
            "### Verdicts\n\n" + md(V), "### Holdout, top 10 robust (BTC, ETH; SOL separately)\n\n" + md(H),
            "### Holdout references\n\n" + md(REF), "### Luck benchmark summary\n\n" + md(LS), "### Luck benchmark per run\n\n" + md(L), "### Neighbour checks\n\n" + md(NB)]) + "\n")
        json.dump({"chosen": [describe(tuple(P[k])) for k in pl["chosen"]]}, open(Path(a.out).with_suffix(".json"), "w"), indent=1)


if __name__ == "__main__":
    main()
