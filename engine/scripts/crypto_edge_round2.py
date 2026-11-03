"""Round 2: wider crypto strategy search on BTC/ETH/SOL with a locked holdout.

Daily: 13 families (published, practitioner and own designs), small pre-declared parameter grids.
  Design (tuning) window 2021-01-01 .. 2024-06-30; one variant per family is chosen by mean design Sharpe across the
  three coins (same parameters for every coin), then run ONCE on the holdout 2024-07-01 .. last completed day.
Intraday: 7 strategies with standard / live parameters (no tuning) on the last 60 days of 1h bars (4h built from 1h),
  including the paper runner's live crypto legs, using backtestceo.paper.strategies itself.
Costs: 0.25% Alpaca taker + 0.05% slippage per side. Fills: next bar open. Reject < 30 trades.

Run: python engine/scripts/crypto_edge_round2.py --out docs/crypto-edge-round2-tables.md
"""
import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import NormalDist

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
from crypto_edge_backtest import SYMS, fetch, segments  # noqa: E402
from backtestceo.paper.strategies import SIGNALS, replay_bars, resample  # noqa: E402

MIN_TRADES = 30
DESIGN_END = pd.Timestamp("2024-07-01", tz="UTC")
N01 = NormalDist()


# ---------------- indicators ----------------
def rsi(c, n):
    d = c.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn)


def atr(d, n):
    pc = d["c"].shift()
    tr = pd.concat([d["h"] - d["l"], (d["h"] - pc).abs(), (d["l"] - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean()


def _state(enter, exit_, n_max=None):
    """Long/flat state machine on boolean arrays evaluated at each close."""
    pos, cur, held = np.zeros(len(enter)), 0, 0
    for i in range(len(enter)):
        if cur == 0 and enter[i]:
            cur, held = 1, 0
        elif cur == 1:
            held += 1
            if exit_[i] or (n_max and held >= n_max):
                cur = 0
        pos[i] = cur
    return pos


# ---------------- daily signal families (1 = long, 0 = flat) ----------------
def f_tsmom(d, L):
    return (d["c"].pct_change(L) > 0).astype(float)


def f_vote(d, k):
    return (sum((d["c"].pct_change(L) > 0).astype(int) for L in (10, 20, 40, 60, 90)) >= k).astype(float)


def f_donch_ens(d, thr):
    votes = []
    for n in (10, 20, 30, 60, 90, 150):
        hi = d["h"].rolling(n).max().shift(1)
        lo = d["l"].rolling(n).min().shift(1)
        votes.append(_state((d["c"] > hi).values, (d["c"] < (hi + lo) / 2).values))
    return pd.Series((np.mean(votes, axis=0) >= thr).astype(float), d.index)


def f_sma(d, N):
    return (d["c"] > d["c"].rolling(N).mean()).astype(float)


def f_cross(d, fs):
    f, s = fs
    return (d["c"].rolling(f).mean() > d["c"].rolling(s).mean()).astype(float)


def _vol_ok(d, q):
    v = d["c"].pct_change().rolling(20).std()
    return v < v.rolling(365, min_periods=180).quantile(q)


def f_volregime(d, q):
    return _vol_ok(d, q).astype(float)


def f_rsi2(d, thr):
    c = d["c"]
    return pd.Series(_state(((c > c.rolling(200).mean()) & (rsi(c, 2) < thr)).values,
                            (c > c.rolling(5).mean()).values), d.index)


def f_tsmom_vol(d, Lq):
    L, q = Lq
    return ((d["c"].pct_change(L) > 0) & _vol_ok(d, q)).astype(float)


def f_trend_dip(d, thr):
    c, r3 = d["c"], rsi(d["c"], 3)
    return pd.Series(_state(((c > c.rolling(100).mean()) & (r3 < thr)).values, (r3 > 70).values, n_max=10), d.index)


def f_weekly_tsmom(d, L):
    s = (d["c"].pct_change(L) > 0).astype(float)
    return s.where(s.index.dayofweek == 0).ffill().fillna(0)


def f_tsmom_trail(d, m):
    c = d["c"].values
    base = (d["c"].pct_change(28) > 0).values
    a = atr(d, 20).values
    pos, cur, armed, peak = np.zeros(len(c)), 0, True, 0.0
    for i in range(len(c)):
        if not base[i]:
            armed = True
            cur = 0
        elif cur == 0 and armed:
            cur, peak = 1, c[i]
        elif cur == 1:
            peak = max(peak, c[i])
            if c[i] < peak - m * a[i]:
                cur, armed = 0, False
        pos[i] = cur
    return pd.Series(pos, d.index)


def make_btc_gate(btc):
    def f_btc_gate(d, N):
        g = (btc["c"] > btc["c"].rolling(N).mean()).astype(float)
        return g.reindex(d.index).fillna(0)
    return f_btc_gate


# family: (label, kind, source, fn, grid)
def families(btc):
    return [
        ("TSMOM", "published", "Liu & Tsyvinski 2021 (RFS)", f_tsmom, [14, 28, 56, 90]),
        ("TSMOM vote 10-90d", "published", "Moskowitz-Ooi-Pedersen style multi-lookback; arXiv 2009.12155", f_vote, [3, 4, 5]),
        ("Donchian ensemble", "published", "Zarattini, Pagani & Barbon 2025 (SFI 25-80), simplified", f_donch_ens, [0.34, 0.5, 0.67]),
        ("Price > SMA", "practitioner", "200-day MA rule (Faber-style), common BTC filter", f_sma, [50, 100, 150, 200]),
        ("SMA cross", "practitioner", "golden-cross family", f_cross, [(10, 30), (20, 50), (50, 100), (50, 200)]),
        ("Low-vol regime", "published", "Moreira & Muir 2017 (JF) vol-managed, binary", f_volregime, [0.5, 0.7, 0.9]),
        ("RSI(2) pullback", "practitioner", "Connors RSI(2), SMA200 filter, exit > SMA5", f_rsi2, [5, 10, 15]),
        ("BTC-trend gate", "own", "hold coin only while BTC > its SMA", make_btc_gate(btc), [50, 100, 200]),
        ("TSMOM + low vol", "own", "TSMOM and 20d vol below its 1y quantile", f_tsmom_vol, [(28, 0.7), (28, 0.9), (56, 0.7), (56, 0.9)]),
        ("Trend dip-buy", "own", "close > SMA100 and RSI(3) < x; exit RSI(3) > 70 or 10 days", f_trend_dip, [20, 30]),
        ("Weekly TSMOM", "own", "TSMOM checked Mondays only (less whipsaw)", f_weekly_tsmom, [28, 56]),
        ("TSMOM + ATR trail", "own", "TSMOM 28d with m x ATR20 trailing stop", f_tsmom_trail, [2, 3, 4]),
    ]


# ---------------- simulation ----------------
def sim(d, sig, side):
    """Signal at close i -> fill at open i+1. Returns (trades [(entry_ts, net ret)], daily returns)."""
    o, c = d["o"].values, d["c"].values
    s = np.nan_to_num(np.asarray(sig, float))
    tgt = np.r_[0.0, s[:-1]]
    E, u, mark, cur, entry, ets = 1.0, 0.0, c[0], 0.0, None, None
    eq, trades = np.empty(len(c)), []
    for j in range(len(c)):
        if tgt[j] != cur:
            px = o[j]
            E += u * (px - mark)
            mark = px
            if cur != 0:
                trades.append((ets, cur * (px / entry - 1) - 2 * side))
            nu = tgt[j] * E / px
            E -= abs(nu - u) * px * side
            u, cur, entry, ets = nu, tgt[j], px, d.index[j]
        E += u * (c[j] - mark)
        mark = c[j]
        eq[j] = E
    if cur != 0:
        trades.append((ets, cur * (c[-1] / entry - 1) - 2 * side))
    daily = pd.Series(eq, d.index).pct_change().fillna(0)
    return trades, daily


def run_family(d, fn, p, side):
    tr, dl = [], []
    for seg in segments(d):
        t, daily = sim(seg, fn(seg, p), side)
        daily.iloc[0] = 0.0
        tr += t
        dl.append(daily)
    return tr, pd.concat(dl)


def window(trades, daily, start, end):
    t = [r for ts, r in trades if start <= ts < end]
    x = daily[(daily.index >= start) & (daily.index < end)].copy()
    if len(x):
        x.iloc[0] = 0.0
    return t, x


def metrics(t, x):
    t = np.asarray(t, float)
    eq = (1 + x).cumprod()
    sd = x.std()
    return {"trades": len(t), "win%": 100 * (t > 0).mean() if len(t) else np.nan,
            "exp%": 100 * t.mean() if len(t) else np.nan, "maxDD%": 100 * (eq / eq.cummax() - 1).min(),
            "sharpe": x.mean() / sd * np.sqrt(365) if sd > 0 else np.nan,
            "CAGR%": 100 * (eq.iloc[-1] ** (365.25 / len(x)) - 1) if len(x) else np.nan}


def dsr(x, n_trials, sr_var):
    """Deflated Sharpe ratio (Bailey & Lopez de Prado 2014), per-period units. P(true SR > best-of-N noise)."""
    x = np.asarray(x)
    x = x[np.isfinite(x)]
    T = len(x)
    if T < 30 or x.std() == 0:
        return np.nan
    sr = x.mean() / x.std()
    g = 0.5772156649
    sr0 = np.sqrt(sr_var) * ((1 - g) * N01.inv_cdf(1 - 1 / n_trials) + g * N01.inv_cdf(1 - 1 / (n_trials * np.e))) if n_trials > 1 else 0.0
    sk, ku = pd.Series(x).skew(), pd.Series(x).kurt() + 3
    den = np.sqrt(max(1 - sk * sr + (ku - 1) / 4 * sr ** 2, 1e-12))
    return N01.cdf((sr - sr0) * np.sqrt(T - 1) / den)


def boot_diff(a, b, reps=2000, block=20, seed=11):
    a, b = np.asarray(a), np.asarray(b)
    n = len(a)
    rng = np.random.default_rng(seed)
    k = int(np.ceil(n / block))
    out = np.empty(reps)
    for i in range(reps):
        idx = (rng.integers(0, n, k)[:, None] + np.arange(block)).ravel()[:n] % n
        x, y = a[idx], b[idx]
        out[i] = (x.mean() / x.std() - y.mean() / y.std()) * np.sqrt(365)
    return np.percentile(out, 2.5), np.percentile(out, 97.5)


# ---------------- rotation (dual momentum across BTC/ETH/SOL) ----------------
def rotation(data, L, side):
    """Weekly (Monday close) pick the coin with the best L-day return if > 0, else cash. Fill next open.
    A coin with no bar that day (SOL hole) is ineligible; if held into a hole it is sold at its last close."""
    idx = data["BTC/USD"].index
    C = pd.DataFrame({s: d["c"] for s, d in data.items()}).reindex(idx)
    O = pd.DataFrame({s: d["o"] for s, d in data.items()}).reindex(idx)
    mom = C.pct_change(L, fill_method=None)
    pick = [None] * len(idx)
    cur = None
    for i, t in enumerate(idx):
        if t.dayofweek == 0:
            m = mom.loc[t].dropna()
            cur = m.idxmax() if len(m) and m.max() > 0 else None
        pick[i] = cur
    E, held, units, entry, ets, mark = 1.0, None, 0.0, None, None, None
    eq, trades = np.empty(len(idx)), []
    for j, t in enumerate(idx):
        want = pick[j - 1] if j else None
        if held is not None and np.isnan(C.iloc[j][held]):   # held coin has no bar: exit at last mark
            trades.append((ets, mark / entry - 1 - 2 * side))
            E -= units * mark * side
            held, units = None, 0.0
        if want is not None and np.isnan(O.iloc[j][want]):
            want = None
        if want != held:
            if held is not None:
                px = O.iloc[j][held]
                E += units * (px - mark)
                trades.append((ets, px / entry - 1 - 2 * side))
                E -= units * px * side
                held, units = None, 0.0
            if want is not None:
                px = O.iloc[j][want]
                E -= E * side
                units, held, entry, ets, mark = E / px, want, px, t, px
        if held is not None:
            c = C.iloc[j][held]
            E += units * (c - mark)
            mark = c
        eq[j] = E
    if held is not None:
        trades.append((ets, mark / entry - 1 - 2 * side))
    return trades, pd.Series(eq, idx).pct_change().fillna(0)


# ---------------- intraday ----------------
def to_bars(df):
    return [dict(ts=t.to_pydatetime(), o=r.o, h=r.h, l=r.l, c=r.c, v=r.v) for t, r in df.iterrows()]


def sig_rsi2_1h(bars):
    c = pd.Series([b["c"] for b in bars])
    e = c.ewm(span=200, adjust=False).mean()
    r = rsi(c, 2)
    s5 = c.rolling(5).mean()
    n = len(c)
    return dict(le=list((c > e) & (r < 10)), lx=list(c > s5), se=[False] * n, sx=[False] * n, stop_pct=None)


def sig_bb_1h(bars):
    c = pd.Series([b["c"] for b in bars])
    m, sd = c.rolling(20).mean(), c.rolling(20).std()
    n = len(c)
    return dict(le=list(c < m - 2 * sd), lx=list(c > m), se=[False] * n, sx=[False] * n, stop_pct=None)


def sig_donch_4h(bars):
    df = pd.DataFrame(bars)
    hi, lo = df["h"].rolling(20).max().shift(1), df["l"].rolling(10).min().shift(1)
    n = len(df)
    return dict(le=list(df["c"] > hi), lx=list(df["c"] < lo), se=[False] * n, sx=[False] * n, stop_pct=None)


def grid_trades(bars, g=0.02):
    """Single-slot grid bot: buy when price falls g below the last exit (anchor), sell g above entry. Limit fills."""
    trades, anchor, entry, ets = [], bars[0]["c"], None, None
    for b in bars:
        if entry is None and b["l"] <= anchor * (1 - g):
            entry, ets = min(anchor * (1 - g), b["o"]), b["ts"]
        elif entry is not None and b["h"] >= entry * (1 + g):
            px = max(entry * (1 + g), b["o"])
            trades.append(dict(entry_time=ets, exit_time=b["ts"], side="long", entry=entry, exit=px))
            entry, anchor = None, px
        if entry is None and b["c"] > anchor:
            anchor = b["c"]  # trail the anchor up while flat
    if entry is not None:
        trades.append(dict(entry_time=ets, exit_time=bars[-1]["ts"], side="long", entry=entry, exit=bars[-1]["c"]))
    return trades


def trade_daily(trades, bars, side, start):
    """Mark-to-market daily returns from a trade list (full-size, one position at a time)."""
    closes = pd.Series([b["c"] for b in bars], index=pd.DatetimeIndex([b["ts"] for b in bars]))
    r = pd.Series(0.0, index=closes.index)
    for t in trades:
        sgn = 1 if t["side"] == "long" else -1
        path = closes[(closes.index >= t["entry_time"]) & (closes.index < t["exit_time"])]
        prices = np.r_[t["entry"], path.values, t["exit"]]
        stamps = list(path.index) + [t["exit_time"]]
        rets = sgn * (prices[1:] / prices[:-1] - 1)
        for ts, x in zip(stamps, rets):
            if ts in r.index:
                r[ts] = (1 + r[ts]) * (1 + x) - 1
        r[path.index[0] if len(path) else t["exit_time"]] -= side
        if t["exit_time"] in r.index:
            r[t["exit_time"]] -= side
    r = r[r.index >= start]
    return (1 + r).groupby(r.index.normalize()).prod() - 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fee", type=float, default=0.0025)
    ap.add_argument("--slip", type=float, default=0.0005)
    ap.add_argument("--cache", default=str(HERE.parent / ".cache" / "crypto_edge"))
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    side = a.fee + a.slip
    cache = Path(a.cache)
    cache.mkdir(parents=True, exist_ok=True)
    end = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(seconds=1)
    d0 = datetime(2021, 1, 1, tzinfo=timezone.utc)
    START, END = pd.Timestamp(d0), pd.Timestamp(end) + pd.Timedelta(seconds=1)
    data = {s: fetch(s, "1Day", d0, end, cache) for s in SYMS}
    fams = families(data["BTC/USD"])

    # ---- design grid: every variant x coin ----
    grid_rows, runs = [], {}
    for name, kind, src, fn, grid in fams:
        for p in grid:
            for s in SYMS:
                tr, daily = run_family(data[s], fn, p, side)
                runs[(name, str(p), s)] = (tr, daily)
                m = metrics(*window(tr, daily, START, DESIGN_END))
                grid_rows.append({"family": name, "param": str(p), "symbol": s, **m})
    for L in (14, 28, 56):
        tr, daily = rotation(data, L, side)
        runs[("Dual-momentum rotation", str(L), "BTC/ETH/SOL")] = (tr, daily)
        grid_rows.append({"family": "Dual-momentum rotation", "param": str(L), "symbol": "BTC/ETH/SOL",
                          **metrics(*window(tr, daily, START, DESIGN_END))})
    G = pd.DataFrame(grid_rows)
    n_trials = G.groupby(["family", "param"]).ngroups
    # variance of per-period design Sharpe across all variant x coin trials (for DSR)
    sr_var = (G["sharpe"] / np.sqrt(365)).var()

    # ---- pick one variant per family by mean design Sharpe across coins ----
    pick = G.groupby(["family", "param"])["sharpe"].mean().reset_index().sort_values("sharpe", ascending=False)
    chosen = pick.drop_duplicates("family").set_index("family")["param"]

    bh = {s: pd.concat([seg["c"].pct_change().fillna(0) for seg in segments(d)]) for s, d in data.items()}
    rows, verdict = [], []
    fam_meta = {f[0]: f for f in fams}
    fam_meta["Dual-momentum rotation"] = ("Dual-momentum rotation", "practitioner", "Antonacci dual momentum across BTC/ETH/SOL", None, [14, 28, 56])
    for fam, p in chosen.items():
        syms = ["BTC/ETH/SOL"] if fam == "Dual-momentum rotation" else SYMS
        per_coin = []
        for s in syms:
            tr, daily = runs[(fam, p, s)]
            full = metrics(*window(tr, daily, START, END))
            des = metrics(*window(tr, daily, START, DESIGN_END))
            ht, hx = window(tr, daily, DESIGN_END, END)
            hold = metrics(ht, hx)
            if s in bh:
                b = bh[s][(bh[s].index >= DESIGN_END)].copy()
                b.iloc[0] = 0
                bm = metrics([], b)
            else:  # rotation: equal-weight B&H of the three (rebalanced daily) as reference
                b = pd.concat([bh[x] for x in SYMS], axis=1).reindex(hx.index).mean(axis=1, skipna=True).fillna(0)
                bm = metrics([], b)
            b = b.reindex(hx.index).fillna(0)
            lo, hi = boot_diff(hx.values, b.values)
            per_coin.append(dict(full=full, hold=hold, bh=bm, ok_trades=full["trades"] >= MIN_TRADES,
                                 pos=(hold["sharpe"] > 0) and (hold["exp%"] > 0),
                                 beats=hold["sharpe"] > bm["sharpe"], dd_better=hold["maxDD%"] - bm["maxDD%"]))
            rows.append({"family": fam, "kind": fam_meta[fam][1], "param": p, "symbol": s,
                         "design sharpe": des["sharpe"],
                         **{f"H {k}": v for k, v in hold.items()},
                         "B&H H sharpe": bm["sharpe"], "B&H H maxDD%": bm["maxDD%"],
                         "dSharpe CI": f"[{lo:.2f}, {hi:.2f}]", "full trades": full["trades"],
                         "DSR(holdout)": dsr(hx.values, len(chosen), sr_var)})
        need = 1 if len(syms) == 1 else 2
        trades_ok = all(c["ok_trades"] for c in per_coin)
        n_pos = sum(c["pos"] for c in per_coin)
        n_beat = sum(c["beats"] and c["pos"] for c in per_coin)
        n_dd = sum(c["pos"] and c["dd_better"] >= 15 for c in per_coin)
        if not trades_ok:
            v = f"REJECT: < {MIN_TRADES} trades on " + ", ".join(s for s, c in zip(syms, per_coin) if not c["ok_trades"])
        elif n_pos < need:
            v = f"REJECT: holdout Sharpe/expectancy > 0 on only {n_pos}/{len(syms)}"
        elif n_beat >= need:
            v = f"SURVIVES (edge): beats B&H holdout Sharpe on {n_beat}/{len(syms)}"
        elif n_dd >= need:
            v = f"SURVIVES (overlay): positive and DD >= 15 pts better on {n_dd}/{len(syms)}"
        else:
            v = "REJECT: positive but neither beats B&H nor cuts DD 15 pts"
        verdict.append({"family": fam, "kind": fam_meta[fam][1], "chosen param": p, "source": fam_meta[fam][2], "verdict": v})

    # ---- intraday (no tuning) ----
    i_end = pd.Timestamp(end)
    i_start = (i_end + pd.Timedelta(seconds=1)) - pd.Timedelta(days=60)
    warm = datetime.fromtimestamp(i_start.timestamp(), timezone.utc) - timedelta(days=110)
    intr = [("SuperTrend+EMA200+ADX 4h (live leg, L/S)", 4, lambda b: SIGNALS["supertrend"](b)),
            ("EMA200+ADX25 4h (live leg, L/S)", 4, lambda b: SIGNALS["alphainsider"](b)),
            ("EMA 9/21 1h + 2% stop (live leg, long)", 1, lambda b: SIGNALS["emacross"](b)),
            ("RSI(2) 1h, EMA200 filter (long)", 1, sig_rsi2_1h),
            ("Bollinger 20/2 1h reversion (long)", 1, sig_bb_1h),
            ("Donchian 20/10 4h breakout (long)", 4, sig_donch_4h),
            ("Grid bot single-slot 2% 1h (long)", 1, None)]
    irows = []
    for s in SYMS:
        h1 = fetch(s, "1Hour", warm, end, cache)
        bars1 = to_bars(h1)
        for name, tf, sfn in intr:
            bars = bars1 if tf == 1 else resample(bars1, 4)
            if sfn is None:
                tl = grid_trades([b for b in bars if b["ts"] >= i_start])
                stop_side = 0.0005 + 0.0015  # grid uses resting limit orders: Alpaca maker 0.15% + slip
            else:
                tl = replay_bars(bars, sfn(bars))
                stop_side = side
            tl = [t for t in tl if t["entry_time"] >= i_start]
            net = [((t["exit"] / t["entry"] - 1) if t["side"] == "long" else (1 - t["exit"] / t["entry"])) - 2 * stop_side for t in tl]
            daily = trade_daily(tl, [b for b in bars if b["ts"] >= i_start - timedelta(hours=4)], stop_side, i_start)
            m = metrics(net, daily)
            irows.append({"strategy": name, "symbol": s, "tf": f"{tf}h", **m,
                          "gross exp%": (m["exp%"] + 200 * stop_side) if len(net) else np.nan,
                          "status": "ok" if m["trades"] >= MIN_TRADES else f"REJECT (<{MIN_TRADES})"})
    I = pd.DataFrame(irows)
    ivs = []
    for name, g in I.groupby("strategy", sort=False):
        okt = (g["trades"] >= MIN_TRADES).all()
        npos = int(((g["exp%"] > 0) & (g["sharpe"] > 0)).sum())
        ivs.append({"strategy": name, "verdict": ("SURVIVES" if okt and npos >= 2 else
                    ("REJECT: < 30 trades on " + ", ".join(g.loc[g["trades"] < MIN_TRADES, "symbol"]) if not okt
                     else f"REJECT: net expectancy > 0 on only {npos}/3"))})

    R, V, IV = pd.DataFrame(rows), pd.DataFrame(verdict), pd.DataFrame(ivs)
    pd.set_option("display.width", 260)
    pd.set_option("display.max_columns", 40)
    pd.set_option("display.max_rows", 400)
    print(f"variants tried (daily): {n_trials}; intraday: {len(intr)}; cost/side {side:.2%}")
    print("\n== Design grid\n", G.round(2).to_string(index=False))
    print("\n== Chosen variants: holdout", DESIGN_END.date(), "->", end.date(), "\n", R.round(2).to_string(index=False))
    print("\n== Daily verdicts\n", V.to_string(index=False))
    print(f"\n== Intraday {i_start.date()} -> {end.date()}\n", I.round(2).to_string(index=False))
    print("\n== Intraday verdicts\n", IV.to_string(index=False))
    if a.out:
        def md(df):
            r = df.round(2).map(lambda v: "" if (isinstance(v, float) and np.isnan(v)) else str(v))
            cols = list(df.columns)
            return "\n".join(["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)] + ["| " + " | ".join(x) + " |" for x in r.values])
        Path(a.out).write_text("\n\n".join([
            f"cost/side {side:.2%}; daily variants tried {n_trials}; holdout {DESIGN_END.date()} -> {end.date()}; intraday {i_start.date()} -> {end.date()}",
            "### Daily verdicts\n\n" + md(V), "### Daily holdout results (chosen variant per family)\n\n" + md(R),
            "### Intraday verdicts\n\n" + md(IV), "### Intraday results (60 days)\n\n" + md(I),
            "### Design grid (2021-01-01 -> 2024-06-30, all variants)\n\n" + md(G)]) + "\n")


if __name__ == "__main__":
    main()
