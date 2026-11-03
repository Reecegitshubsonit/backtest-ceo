"""Five ETF strategies vs buy-and-hold SPY. Read-only market data, no orders.

Data: Alpaca SIP bars, split+dividend adjusted (Yahoo is blocked from this environment).
Daily strategies: 2016-01-04 .. latest close. Intraday strategy: last 60 calendar days of 5-min RTH bars.
Execution: signal on bar close, fill at NEXT bar open (no lookahead). Costs charged on every fill.
Sharpe: daily returns, rf = 0, sqrt(252). Idle cash earns 0.
Run: python3 research/etf_strategies/backtest.py
"""
import json, os, sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import requests

HERE = Path(__file__).resolve().parent
CACHE = HERE.parent.parent / "data" / "etf_research_cache"  # gitignored
CACHE.mkdir(parents=True, exist_ok=True)
URL = "https://data.alpaca.markets/v2/stocks/bars"
HDR = {"APCA-API-KEY-ID": os.environ.get("ALPACA_API_KEY", "x"), "APCA-API-SECRET-KEY": os.environ.get("ALPACA_SECRET_KEY", "x")}

DAILY_START = "2016-01-01"
COST_DAILY = 0.0003     # 3 bp per side: 1 bp fees/SEC + 2 bp spread/slippage
COST_INTRA = 0.0002     # 2 bp per side on SPY (spread ~0.15 bp; rest = slippage on 5-min fills)
SECTORS = ["XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY", "XLRE", "XLC"]
TREND_SET = ["SPY", "QQQ", "IWM", "EFA", "EEM", "TLT", "IEF", "GLD", "DBC", "VNQ"]
ROT_SET = ["SPY", "QQQ", "EFA", "TLT", "GLD"]
CASH = "BIL"


def fetch(symbol, timeframe, start, end=None):
    key = CACHE / f"{symbol}_{timeframe}_{start}_{end or 'now'}_{datetime.now(timezone.utc).date()}.json"
    if key.exists():
        rows = json.loads(key.read_text())
    else:
        rows, token = [], None
        while True:
            p = {"symbols": symbol, "timeframe": timeframe, "start": start, "adjustment": "all",
                 "feed": "sip", "limit": 10000, "sort": "asc"}
            if end: p["end"] = end
            if token: p["page_token"] = token
            r = requests.get(URL, headers=HDR, params=p, timeout=60)
            r.raise_for_status()
            b = r.json()
            rows += (b.get("bars") or {}).get(symbol, [])
            token = b.get("next_page_token")
            if not token: break
        key.write_text(json.dumps(rows))
    df = pd.DataFrame(rows)
    df["t"] = pd.to_datetime(df["t"], utc=True)
    return df.set_index("t")[["o", "h", "l", "c", "v"]]


def daily_panel(symbols):
    o, c = {}, {}
    for s in symbols:
        d = fetch(s, "1Day", DAILY_START)
        d.index = d.index.tz_convert("America/New_York").normalize().tz_localize(None)
        o[s], c[s] = d["o"], d["c"]
    return pd.DataFrame(o), pd.DataFrame(c)


def run_weights(target, O, C, cost):
    """target: weights decided at close of day t (rows = dates). Executed at open of t+1.
    Day return = old weights over prev close->open + new weights over open->close - cost * turnover."""
    target = target.reindex(C.index).fillna(0.0)
    held = target.shift(1).fillna(0.0)           # weight held from open t+1
    prev = held.shift(1).fillna(0.0)             # weight held before that open
    gap = (O / C.shift(1) - 1).fillna(0.0)
    intra = (C / O - 1).fillna(0.0)
    turnover = (held - prev).abs().sum(axis=1)
    ret = (prev * gap).sum(axis=1) + (held * intra).sum(axis=1) - cost * turnover
    # trade count: each change in a symbol's weight is one fill (rebalance trims count too)
    trades = int(((held - prev).abs() > 1e-9).sum().sum())
    return ret, trades


def stats(ret, trades, periods_per_year=252):
    ret = ret.dropna()
    eq = (1 + ret).cumprod()
    days = (ret.index[-1] - ret.index[0]).days or 1
    cagr = eq.iloc[-1] ** (365.25 / days) - 1
    mdd = (eq / eq.cummax() - 1).min()
    sharpe = ret.mean() / ret.std() * np.sqrt(periods_per_year) if ret.std() > 0 else 0.0
    return {"CAGR": cagr, "MaxDD": mdd, "Sharpe": sharpe, "Trades": trades, "Total": eq.iloc[-1] - 1}


def rsi(c, n):
    d = c.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn)


def month_ends(idx):
    s = pd.Series(idx, index=idx)
    return set(s.groupby([idx.year, idx.month]).max())


# ---------------- daily strategies ----------------
def s_spy_bh(O, C):
    w = pd.DataFrame(0.0, index=C.index, columns=C.columns); w["SPY"] = 1.0
    return w


def s_sma200(O, C):
    """Trend 1: SPY when close > 200d SMA, else BIL. Checked daily."""
    w = pd.DataFrame(0.0, index=C.index, columns=C.columns)
    on = C["SPY"] > C["SPY"].rolling(200).mean()
    w["SPY"] = on.astype(float); w[CASH] = (~on).astype(float)
    w.iloc[:199] = 0.0
    return w


def s_tsmom(O, C):
    """Trend 2: 10-ETF multi-asset, equal 10% slots; slot held if 12-1 month return > 0 AND close > 200d SMA, else BIL.
    Monthly rebalance on last trading day."""
    w = pd.DataFrame(np.nan, index=C.index, columns=C.columns)
    mom = C[TREND_SET].shift(21) / C[TREND_SET].shift(252) - 1
    sma = C[TREND_SET].rolling(200).mean()
    me = month_ends(C.index)
    for d in C.index:
        if d not in me or pd.isna(mom.loc[d]).any(): continue
        on = (mom.loc[d] > 0) & (C.loc[d, TREND_SET] > sma.loc[d])
        row = pd.Series(0.0, index=C.columns)
        row[TREND_SET] = on.astype(float) / len(TREND_SET)
        row[CASH] = 1 - row[TREND_SET].sum()
        w.loc[d] = row
    return w.ffill().fillna(0.0)


def s_sector_rot(O, C):
    """Rotation 1: SPDR sectors, hold top 3 by blended 1/3/6-month momentum, equal weight, monthly.
    Absolute filter: a pick must beat BIL over 6 months, else its slot goes to BIL. XLRE/XLC join when they have history."""
    w = pd.DataFrame(np.nan, index=C.index, columns=C.columns)
    m = (C[SECTORS] / C[SECTORS].shift(21) + C[SECTORS] / C[SECTORS].shift(63) + C[SECTORS] / C[SECTORS].shift(126)) / 3 - 1
    m6 = C[SECTORS] / C[SECTORS].shift(126) - 1
    b6 = C[CASH] / C[CASH].shift(126) - 1
    me = month_ends(C.index)
    for d in C.index:
        if d not in me: continue
        sc = m.loc[d].dropna()
        if len(sc) < 9: continue
        row = pd.Series(0.0, index=C.columns)
        for s in sc.nlargest(3).index:
            row[s if m6.loc[d, s] > b6.loc[d] else CASH] += 1 / 3
        w.loc[d] = row
    return w.ffill().fillna(0.0)


def s_dual_mom(O, C):
    """Rotation 2: dual momentum across SPY/QQQ/EFA/TLT/GLD. Hold the single best 6-month (126d) performer
    if it beats BIL over the same window, else BIL. Monthly."""
    w = pd.DataFrame(np.nan, index=C.index, columns=C.columns)
    r6 = C / C.shift(126) - 1
    me = month_ends(C.index)
    for d in C.index:
        if d not in me or pd.isna(r6.loc[d, ROT_SET + [CASH]]).any(): continue
        best = r6.loc[d, ROT_SET].idxmax()
        row = pd.Series(0.0, index=C.columns)
        row[best if r6.loc[d, best] > r6.loc[d, CASH] else CASH] = 1.0
        w.loc[d] = row
    return w.ffill().fillna(0.0)


def s_rsi2(O, C):
    """Mean reversion 1 (daily): Connors RSI(2) on SPY. Long when RSI2 < 10 and close > 200d SMA;
    exit when close > 5d SMA or after 10 days. Idle cash = 0%."""
    c = C["SPY"]; r = rsi(c, 2); sma200 = c.rolling(200).mean(); sma5 = c.rolling(5).mean()
    pos = np.zeros(len(c)); inpos, age = False, 0
    for i in range(len(c)):
        if inpos:
            age += 1
            if c.iloc[i] > sma5.iloc[i] or age >= 10: inpos = False
        elif r.iloc[i] < 10 and c.iloc[i] > sma200.iloc[i]:
            inpos, age = True, 0
        pos[i] = 1.0 if inpos else 0.0
    w = pd.DataFrame(0.0, index=C.index, columns=C.columns); w["SPY"] = pos
    return w


# ---------------- intraday strategy ----------------
def intraday():
    """Mean reversion 2 (intraday, SPY 5-min, RTH): z = (close - session VWAP) / rolling 20-bar std of (close - VWAP).
    Long z < -2, short z > +2; exit when price crosses VWAP or at the 15:55 bar. No new entries after 15:30
    and none on the first 6 bars (30 min). Fills at next bar open. Flat overnight."""
    end = datetime.now(timezone.utc)
    start = (end - timedelta(days=60)).strftime("%Y-%m-%d")
    d = fetch("SPY", "5Min", start)
    d.index = d.index.tz_convert("America/New_York")
    d = d.between_time("09:30", "15:55")
    d["date"] = d.index.date
    pv = (d["c"] + d["h"] + d["l"]) / 3 * d["v"]
    d["vwap"] = pv.groupby(d["date"]).cumsum() / d["v"].groupby(d["date"]).cumsum()
    dev = d["c"] - d["vwap"]
    d["z"] = dev / dev.groupby(d["date"]).transform(lambda x: x.rolling(20, min_periods=6).std())
    d["bar"] = d.groupby("date").cumcount()
    tod = d.index.strftime("%H:%M")
    sig = np.zeros(len(d)); pos = 0
    for i in range(len(d)):
        z, last = d["z"].iloc[i], tod[i] >= "15:50"
        if pos == 1 and (dev.iloc[i] >= 0 or last): pos = 0
        elif pos == -1 and (dev.iloc[i] <= 0 or last): pos = 0
        if pos == 0 and not last and tod[i] <= "15:30" and d["bar"].iloc[i] >= 6 and not np.isnan(z):
            if z < -2: pos = 1
            elif z > 2: pos = -1
        sig[i] = pos
    held = pd.Series(sig, index=d.index).groupby(d["date"]).shift(1).fillna(0.0)  # fill at next bar open, same day
    # bar return for a position entered at this bar's open: open->close; carried positions: prev close->close
    prev_held = held.groupby(d["date"]).shift(1).fillna(0.0)
    o, c = d["o"], d["c"]; pc = c.groupby(d["date"]).shift(1)
    gap = (o / pc - 1).fillna(0.0)
    r = prev_held * gap + held * (c / o - 1) - COST_INTRA * (held - prev_held).abs()
    # 15:55 bar: anything held is closed at that bar's close (cost charged)
    is_last = d["date"] != pd.Series(d["date"], index=d.index).shift(-1)
    r = r - COST_INTRA * held.abs() * is_last
    trades = int(((held - prev_held).abs() > 0).sum() + (held.abs() * is_last).sum())
    daily = (1 + r).groupby(d["date"]).prod() - 1
    daily.index = pd.to_datetime(daily.index)
    # SPY buy-and-hold over the same window, daily closes
    dc = d["c"].groupby(d["date"]).last(); dc.index = pd.to_datetime(dc.index)
    first_open = d["o"].iloc[0]
    bh = dc.pct_change(); bh.iloc[0] = dc.iloc[0] / first_open - 1
    return daily, trades, bh, (daily.index[0].date(), daily.index[-1].date(), len(daily))


def fmt(rows, title):
    out = [f"### {title}", "", "| Strategy | CAGR | Max DD | Sharpe | Trades | Total return |", "|---|---:|---:|---:|---:|---:|"]
    for name, s in rows:
        out.append(f"| {name} | {s['CAGR']*100:.1f}% | {s['MaxDD']*100:.1f}% | {s['Sharpe']:.2f} | {s['Trades']} | {s['Total']*100:.1f}% |")
    return "\n".join(out)


def main():
    syms = sorted(set(["SPY", CASH] + SECTORS + TREND_SET + ROT_SET))
    O, C = daily_panel(syms)
    strategies = [
        ("SPY buy & hold (benchmark)", s_spy_bh),
        ("1. Trend: SPY 200d SMA / BIL", s_sma200),
        ("2. Trend: 10-ETF TSMOM (12-1m + SMA200)", s_tsmom),
        ("3. Rotation: top-3 sectors, 1/3/6m mom", s_sector_rot),
        ("4. Rotation: dual momentum SPY/QQQ/EFA/TLT/GLD", s_dual_mom),
        ("5a. Mean rev: SPY RSI(2) < 10 > SMA200", s_rsi2),
    ]
    first_full = C.index[C.index >= "2017-01-03"][0]   # warm-up: 252d lookbacks need 2016
    two_y = C.index[C.index >= C.index[-1] - pd.Timedelta(days=730)][0]
    results = {}
    md = [f"Daily data: Alpaca SIP adjusted, {C.index[0].date()} .. {C.index[-1].date()}. Costs {COST_DAILY*1e4:.0f} bp/side."]
    for label, start in [(f"Full: {first_full.date()} .. {C.index[-1].date()}", first_full), (f"Last 2 years: {two_y.date()} .. {C.index[-1].date()}", two_y)]:
        rows = []
        for name, fn in strategies:
            w = fn(O, C)
            w = w.loc[w.index >= start - pd.Timedelta(days=1)]
            # start every strategy flat the day before the window, so entry costs are charged
            w.iloc[0] = 0.0
            ret, n = run_weights(w, O.loc[w.index], C.loc[w.index], COST_DAILY)
            ret = ret.loc[ret.index >= start]
            rows.append((name, stats(ret, n)))
        results[label] = rows
        md.append(fmt(rows, label))
    daily, n, bh, (a, b, nd) = intraday()
    irows = [("SPY buy & hold (same window)", stats(bh, 1)),
             ("5b. Mean rev intraday: SPY 5m VWAP z±2", stats(daily, n))]
    md.append(fmt(irows, f"Intraday: SPY 5-min RTH, {a} .. {b} ({nd} sessions), costs {COST_INTRA*1e4:.0f} bp/side"))
    text = "\n\n".join(md)
    print(text)
    (HERE / "results.md").write_text(text + "\n")
    flat = [{"window": k, "strategy": n_, **v} for k, rows in list(results.items()) + [("intraday", irows)] for n_, v in rows]
    pd.DataFrame(flat).to_csv(HERE / "results.csv", index=False, float_format="%.6f")


if __name__ == "__main__":
    main()
