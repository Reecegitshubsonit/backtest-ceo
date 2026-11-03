"""Round 4: published intraday strategies on 5-min SIP bars, 2016-2026. Read-only data, no orders.

I1 Noise-boundary intraday momentum, SPY (Zarattini, Aziz, Barbon 2024, 'Beat the Market').
I2 5-minute opening-range breakout, QQQ (Zarattini, Barbon, Aziz 2023, 'Can Day Trading Really Be Profitable?').
I3 Intraday momentum: first half-hour predicts last half-hour, SPY (Gao, Han, Li, Zhou 2018, JFE).
Paper parameters, not tuned here. Flat every night; capital earns BIL overnight, so Sharpe (excess of BIL) = Sharpe of trading P&L.
Costs: 0.5 bp per side on traded notional, main case (SPY/QQQ 1-cent spread ~0.13-0.17 bp; papers assumed ~0.06 bp);
sensitivity 0-2 bp reported. Fills: next bar open
after a decision bar's close; stops at the stop price, or the bar's open if it gapped through; stop wins ties with target.

Pre-declared pass rule: net Sharpe above SPY buy-and-hold in BOTH 2016-2023 and 2024-01..2026-07; the last 3 months
(2026-08-03 .. ) are a holdout scored once, not used to choose or tune anything.
Run: python3 research/etf_strategies/intraday.py  -> intraday_results.md / .csv
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import backtest as bt
import new_strategies as ns

COST = 0.00005         # 0.5 bp/side main case (see README: chosen after seeing 2 bp results; sensitivity table shows 0-2 bp)
COST_GRID = [0.0, 0.000025, 0.00005, 0.0001, 0.0002]
MAX_LEV = 4.0          # FINRA pattern-day-trader intraday buying power
WINDOWS = [("2016-2023 (overlaps papers' samples)", "2016-02-01", "2023-12-31"),
           ("2024-01 .. 2026-07 (post-publication)", "2024-01-01", "2026-07-31"),
           ("Holdout: last 3 months", "2026-08-03", None),
           ("Full 2016-2026", "2016-02-01", None)]


def load(sym):
    d = bt.fetch(sym, "5Min", "2016-01-01")
    d.index = d.index.tz_convert("America/New_York")
    d = d.between_time("09:30", "15:55")
    d["date"] = pd.to_datetime(d.index.date)
    d["k"] = ((d.index.hour * 60 + d.index.minute) - 570) // 5      # bar index 0..77 from 09:30
    days = {}
    for dt, g in d.groupby("date"):
        if g["k"].iloc[0] != 0 or len(g) < 40: continue               # need the opening bar; skip broken days
        g = g.set_index("k").reindex(range(g["k"].iloc[-1] + 1)).ffill()  # fill rare missing bars inside the day
        days[dt] = g
    return days


def daily_sigma(days):
    closes = pd.Series({dt: g["c"].iloc[-1] for dt, g in days.items()})
    return closes, closes.pct_change().rolling(14).std().shift(1)   # known before the open


# ---------- I1 noise boundary ----------
def i1(days, levered):
    dates = list(days)
    closes, sig_d = daily_sigma(days)
    moves = pd.DataFrame({dt: (g["c"] / g["o"].iloc[0] - 1).abs().reindex(range(78)) for dt, g in days.items()}).T
    sig_t = moves.rolling(14, min_periods=14).mean().shift(1)            # same time-of-day, prior 14 sessions
    pnl, trades = {}, []
    for j, dt in enumerate(dates):
        if j == 0 or sig_t.loc[dt].isna().all() or np.isnan(sig_d.loc[dt]): continue
        g = days[dt]; n = len(g)
        o0, pc = g["o"].iloc[0], closes.iloc[j - 1]
        s = sig_t.loc[dt].values[:n]
        ub = max(o0, pc) * (1 + s); lb = min(o0, pc) * (1 - s)
        tp = (g["h"] + g["l"] + g["c"]) / 3
        vwap = ((tp * g["v"]).cumsum() / g["v"].cumsum()).values
        c, o = g["c"].values, g["o"].values
        lev = min(MAX_LEV, 0.02 / sig_d.loc[dt]) if levered else 1.0
        pos, entry, day = 0, 0.0, 0.0
        for k in range(5, n - 1):
            if (k + 1) % 6 != 0: continue                               # decision on bars ending at :00 / :30
            new = pos
            if pos == 1 and c[k] < max(ub[k], vwap[k]): new = 0
            if pos == -1 and c[k] > min(lb[k], vwap[k]): new = 0
            if new == 0:
                if c[k] > ub[k]: new = 1
                elif c[k] < lb[k]: new = -1
            if new != pos:
                px = o[k + 1]
                if pos != 0:
                    r = lev * pos * (px / entry - 1) - 2 * COST * lev; day += r; trades.append((dt, r))
                if new != 0: entry = px
                pos = new
        if pos != 0:
            r = lev * pos * (c[-1] / entry - 1) - 2 * COST * lev; day += r; trades.append((dt, r))
        pnl[dt] = day
    return pd.Series(pnl), trades


# ---------- I2 opening-range breakout ----------
def i2(days, levered):
    pnl, trades = {}, []
    for dt, g in days.items():
        o, h, l, c = g["o"].values, g["h"].values, g["l"].values, g["c"].values
        day = 0.0
        if c[0] != o[0] and len(g) > 2:
            side = 1 if c[0] > o[0] else -1
            entry = o[1]; stop = l[0] if side == 1 else h[0]
            R = (entry - stop) * side
            if R > 0:
                target = entry + side * 10 * R
                lev = min(MAX_LEV, 0.01 / (R / entry)) if levered else 1.0
                exit_px = c[-1]
                for k in range(1, len(g)):
                    if side == 1:
                        if l[k] <= stop: exit_px = min(o[k], stop); break
                        if h[k] >= target: exit_px = max(o[k], target); break
                    else:
                        if h[k] >= stop: exit_px = max(o[k], stop); break
                        if l[k] <= target: exit_px = min(o[k], target); break
                day = lev * side * (exit_px / entry - 1) - 2 * COST * lev
                trades.append((dt, day))
        pnl[dt] = day
    return pd.Series(pnl), trades


# ---------- I3 first half-hour -> last half-hour ----------
def i3(days):
    dates = list(days); closes = pd.Series({dt: g["c"].iloc[-1] for dt, g in days.items()})
    pnl, trades = {}, []
    for j, dt in enumerate(dates):
        g = days[dt]; day = 0.0
        if j > 0 and len(g) == 78:
            r1 = g["c"].iloc[5] / closes.iloc[j - 1] - 1                 # prev close -> 10:00
            if r1 != 0:
                side = np.sign(r1)
                day = side * (g["c"].iloc[-1] / g["o"].iloc[72] - 1) - 2 * COST   # 15:30 open -> 16:00 close
                trades.append((dt, day))
        pnl[dt] = day
    return pd.Series(pnl), trades


def main():
    global COST
    spy, qqq = load("SPY"), load("QQQ")
    O, C = bt.daily_panel(["SPY", bt.CASH])
    rf = (C[bt.CASH] / C[bt.CASH].shift(1) - 1).fillna(0.0)
    spy_ret = (C["SPY"] / C["SPY"].shift(1) - 1)
    strats = {
        "I1a. Noise boundary SPY, 1x": i1(spy, False),
        "I1b. Noise boundary SPY, vol-sized ≤4x (paper)": i1(spy, True),
        "I2a. ORB 5-min QQQ, 1x": i2(qqq, False),
        "I2b. ORB 5-min QQQ, 1% risk ≤4x (paper)": i2(qqq, True),
        "I3. First → last half-hour SPY, 1x": i3(spy),
    }
    m = 12 + len(strats)
    md = [f"Intraday strategies, 5-min SIP bars. Costs {COST*1e4:g} bp/side × leverage (main case). Capital earns BIL overnight. "
          f"Holm m = {m} (all strategy-vs-SPY tests in the project)."]
    flat = []
    for label, a, b in WINDOWS:
        lines = [f"### {label}: {a} .. {b or C.index[-1].date()}", "",
                 "| Strategy | CAGR | Vol | Sharpe | Max DD | Longest DD (d) | Trades | Win % | Avg trade | ΔSharpe vs SPY [95% CI] | p (one-sided) | Holm p |",
                 "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
        sl = lambda s: s.loc[(s.index >= a) & ((s.index <= b) if b else True)]
        bench = sl(spy_ret.dropna()); r_f = rf.reindex(bench.index).fillna(0)
        s0 = bt.stats(bench, r_f)
        lines.append(f"| SPY buy & hold | {s0['CAGR']*100:.1f}% | {s0['Vol']*100:.1f}% | {s0['Sharpe']:.2f} | {s0['MaxDD']*100:.1f}% | {s0['LongestDD_days']} | 1 | | | | | |")
        rows = []
        for name, (pnl, trades) in strats.items():
            p = sl(pnl).reindex(bench.index).fillna(0.0)
            tot = p + r_f
            s = bt.stats(tot, r_f)
            d, lo, hi, pv = bt.boot_sharpe_diff(tot, bench, r_f)
            tw = [r for dd, r in trades if dd >= pd.Timestamp(a) and (b is None or dd <= pd.Timestamp(b))]
            rows.append((name, s, d, lo, hi, pv, tw))
        adj = ns.holm(np.r_[[r[5] for r in rows], np.ones(m - len(rows))])[:len(rows)]
        for (name, s, d, lo, hi, pv, tw), ap in zip(rows, adj):
            win = np.mean(np.array(tw) > 0) * 100 if tw else 0
            avg = np.mean(tw) * 1e4 if tw else 0
            lines.append(f"| {name} | {s['CAGR']*100:.1f}% | {s['Vol']*100:.1f}% | {s['Sharpe']:.2f} | {s['MaxDD']*100:.1f}% | {s['LongestDD_days']} | {len(tw)} | {win:.0f}% | {avg:+.1f} bp | {d:+.2f} [{lo:+.2f}, {hi:+.2f}] | {pv:.3f} | {ap:.3f} |")
            flat.append({"window": label, "strategy": name, **s, "trades": len(tw), "win_rate": win / 100,
                         "avg_trade_bp": avg, "dSharpe": d, "dSharpe_lo": lo, "dSharpe_hi": hi, "p": pv, "holm_p": ap})
        md.append("\n".join(lines))
    # cost sensitivity: Sharpe (excess of BIL) by window and cost level
    main_cost = COST
    sens = ["### Cost sensitivity: Sharpe by window (SPY buy & hold: " + ", ".join(
        f"{lab.split(' (')[0]} {bt.stats(spy_ret.dropna().loc[(spy_ret.dropna().index >= a) & ((spy_ret.dropna().index <= b) if b else True)], rf)['Sharpe']:.2f}"
        for lab, a, b in WINDOWS) + ")", "",
        "| Strategy | bp/side | " + " | ".join(w[0].split(' (')[0] for w in WINDOWS) + " |", "|---|---:|" + "---:|" * len(WINDOWS)]
    fns = {"I1a": lambda: i1(spy, False), "I1b": lambda: i1(spy, True), "I2a": lambda: i2(qqq, False),
           "I2b": lambda: i2(qqq, True), "I3": lambda: i3(spy)}
    for key, fn in fns.items():
        for cst in COST_GRID:
            COST = cst
            pnl, _ = fn()
            cells = []
            for lab, a, b in WINDOWS:
                p = pnl.loc[(pnl.index >= a) & ((pnl.index <= b) if b else True)]
                cells.append(f"{p.mean() / p.std() * np.sqrt(252):.2f}" if p.std() > 0 else "n/a")
            sens.append(f"| {key} | {cst*1e4:g} | " + " | ".join(cells) + " |")
    COST = main_cost
    md.append("\n".join(sens))
    out = "\n\n".join(md)
    print(out)
    (bt.HERE / "intraday_results.md").write_text(out + "\n")
    pd.DataFrame(flat).to_csv(bt.HERE / "intraday_results.csv", index=False, float_format="%.6f")


if __name__ == "__main__":
    main()
