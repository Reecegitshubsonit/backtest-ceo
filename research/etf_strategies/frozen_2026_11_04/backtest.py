"""Five ETF strategies vs buy-and-hold SPY. Read-only market data, no orders.

Data: Alpaca SIP bars, split+dividend adjusted (Yahoo is blocked from this environment). Alpaca history starts 2016-01-04.
Daily strategies: scored 2017-01-03 .. latest close (2016 = indicator warm-up) and over the last 2 years.
Intraday strategy (--intraday): last 60 calendar days of SPY 5-min RTH bars.

Engine: holdings drift with prices between rebalances (no free daily rebalancing). Signal on close, trade at NEXT open.
Costs on traded notional. Any unallocated weight is cash earning BIL's daily total return, free to move.
Sharpe = mean/std of daily returns in excess of BIL, x sqrt(252).
Run: python3 research/etf_strategies/backtest.py [--intraday]
"""
import json, os, sys, time
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
            for attempt in range(6):
                r = requests.get(URL, headers=HDR, params=p, timeout=60)
                if r.status_code != 429: break
                time.sleep(2 ** attempt)
            r.raise_for_status()
            b = r.json()
            rows += (b.get("bars") or {}).get(symbol, [])
            token = b.get("next_page_token")
            if not token: break
        key.write_text(json.dumps(rows))
    df = pd.DataFrame(rows)
    df["t"] = pd.to_datetime(df["t"], utc=True)
    return df.set_index("t")[["o", "h", "l", "c", "v"]]


DAILY_START = "2016-01-01"
SCORE_START = "2017-01-03"
COST_DAILY = 0.0003     # 3 bp per side: 1 bp fees/SEC + 2 bp spread/slippage
COST_INTRA = 0.0002     # 2 bp per side on SPY (spread ~0.15 bp; rest = slippage on 5-min fills)
CASH = "BIL"            # T-bill proxy: idle cash return and Sharpe risk-free rate (net of BIL's 0.14% fee)
SECTORS = ["XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY", "XLRE", "XLC"]
# Original list (picked by me in 2026; see README for the hindsight discussion)
TREND_SET = ["SPY", "QQQ", "IWM", "EFA", "EEM", "TLT", "IEF", "GLD", "DBC", "VNQ"]
# Rule-chosen lists for the robustness rerun
SECTORS_2017 = ["XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY", "XLRE"]   # every Select Sector SPDR listed before 2017-01-01
GTAA5 = ["SPY", "EFA", "IEF", "VNQ", "DBC"]   # Faber (2007) "A Quantitative Approach to Tactical Asset Allocation", 5 classes
ROT_SET = ["SPY", "QQQ", "EFA", "TLT", "GLD"]
BOOT_N, BOOT_BLOCK, SEED = 5000, 21, 7


def daily_panel(symbols):
    o, c = {}, {}
    for s in symbols:
        d = fetch(s, "1Day", DAILY_START)
        d.index = d.index.tz_convert("America/New_York").normalize().tz_localize(None)
        o[s], c[s] = d["o"], d["c"]
    return pd.DataFrame(o), pd.DataFrame(c)


def simulate(target, O, C, rf, cost):
    """target: rows = signal dates (decided at that close), NaN rows = no instruction (holdings drift).
    A non-NaN row is executed at the next open if it differs from the drifted weights by > 1e-6.
    Returns daily returns and trade counts. Weight left unallocated sits in cash at rf."""
    cols = list(target.columns)
    Ov, Cv, rfv = O[cols].values, C[cols].values, rf.values
    gap = np.nan_to_num(Ov[1:] / Cv[:-1], nan=1.0); gap = np.vstack([np.ones(len(cols)), gap])
    intra = np.nan_to_num(Cv / Ov, nan=1.0)   # assets not yet listed: no move (and never targeted)
    T = target.values
    n, k = Cv.shape
    v = np.zeros(k); cash = 1.0; prev_eq = 1.0
    ret = np.zeros(n)
    fills = resizes = entries = exits = 0
    for i in range(n):
        if i > 0:
            v = v * gap[i]
            tgt = T[i - 1]
            if not np.isnan(tgt).all():
                tgt = np.nan_to_num(tgt)
                eq = v.sum() + cash
                cur = v / eq
                if np.abs(tgt - cur).max() > 1e-6:
                    net = eq
                    for _ in range(3):              # costs come out of the target book, not out of cash
                        new = tgt * net
                        net = eq - cost * np.abs(new - v).sum()
                    new = tgt * net
                    traded = np.abs(new - v)
                    moved = traded > 1e-9 * eq
                    fills += int(moved.sum())
                    was, now = v > 1e-12, new > 1e-12
                    entries += int((~was & now).sum())
                    exits += int((was & ~now).sum())
                    resizes += int((moved & was & now).sum())
                    cash = eq - new.sum() - cost * traded.sum()
                    v = new
            v = v * intra[i]
            cash = cash * (1 + rfv[i])
        eq = v.sum() + cash
        ret[i] = eq / prev_eq - 1
        prev_eq = eq
    still_open = int((v > 1e-12).sum())
    return pd.Series(ret, index=C.index), {"fills": fills, "resizes": resizes, "entries": entries,
                                           "exits": exits, "round_trips": exits, "open_at_end": still_open,
                                           "pos_changes": entries + exits}


def drawdown_stats(ret):
    eq = (1 + ret).cumprod()
    peak = eq.cummax()
    dd = eq / peak - 1
    # longest time below a prior peak, in calendar days (ongoing drawdowns count to the last date)
    under = dd < -1e-12
    longest, start = 0, None
    for d, u in under.items():
        if u and start is None: start = last_peak
        if not u:
            if start is not None: longest = max(longest, (d - start).days); start = None
            last_peak = d
    if start is not None: longest = max(longest, (dd.index[-1] - start).days)
    return dd.min(), longest


def stats(ret, rf):
    ret, rf = ret.dropna(), rf.reindex(ret.index).fillna(0)
    eq = (1 + ret).cumprod()
    yrs = (ret.index[-1] - ret.index[0]).days / 365.25
    ex = ret - rf
    mdd, longest = drawdown_stats(ret)
    return {"CAGR": eq.iloc[-1] ** (1 / yrs) - 1, "Vol": ret.std() * np.sqrt(252),
            "Sharpe": ex.mean() / ex.std() * np.sqrt(252) if ex.std() > 0 else np.nan, "MaxDD": mdd, "LongestDD_days": longest}


def vol_matched_spy(spy, rf, target_vol):
    """SPY scaled (daily, frictionless) to target_vol, rest in T-bills: r = rf + k (spy - rf)."""
    k = target_vol / (spy.std() * np.sqrt(252))
    return rf + k * (spy - rf), k


def boot_sharpe_diff(a, b, rf):
    """Circular block bootstrap (21-day blocks) of paired daily excess returns. 95% CI on Sharpe(a) - Sharpe(b)."""
    ea, eb = (a - rf).values, (b - rf).values
    n = len(ea); rng = np.random.default_rng(SEED)
    nb = int(np.ceil(n / BOOT_BLOCK))
    starts = rng.integers(0, n, size=(BOOT_N, nb))
    idx = ((starts[:, :, None] + np.arange(BOOT_BLOCK)) % n).reshape(BOOT_N, -1)[:, :n]
    sa = ea[idx].mean(1) / ea[idx].std(1) * np.sqrt(252)
    sb = eb[idx].mean(1) / eb[idx].std(1) * np.sqrt(252)
    d = sa - sb
    point = ea.mean() / ea.std() * np.sqrt(252) - eb.mean() / eb.std() * np.sqrt(252)
    return point, np.percentile(d, 2.5), np.percentile(d, 97.5), (d <= 0).mean()


def rsi(c, n):
    d = c.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn)


def month_end_mask(idx):
    s = pd.Series(idx, index=idx)
    me = set(s.groupby([idx.year, idx.month]).max())
    return np.array([d in me for d in idx])


def blank(C, cols):
    return pd.DataFrame(np.nan, index=C.index, columns=cols)


# ---------------- daily strategies: return target weights (NaN = hold/drift) ----------------
def s_spy_bh(C):
    w = blank(C, ["SPY"]); w.iloc[:] = 1.0
    return w


def s_sma200(C):
    """Trend 1: 100% SPY when close > 200d SMA, else cash (T-bills). Checked daily."""
    on = (C["SPY"] > C["SPY"].rolling(200).mean()).astype(float)
    on[C["SPY"].rolling(200).mean().isna()] = np.nan
    return pd.DataFrame({"SPY": on})


def make_tsmom(universe):
    def s(C):
        """Trend 2: equal 1/N slots; slot held if 12-1 month return > 0 AND close > 200d SMA, else cash. Monthly,
        full rebalance to 1/N on each month end (drift trims are resizes, not trades)."""
        mom = C[universe].shift(21) / C[universe].shift(252) - 1
        on = ((mom > 0) & (C[universe] > C[universe].rolling(200).mean())).astype(float) / len(universe)
        on[mom.isna().any(axis=1)] = np.nan
        on[~month_end_mask(C.index)] = np.nan
        return on
    return s


def s_sector_rot(C):
    """Rotation 1: SPDR sectors, top 3 by average of 1/3/6-month returns, 1/3 each, monthly.
    Absolute filter: a pick must beat BIL over 6 months, else its slot stays in cash. XLC joins once it has 6m history."""
    S = C[SECTORS]
    m = (S / S.shift(21) + S / S.shift(63) + S / S.shift(126)) / 3 - 1
    m6 = S / S.shift(126) - 1
    b6 = C[CASH] / C[CASH].shift(126) - 1
    w = blank(C, SECTORS)
    for i in np.where(month_end_mask(C.index))[0]:
        sc = m.iloc[i].dropna()
        if len(sc) < 9: continue
        row = pd.Series(0.0, index=SECTORS)
        for s in sc.nlargest(3).index:
            if m6.iloc[i][s] > b6.iloc[i]: row[s] = 1 / 3
        w.iloc[i] = row.values
    return w


def s_dual_mom(C):
    """Rotation 2: best 6-month (126d) performer of SPY/QQQ/EFA/TLT/GLD if it beats BIL, else cash. Monthly."""
    r6 = C / C.shift(126) - 1
    w = blank(C, ROT_SET)
    for i in np.where(month_end_mask(C.index))[0]:
        if r6.iloc[i][ROT_SET + [CASH]].isna().any(): continue
        best = r6.iloc[i][ROT_SET].idxmax()
        row = pd.Series(0.0, index=ROT_SET)
        if r6.iloc[i][best] > r6.iloc[i][CASH]: row[best] = 1.0
        w.iloc[i] = row.values
    return w


def s_rsi2(C):
    """Mean reversion (daily): Connors RSI(2) on SPY. Long when RSI2 < 10 and close > 200d SMA;
    exit when close > 5d SMA or after 10 days. Idle = cash at T-bill rate."""
    c = C["SPY"]; r = rsi(c, 2); sma200 = c.rolling(200).mean(); sma5 = c.rolling(5).mean()
    pos = np.zeros(len(c)); inpos, age = False, 0
    for i in range(len(c)):
        if inpos:
            age += 1
            if c.iloc[i] > sma5.iloc[i] or age >= 10: inpos = False
        elif r.iloc[i] < 10 and c.iloc[i] > sma200.iloc[i]:
            inpos, age = True, 0
        pos[i] = 1.0 if inpos else 0.0
    pos[sma200.isna().values] = np.nan
    return pd.DataFrame({"SPY": pos}, index=C.index)


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


def pct(x): return f"{x*100:.1f}%"


def run_window(strategies, O, C, rf, start):
    """Every strategy starts in cash the day before `start`, then takes its latest standing target at the first open."""
    idx = C.index[C.index >= start]
    pre = C.index[C.index < start][-1]
    sl = C.index[C.index >= pre]
    out = {}
    for name, fn in strategies:
        t = fn(C)
        t0 = t.loc[:pre].ffill().iloc[-1]          # standing target as of the day before the window
        t = t.loc[sl].copy()
        t.iloc[0] = t0.fillna(0.0).values
        ret, tr = simulate(t, O.loc[sl], C.loc[sl], rf.loc[sl], COST_DAILY)
        out[name] = (ret.loc[idx], tr)
    return out


def report(res, rf, title):
    spy = res[BENCH][0]
    rf = rf.reindex(spy.index)
    lines = [f"### {title}", "",
             "| Strategy | CAGR | Vol | Sharpe (xs T-bill) | Max DD | Longest DD (days) | Round trips | Position changes | Fills (incl. resizes) |",
             "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    vm = ["", f"**Vol-matched SPY** (SPY scaled daily to the strategy's vol, rest in T-bills, frictionless) and **bootstrap 95% CI on Sharpe(strategy) − Sharpe(SPY)** ({BOOT_N} resamples, {BOOT_BLOCK}-day circular blocks):", "",
          "| Strategy | Strategy CAGR | Vol-matched SPY CAGR | Strategy max DD | Vol-matched SPY max DD | SPY scale | ΔSharpe | 95% CI | P(boot Δ ≤ 0) |",
          "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    rows = []
    for name, (ret, tr) in res.items():
        s = stats(ret, rf)
        rt = f"{tr['round_trips']}" + (f" (+{tr['open_at_end']} open)" if tr["open_at_end"] else "")
        lines.append(f"| {name} | {pct(s['CAGR'])} | {pct(s['Vol'])} | {s['Sharpe']:.2f} | {pct(s['MaxDD'])} | {s['LongestDD_days']} | {rt} | {tr['pos_changes']} | {tr['fills']} |")
        row = {"window": title, "strategy": name, **s, **tr}
        if name != BENCH:
            m, k = vol_matched_spy(spy, rf, s["Vol"])
            ms = stats(m, rf)
            d, lo, hi, p = boot_sharpe_diff(ret, spy, rf)
            vm.append(f"| {name} | {pct(s['CAGR'])} | {pct(ms['CAGR'])} | {pct(s['MaxDD'])} | {pct(ms['MaxDD'])} | {k:.2f} | {d:+.2f} | [{lo:+.2f}, {hi:+.2f}] | {p:.2f} |")
            row.update({"vm_spy_CAGR": ms["CAGR"], "vm_spy_MaxDD": ms["MaxDD"], "spy_scale": k,
                        "dSharpe": d, "dSharpe_lo": lo, "dSharpe_hi": hi, "p_boot_le0": p})
        rows.append(row)
    return "\n".join(lines + vm), rows


BENCH = "SPY buy & hold"


def main():
    syms = sorted(set(["SPY", CASH] + SECTORS + TREND_SET + ROT_SET + GTAA5))
    O, C = daily_panel(syms)
    rf = (C[CASH] / C[CASH].shift(1) - 1).fillna(0.0)
    strategies = [
        (BENCH, s_spy_bh),
        ("1. Trend: SPY 200d SMA / cash", s_sma200),
        ("2. Trend: TSMOM, original 10 ETFs", make_tsmom(TREND_SET)),
        ("3. Rotation: top-3 sectors", s_sector_rot),
        ("4. Rotation: dual momentum", s_dual_mom),
        ("5a. Mean rev: SPY RSI(2)", s_rsi2),
    ]
    robust = [
        (BENCH, s_spy_bh),
        ("2. TSMOM, original 10 ETFs", make_tsmom(TREND_SET)),
        ("2r. TSMOM, 10 sector SPDRs listed before 2017", make_tsmom(SECTORS_2017)),
        ("2r. TSMOM, Faber 2007 GTAA-5", make_tsmom(GTAA5)),
    ]
    last = C.index[-1]
    two_y = C.index[C.index >= last - pd.Timedelta(days=730)][0]
    md = [f"Daily data: Alpaca SIP adjusted, {C.index[0].date()} .. {last.date()}. Costs {COST_DAILY*1e4:.0f} bp/side. "
          f"Cash and Sharpe risk-free = BIL daily total return (BIL CAGR over window shown in the T-bill row of results.csv)."]
    flat = []
    for label, start in [(f"2017–2026: {SCORE_START} .. {last.date()}", pd.Timestamp(SCORE_START)),
                         (f"Last 2 years: {two_y.date()} .. {last.date()}", two_y)]:
        t, rows = report(run_window(strategies, O, C, rf, start), rf, label)
        md.append(t); flat += rows
        t, rows = report(run_window(robust, O, C, rf, start), rf, "Universe robustness, " + label)
        md.append(t); flat += [r for r in rows if r["strategy"] != BENCH]
        b = rf.loc[rf.index >= start]
        flat.append({"window": label, "strategy": "T-bills (BIL)", **stats(b, b)})
    if "--intraday" in sys.argv:
        daily, n, bh, (a, b, nd) = intraday()
        md.append(f"Intraday {a}..{b}: strategy {stats(daily, daily*0)}, SPY {stats(bh, bh*0)}, fills {n}")
    text = "\n\n".join(md)
    print(text)
    (HERE / "results.md").write_text(text + "\n")
    pd.DataFrame(flat).to_csv(HERE / "results.csv", index=False, float_format="%.6f")


if __name__ == "__main__":
    main()
