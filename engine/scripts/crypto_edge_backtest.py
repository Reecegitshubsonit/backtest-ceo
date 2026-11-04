"""Five published crypto edges, backtested on BTC/ETH/SOL with Alpaca crypto bars and fees.

Daily strategies: 2021-01-01 .. yesterday (≈5.8 years). Intraday: last 60 days of 30-minute bars.
Run:  python engine/scripts/crypto_edge_backtest.py [--fee 0.0025] [--slip 0.0005] [--out docs/crypto-edge-results.md]
Needs network access to data.alpaca.markets (keys via ALPACA_API_KEY / ALPACA_SECRET_KEY or an auth proxy).
"""
import argparse
import json
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import requests

URL = "https://data.alpaca.markets/v1beta3/crypto/us/bars"
SYMS = ["BTC/USD", "ETH/USD", "SOL/USD"]
MIN_TRADES = 30


def fetch(sym, tf, start, end, cache):
    f = cache / f"{sym.replace('/', '')}_{tf}_{start:%Y%m%d}_{end:%Y%m%d}.json"
    if f.exists():
        rows = json.loads(f.read_text())
    else:
        h = {"APCA-API-KEY-ID": os.environ.get("ALPACA_API_KEY", "x"), "APCA-API-SECRET-KEY": os.environ.get("ALPACA_SECRET_KEY", "x")}
        rows, tok = [], None
        while True:
            p = {"symbols": sym, "timeframe": tf, "start": start.isoformat(), "end": end.isoformat(), "limit": 10000}
            if tok:
                p["page_token"] = tok
            for a in range(10):  # Alpaca rate-limits at ~200 req/min: back off on 429, honour Retry-After
                r = requests.get(URL, params=p, headers=h, timeout=30)
                if r.status_code == 200:
                    break
                time.sleep(float(r.headers.get("Retry-After") or min(60, 2 ** a)))
            r.raise_for_status()
            time.sleep(0.35)
            j = r.json()
            rows += j["bars"].get(sym, [])
            tok = j.get("next_page_token")
            if not tok:
                break
        f.write_text(json.dumps(rows))
    df = pd.DataFrame(rows)
    df["t"] = pd.to_datetime(df["t"], utc=True)
    return df.set_index("t")[["o", "h", "l", "c", "v"]].astype(float).sort_index()


# ---------- metrics ----------
def metrics(trades, daily, cost):
    """trades: net per-trade returns; daily: net daily strategy returns (zeros when flat)."""
    t = np.asarray(trades, float)
    eq = (1 + daily).cumprod()
    dd = (eq / eq.cummax() - 1).min()
    sd = daily.std()
    return {
        "trades": len(t),
        "win%": 100 * (t > 0).mean() if len(t) else np.nan,
        "exp%": 100 * t.mean() if len(t) else np.nan,
        "gross_exp%": 100 * (t + cost).mean() if len(t) else np.nan,
        "maxDD%": 100 * dd,
        "sharpe": daily.mean() / sd * np.sqrt(365) if sd > 0 else np.nan,
        "total%": 100 * (eq.iloc[-1] - 1),
    }


def simulate(d, sig, side_cost, fill="next_open", rf=None):
    """Event simulation of a daily signal. sig[i] is computed from bar i (uses its close).
    fill: "next_open"  -> trade at the open of bar i+1 (default, realistic)
          "next_close" -> trade at the close of bar i+1 (one full bar of lag, stress test)
          "same_close" -> trade at the close of bar i (look-ahead-ish: the signal bar's own close)
    rf: optional daily cash return series (index = d.index) earned on idle equity when flat.
    Returns (trade returns, daily equity returns, held position per bar)."""
    o, c = d["o"].values, d["c"].values
    s = np.nan_to_num(np.asarray(sig, float))
    n = len(c)
    tgt = np.zeros(n)  # target applied at bar j's fill
    if fill == "same_close":
        tgt[:] = s
    else:
        tgt[1:] = s[:-1]
    at_open = fill == "next_open"
    r_cash = np.zeros(n) if rf is None else rf.reindex(d.index).ffill().fillna(0).values
    E, u, mark = 1.0, 0.0, c[0]
    eq, held, trades = np.empty(n), np.empty(n), []
    cur, entry = 0.0, None
    for j in range(n):
        if u == 0:
            E *= 1 + r_cash[j]
        px = o[j] if at_open else c[j]
        if tgt[j] != cur:
            E += u * (px - mark)
            mark = px
            if cur != 0:
                trades.append(cur * (px / entry - 1) - 2 * side_cost)
            new_u = tgt[j] * E / px
            E -= abs(new_u - u) * px * side_cost
            u, cur, entry = new_u, tgt[j], px
        E += u * (c[j] - mark)
        mark = c[j]
        eq[j], held[j] = E, cur
    if cur != 0:
        trades.append(cur * (c[-1] / entry - 1) - 2 * side_cost)
    daily = pd.Series(eq, d.index).pct_change().fillna(0)
    return trades, daily, pd.Series(held, d.index)


def trades_in(d, held, side_cost, start, at_open=True):
    """Net trade returns for trades whose entry falls on/after start (for sub-period tables)."""
    o, c = d["o"], d["c"]
    px = o if at_open else c
    out, cur, entry = [], 0.0, None
    for t, h in held.items():
        if h != cur:
            if cur != 0 and entry is not None:
                out.append(cur * (px[t] / entry - 1) - 2 * side_cost)
            cur, entry = h, (px[t] if t >= start else None)
    if cur != 0 and entry is not None:
        out.append(cur * (c.iloc[-1] / entry - 1) - 2 * side_cost)
    return out


def cagr(daily):
    eq = (1 + daily).prod()
    yrs = len(daily) / 365.25  # bar count, so a data hole is not counted as elapsed time
    return 100 * (eq ** (1 / yrs) - 1)


def sharpe(x):
    return x.mean() / x.std() * np.sqrt(365) if x.std() > 0 else np.nan


def boot_sharpe_diff(a, b, reps=5000, block=20, seed=7):
    """Paired circular block bootstrap of Sharpe(a) - Sharpe(b). Returns (point, lo95, hi95, P(diff<=0))."""
    a, b = np.asarray(a), np.asarray(b)
    n = len(a)
    rng = np.random.default_rng(seed)
    k = int(np.ceil(n / block))
    out = np.empty(reps)
    for i in range(reps):
        idx = (rng.integers(0, n, k)[:, None] + np.arange(block)).ravel()[:n] % n
        x, y = a[idx], b[idx]
        out[i] = x.mean() / x.std() * np.sqrt(365) - y.mean() / y.std() * np.sqrt(365)
    pt = sharpe(pd.Series(a)) - sharpe(pd.Series(b))
    return pt, np.percentile(out, 2.5), np.percentile(out, 97.5), (out <= 0).mean()


def tbill_daily(cache, start, end):
    """Daily T-bill cash return from Alpaca dividend-adjusted BIL (+0.1355%/y expense ratio added back),
    smoothed over 63 trading days, spread over calendar days."""
    f = cache / f"BIL_adj_{start:%Y%m%d}_{end:%Y%m%d}.json"
    if f.exists():
        rows = json.loads(f.read_text())
    else:
        rows, tok = [], None
        while True:
            p = {"symbols": "BIL", "timeframe": "1Day", "start": (start - timedelta(days=120)).isoformat(),
                 "end": end.isoformat(), "adjustment": "all", "feed": "sip", "limit": 10000}
            if tok:
                p["page_token"] = tok
            j = requests.get("https://data.alpaca.markets/v2/stocks/bars", params=p, timeout=30,
                             headers={"APCA-API-KEY-ID": os.environ.get("ALPACA_API_KEY", "x"),
                                      "APCA-API-SECRET-KEY": os.environ.get("ALPACA_SECRET_KEY", "x")}).json()
            rows += j["bars"]["BIL"]
            tok = j.get("next_page_token")
            if not tok:
                break
        f.write_text(json.dumps(rows))
    b = pd.Series({pd.Timestamp(r["t"]).normalize(): r["c"] for r in rows}).sort_index()
    b.index = b.index.tz_convert("UTC").normalize()
    days = (b.index.to_series().diff(63).dt.days).values
    ann = (b / b.shift(63)) ** (365.25 / days) - 1 + 0.001355
    cal = pd.date_range(b.index[0], end.replace(hour=0, minute=0, second=0), freq="D", tz="UTC")
    ann = ann.reindex(cal).ffill()
    return ((1 + ann) ** (1 / 365.25) - 1).fillna(0), ann


# ---------- daily strategies ----------
def tsmom(d, lb=28):
    """Liu & Tsyvinski (2021): crypto time-series momentum. Long while trailing lb-day return > 0, else flat."""
    return (d["c"].pct_change(lb) > 0).astype(float)


def donchian(d, n_in=20, n_out=10):
    """Zarattini, Pagani & Barbon (2025) / Hudson & Urquhart (2021): long-only breakout. Enter on close above prior
    n_in-day high, exit on close below prior n_out-day low."""
    hi = d["h"].rolling(n_in).max().shift(1)
    lo = d["l"].rolling(n_out).min().shift(1)
    pos, cur = [], 0.0
    for c, h, l in zip(d["c"], hi, lo):
        if cur == 0 and c > h:
            cur = 1.0
        elif cur == 1 and c < l:
            cur = 0.0
        pos.append(cur)
    return pd.Series(pos, d.index)


def abnormal_day(d, win=30, k=1.0):
    """Caporale & Plastun (2020): after a one-day abnormal return (|r - mean| > k·sd over prior win days),
    trade in the same direction the next day (long/short, short needs a perp or margin)."""
    r = d["c"].pct_change()
    m, s = r.rolling(win).mean().shift(1), r.rolling(win).std().shift(1)
    return pd.Series(np.where(r > m + k * s, 1.0, np.where(r < m - k * s, -1.0, 0.0)), d.index)


# ---------- intraday strategies (30m bars, UTC days) ----------
def intraday(df, side_cost, kind):
    trades, days = [], {}
    for day, g in df.groupby(df.index.date):
        g = g.copy()
        g["hhmm"] = g.index.strftime("%H:%M")
        b = g.set_index("hhmm")
        if kind == "ihm":
            # Shen, Urquhart & Wang (2022): first half-hour return predicts last half-hour return (sign trade).
            if not {"00:00", "23:30"} <= set(b.index):
                continue
            sig = np.sign(b.loc["00:00", "c"] / b.loc["00:00", "o"] - 1)
            if sig == 0:
                continue
            r = sig * (b.loc["23:30", "c"] / b.loc["23:30", "o"] - 1)
        else:
            # Quantpedia (2022/23) Bitcoin intraday seasonality: long 21:00 -> 23:00 UTC.
            if not {"21:00", "22:30"} <= set(b.index):
                continue
            r = b.loc["22:30", "c"] / b.loc["21:00", "o"] - 1
        net = r - 2 * side_cost
        trades.append(net)
        days[pd.Timestamp(day)] = net
    idx = pd.date_range(df.index[0].normalize().tz_localize(None), df.index[-1].normalize().tz_localize(None), freq="D")
    daily = pd.Series(days, dtype=float).reindex(idx).fillna(0)
    return trades, daily


def segments(d, max_gap_days=5, min_len=60):
    """Split a daily series at holes > max_gap_days (Alpaca SOL/USD has a 417-day hole 2023-06 -> 2024-08).
    Strategies run per segment; the return across a hole is never booked."""
    cut = np.flatnonzero(d.index.to_series().diff().dt.days.values > max_gap_days)
    parts = np.split(np.arange(len(d)), cut)
    return [d.iloc[p] for p in parts if len(p) >= min_len]


def seg_run(d, sig_fn, side_cost, fill="next_open", rf=None):
    tr, dl, hl = [], [], []
    for seg in segments(d):
        t, daily, held = simulate(seg, sig_fn(seg), side_cost, fill, rf)
        daily.iloc[0] = 0.0
        tr += t
        dl.append(daily)
        hl.append(held)
    return tr, pd.concat(dl), pd.concat(hl)


def seg_trades_in(d, held, side_cost, start):
    out = []
    for seg in segments(d):
        out += trades_in(seg, held.reindex(seg.index), side_cost, start)
    return out


def seg_bh(d):
    return pd.concat([seg["c"].pct_change().fillna(0) for seg in segments(d)])


def md_table(df):
    r = df.round(2).map(lambda v: "" if (isinstance(v, float) and np.isnan(v)) else str(v))
    cols = list(df.columns)
    return "\n".join(["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)] + ["| " + " | ".join(x) + " |" for x in r.values])


def stats(daily, trades=None, cost=0.0, rf=None):
    eq = (1 + daily).cumprod()
    out = {"CAGR%": cagr(daily), "vol%": 100 * daily.std() * np.sqrt(365), "maxDD%": 100 * (eq / eq.cummax() - 1).min(),
           "sharpe": sharpe(daily)}
    if rf is not None:
        out["xs_sharpe"] = sharpe(daily - rf.reindex(daily.index).fillna(0))
    if trades is not None:
        t = np.asarray(trades)
        out = {"trades": len(t), "win%": 100 * (t > 0).mean(), "exp%": 100 * t.mean(), **out}
    return out


def quality(sym, d, m):
    """Internal Alpaca checks (no second venue reachable): daily open vs prior close gap, daily close vs the last
    30m close of the same UTC day, missing / zero-range / stale 30m bars."""
    gap = (d["o"] / d["c"].shift(1) - 1).abs() * 100
    full_days = pd.date_range(d.index[0], d.index[-1], freq="D")
    m_day = m.groupby(m.index.normalize())["c"].last()
    both = d["c"].reindex(m_day.index).dropna()
    dc = ((m_day.reindex(both.index) / both - 1).abs() * 100)
    exp = pd.date_range(m.index[0], m.index[-1], freq="30min")
    zero = (m["h"] == m["l"])
    stale = zero & (m["c"] == m["c"].shift(1))
    return {"symbol": sym,
            "daily_missing": len(full_days) - len(d),
            "largest_hole_days": int(d.index.to_series().diff().dt.days.max()) - 1,
            "open_vs_prev_close_med%": gap.median(), "open_vs_prev_close_max%": gap.max(),
            "gaps>1%": int((gap > 1).sum()),
            "daily_vs_30m_close_max%": dc.max(),
            "30m_bars": len(m), "30m_missing": len(exp) - len(m),
            "30m_zero_range": int(zero.sum()), "30m_stale": int(stale.sum()), "30m_zero_vol": int((m["v"] == 0).sum())}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fee", type=float, default=0.0025, help="per-side fee (Alpaca crypto taker tier 1 = 0.25%%)")
    ap.add_argument("--slip", type=float, default=0.0005, help="per-side slippage")
    ap.add_argument("--daily-start", default="2021-01-01")
    ap.add_argument("--recent-years", type=float, default=2.0)
    ap.add_argument("--intraday-days", type=int, default=60)
    ap.add_argument("--cache", default=str(Path(__file__).resolve().parents[1] / ".cache" / "crypto_edge"))
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    cache = Path(a.cache)
    cache.mkdir(parents=True, exist_ok=True)
    side = a.fee + a.slip
    # end at the last completed UTC day: drop today's partial bar
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(seconds=1)
    d0 = datetime.fromisoformat(a.daily_start).replace(tzinfo=timezone.utc)
    i0 = today + timedelta(seconds=1) - timedelta(days=a.intraday_days)
    recent = pd.Timestamp(today + timedelta(seconds=1) - timedelta(days=round(365.25 * a.recent_years)))
    rf, rf_ann = tbill_daily(cache, d0, today)
    strats = [("TSMOM 28d (long/flat)", tsmom), ("Donchian 20/10 (long/flat)", donchian),
              ("Abnormal-day momentum (L/S)", abnormal_day)]

    main_rows, fill_rows, bh_rows, ts_rows, boot_rows, q_rows = [], [], [], [], [], []
    for sym in SYMS:
        d = fetch(sym, "1Day", d0, today, cache)
        m = fetch(sym, "30Min", i0, today, cache)
        q_rows.append(quality(sym, d, m))
        bh = seg_bh(d)
        for name, f in strats:
            for fill in ["same_close", "next_open", "next_close"]:
                tr, daily, _ = seg_run(d, f, side, fill)
                st = stats(daily, tr, 2 * side)
                fill_rows.append({"strategy": name, "symbol": sym, "fill": fill, "trades": st["trades"],
                                  "exp%": st["exp%"], "sharpe": st["sharpe"], "maxDD%": st["maxDD%"]})
                if fill == "next_open":
                    main_rows.append({"strategy": name, "tf": "1D", "symbol": sym, **stats(daily, tr, 2 * side)})
        main_rows.append({"strategy": "Buy & hold (reference)", "tf": "1D", "symbol": sym, **stats(bh)})
        for name, kind in [("Intraday TS momentum 1st->last 30m (L/S)", "ihm"), ("21-23 UTC seasonality (long)", "season")]:
            tr, daily = intraday(m, side, kind)
            main_rows.append({"strategy": name, "tf": "30m", "symbol": sym, **stats(daily, tr, 2 * side)})

        # buy & hold by period
        bper = [("full", d.index[0]), (f"last {a.recent_years:g}y", recent)]
        if sym == "SOL/USD":
            bper.append(("ex-2021 (2022+)", pd.Timestamp("2022-01-01", tz="UTC")))
        for per, st0 in bper:
            x = bh[bh.index >= st0]
            x.iloc[0] = 0.0
            bh_rows.append({"symbol": sym, "period": per, "from": f"{x.index[0]:%Y-%m-%d}", **stats(x, rf=rf)})

        # TSMOM variants: periods x cash, with bootstrap vs buy & hold
        periods = [("full", d.index[0]), (f"last {a.recent_years:g}y", recent)]
        if sym == "SOL/USD":
            periods.append(("ex-2021 (2022+)", pd.Timestamp("2022-01-01", tz="UTC")))
        for cash in [False, True]:
            tr_all, daily, held = seg_run(d, tsmom, side, "next_open", rf if cash else None)
            for per, st0 in periods:
                x = daily[daily.index >= st0].copy()
                x.iloc[0] = 0.0
                b = bh[bh.index >= st0].copy()
                b.iloc[0] = 0.0
                tr = seg_trades_in(d, held, side, st0)
                st = stats(x, tr, 2 * side, rf)
                ts_rows.append({"symbol": sym, "period": per, "idle cash": "T-bill" if cash else "0%",
                                **{k: st[k] for k in ["trades", "exp%", "CAGR%", "maxDD%", "sharpe", "xs_sharpe"]},
                                "B&H sharpe": sharpe(b), "B&H xs_sharpe": sharpe(b - rf.reindex(b.index).fillna(0))})
                r = rf.reindex(x.index).fillna(0)
                ex = (x - r, b - r) if cash else (x, b)
                pt, lo, hi, p0 = boot_sharpe_diff(*ex)
                boot_rows.append({"symbol": sym, "period": per, "idle cash": "T-bill" if cash else "0%",
                                  "sharpe": "excess" if cash else "raw", "diff": pt, "lo95": lo, "hi95": hi,
                                  "P(diff<=0)": p0, "CI excludes 0": "yes" if lo > 0 or hi < 0 else "no"})

    t = pd.DataFrame(main_rows)
    ref = t["strategy"].str.startswith("Buy & hold")
    t["status"] = np.where(ref, "reference", np.where(t["trades"] < MIN_TRADES, f"REJECT (<{MIN_TRADES} trades)", "ok"))
    t = t[["strategy", "tf", "symbol", "trades", "win%", "exp%", "maxDD%", "sharpe", "CAGR%", "status"]]
    sections = {
        f"Main table — next-bar-open fills, cost {side:.2%}/side": t,
        "Fill timing check (daily strategies)": pd.DataFrame(fill_rows),
        "Buy & hold by period (xs_sharpe = minus T-bill)": pd.DataFrame(bh_rows),
        "TSMOM variants (next-open fills)": pd.DataFrame(ts_rows),
        "Bootstrap 95% CI: Sharpe(TSMOM) - Sharpe(B&H), circular block 20d, 5000 reps": pd.DataFrame(boot_rows),
        "Data quality (Alpaca only)": pd.DataFrame(q_rows),
    }
    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 30)
    txt = []
    for k, v in sections.items():
        print(f"\n== {k}\n{v.round(3).to_string(index=False)}")
        txt.append(f"### {k}\n\n{md_table(v)}\n")
    print(f"\nT-bill (BIL-implied) annual rate: first {rf_ann.dropna().iloc[0]:.2%}, mean {rf_ann.mean():.2%}, last {rf_ann.iloc[-1]:.2%}")
    if a.out:
        Path(a.out).write_text("\n".join(txt))
    return sections


if __name__ == "__main__":
    main()
