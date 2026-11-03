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
            for a in range(5):
                r = requests.get(URL, params=p, headers=h, timeout=30)
                if r.status_code == 200:
                    break
                time.sleep(2 ** a)
            r.raise_for_status()
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


def run_positions(close, pos, side_cost):
    """pos[t] is chosen at close t and earns close t -> close t+1. Fee charged per unit of position change."""
    ret = close.pct_change().shift(-1).fillna(0)
    pos = pos.fillna(0)
    turn = pos.diff().abs().fillna(pos.abs())
    daily = pos * ret - turn * side_cost
    trades, cur, acc = [], 0, 1.0
    for p, r in zip(pos.values, ret.values):
        if p != cur:
            if cur != 0:
                trades.append(acc - 1 - 2 * side_cost)
            cur, acc = p, 1.0
        if cur != 0:
            acc *= 1 + cur * r
    if cur != 0:
        trades.append(acc - 1 - 2 * side_cost)
    return trades, daily


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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fee", type=float, default=0.0025, help="per-side fee (Alpaca crypto taker tier 1 = 0.25%%)")
    ap.add_argument("--slip", type=float, default=0.0005, help="per-side slippage")
    ap.add_argument("--daily-start", default="2021-01-01")
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

    rows = []
    for sym in SYMS:
        d = fetch(sym, "1Day", d0, today, cache)
        span = f"{d.index[0]:%Y-%m-%d}..{d.index[-1]:%Y-%m-%d}"
        for name, f in [("TSMOM 28d (long/flat)", tsmom), ("Donchian 20/10 (long/flat)", donchian),
                        ("Abnormal-day momentum (L/S)", abnormal_day)]:
            tr, daily = run_positions(d["c"], f(d), side)
            rows.append({"strategy": name, "tf": "1D", "symbol": sym, "span": span, **metrics(tr, daily, 2 * side)})
        bh = d["c"].pct_change().fillna(0)
        rows.append({"strategy": "Buy & hold (reference)", "tf": "1D", "symbol": sym, "span": span,
                     **metrics([d["c"].iloc[-1] / d["c"].iloc[0] - 1 - 2 * side], bh, 2 * side)})
        m = fetch(sym, "30Min", i0, today, cache)
        span = f"{m.index[0]:%Y-%m-%d}..{m.index[-1]:%Y-%m-%d}"
        for name, kind in [("Intraday TS momentum 1st->last 30m (L/S)", "ihm"), ("21-23 UTC seasonality (long)", "season")]:
            tr, daily = intraday(m, side, kind)
            rows.append({"strategy": name, "tf": "30m", "symbol": sym, "span": span, **metrics(tr, daily, 2 * side)})

    t = pd.DataFrame(rows)
    ref = t["strategy"].str.startswith("Buy & hold")
    t["status"] = np.where(ref, "reference", np.where(t["trades"] < MIN_TRADES, f"REJECT (<{MIN_TRADES} trades)", "ok"))
    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 20)
    print(f"cost per side = {side:.4%} (fee {a.fee:.4%} + slip {a.slip:.4%})")
    print(t.round(2).to_string(index=False))
    if a.out:
        cols = ["strategy", "tf", "symbol", "trades", "win%", "exp%", "gross_exp%", "maxDD%", "sharpe", "total%", "status"]
        r = t[cols].round(2).astype(str)
        md = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)] + ["| " + " | ".join(x) + " |" for x in r.values]
        Path(a.out).write_text(f"cost per side {side:.2%}\n\n" + "\n".join(md) + "\n")
    return t


if __name__ == "__main__":
    main()
