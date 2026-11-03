"""Where do the candidate strategies make and lose money, and do they make it where their thesis says they should?
Descriptive only (full-sample buckets are fine here because nothing is traded on them).
Run: python3 research/etf_strategies/diagnostics.py  -> diagnostics.md"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import backtest as bt
import new_strategies as ns
import intraday as it

P = lambda x: f"{x*100:+.1f}%"


def episodes(px, thresh=0.10):
    """SPY drawdowns deeper than thresh: (peak, trough, recovery-or-None)."""
    out, peak_i, in_dd = [], px.index[0], False
    peak = px.iloc[0]
    for d, v in px.items():
        if v >= peak:
            if in_dd and (peak / px.loc[peak_i:d].min() - 1) and px.loc[peak_i:d].min() / peak - 1 <= -thresh:
                out.append((peak_i, px.loc[peak_i:d].idxmin(), d))
            peak, peak_i, in_dd = v, d, False
        else:
            in_dd = True
    if in_dd and px.loc[peak_i:].min() / peak - 1 <= -thresh:
        out.append((peak_i, px.loc[peak_i:].idxmin(), None))
    return out


def comp(r, a, b):
    s = r.loc[(r.index > a) & (r.index <= b)]
    return (1 + s).prod() - 1


def daily_section(name, ret, spy, exposure, thesis):
    L = [f"## {name}", "", f"**Thesis (when it should make money vs SPY):** {thesis}", "",
         "| SPY drawdown episode | SPY fall | Strategy in fall | SPY recovery leg | Strategy in recovery | Net vs SPY over episode |",
         "|---|---:|---:|---:|---:|---:|"]
    px = (1 + spy).cumprod()
    for pk, tr, rc in episodes(px):
        end = rc or spy.index[-1]
        f_s, f_x = comp(spy, pk, tr), comp(ret, pk, tr)
        r_s, r_x = comp(spy, tr, end), comp(ret, tr, end)
        net = (1 + f_x) * (1 + r_x) - (1 + f_s) * (1 + r_s)
        L.append(f"| {pk.date()} → {tr.date()} → {rc.date() if rc else 'ongoing'} | {P(f_s)} | {P(f_x)} | {P(r_s)} | {P(r_x)} | {P(net)} |")
    # exposure buckets: SPY's own return/vol by the strategy's exposure that day
    b = pd.cut(exposure, [-0.01, 0.01, 0.6, 0.9, 1.1, 1.5, 2.01], labels=["0 (cash)", "0-0.6", "0.6-0.9", "0.9-1.1", "1.1-1.5", "1.5-2"])
    df = pd.DataFrame({"spy": spy, "ret": ret, "b": b}).dropna()
    L += ["", "| Exposure | Days | SPY ann. return those days | SPY ann. vol those days | SPY Sharpe-like | Strategy P&L contribution |", "|---|---:|---:|---:|---:|---:|"]
    for k, g in df.groupby("b", observed=True):
        mu, sd = g.spy.mean() * 252, g.spy.std() * np.sqrt(252)
        L.append(f"| {k} | {len(g)} | {P(mu)} | {sd*100:.1f}% | {mu/sd if sd else 0:.2f} | {P(g.ret.sum())} |")
    return L


def out_periods(exposure, spy):
    """Contiguous spells at zero exposure: SPY return while out. Positive = gain missed; negative = loss avoided."""
    spells, cur = [], None
    for d, e in exposure.items():
        if e < 0.01 and cur is None: cur = d
        if e >= 0.01 and cur is not None: spells.append((cur, d)); cur = None
    if cur is not None: spells.append((cur, exposure.index[-1]))
    rows = [(a, b, comp(spy, a - pd.Timedelta(days=1), b)) for a, b in spells]
    return rows


def intraday_section(name, trades, day_oc, thesis, keys):
    df = pd.DataFrame([{"date": d, "r": r, **info} for d, r, info in trades])
    df["period"] = np.where(df.date < "2024-01-01", "2016-23", "2024+")
    df["oc"] = df.date.map(day_oc)
    df["absq"] = pd.qcut(df.oc.abs(), 5, labels=["Q1 quiet", "Q2", "Q3", "Q4", "Q5 trend"])
    df["aligned"] = np.sign(df.oc) == df.side
    L = [f"## {name}", "", f"**Thesis:** {thesis}", ""]
    def table(col, title):
        t = df.pivot_table(index=col, columns="period", values="r", aggfunc=["count", "sum", "mean"], observed=True)
        rows = [f"**By {title}**", "", "| " + title + " | Trades 16-23 | Sum P&L 16-23 | Avg bp 16-23 | Trades 24+ | Sum P&L 24+ | Avg bp 24+ |", "|---|---:|---:|---:|---:|---:|---:|"]
        for k in t.index:
            g = lambda f, p: t[(f, p)].get(k, np.nan) if (f, p) in t.columns else np.nan
            rows.append(f"| {k} | {g('count','2016-23'):.0f} | {P(g('sum','2016-23'))} | {g('mean','2016-23')*1e4:+.1f} | {g('count','2024+'):.0f} | {P(g('sum','2024+'))} | {g('mean','2024+')*1e4:+.1f} |")
        return rows + [""]
    for col, title in keys + [("absq", "day's |open→close| quintile"), ("aligned", "trade side matches day's open→close direction")]:
        L += table(col, title)
    # the core expectation check: profit on trend-aligned big days, small loss elsewhere
    big = df[df.absq == "Q5 trend"]
    L.append(f"Trend days (top quintile |open→close|) share of trades: {len(big)/len(df)*100:.0f}%; "
             f"their P&L 2016-23 {P(big[big.period=='2016-23'].r.sum())}, 2024+ {P(big[big.period=='2024+'].r.sum())}; "
             f"all other days 2016-23 {P(df[(df.absq!='Q5 trend')&(df.period=='2016-23')].r.sum())}, 2024+ {P(df[(df.absq!='Q5 trend')&(df.period=='2024+')].r.sum())}.")
    return L, df


def main():
    syms = sorted(set(["SPY", "SSO", "UPRO", bt.CASH]))
    O, C = bt.daily_panel(syms)
    rf = (C[bt.CASH] / C[bt.CASH].shift(1) - 1).fillna(0.0)
    start = pd.Timestamp(bt.SCORE_START)
    res = bt.run_window([(bt.BENCH, ns.spy_bh), ("N1", ns.s_voltarget), ("T1", bt.s_sma200)], O, C, rf, start)
    spy = res[bt.BENCH][0]
    md = ["# Diagnostics: where the candidates make and lose money", "",
          "Daily section: 2017-01-03 .. latest, same engine/costs as the backtests. Intraday section: 0.5 bp/side main case.", ""]

    # N1 vol target
    e_n1 = ns.s_voltarget(C).ffill()
    e_n1 = (e_n1["SPY"] + 2 * e_n1["SSO"]).shift(1).reindex(spy.index).fillna(0)   # held the day after the signal
    md += daily_section("N1 vol target 15% (SPY/SSO, ≤2x)", res["N1"][0], spy, e_n1,
                        "Volatility clusters, and high-vol periods have worse return per unit of risk. Cutting exposure as vol rises "
                        "should lose less in slow-building selloffs. Levering up in calm markets should earn more than SPY. "
                        "It should LOSE vs SPY in V-shaped crashes: it de-levers after the drop and misses the rebound.")
    cuts = e_n1[(e_n1 < 0.6) & (e_n1.shift(1) >= 0.6)]
    md += ["", "**Exposure-cut events (exposure falls below 0.6): next 21 sessions**", "",
           "| Date | Exposure | SPY next 21d | N1 next 21d | Missed |", "|---|---:|---:|---:|---:|"]
    for d, e in cuts.items():
        i = spy.index.get_loc(d); w = spy.index[i:i + 21]
        s_, n_ = (1 + spy.loc[w]).prod() - 1, (1 + res["N1"][0].loc[w]).prod() - 1
        md.append(f"| {d.date()} | {e:.2f} | {P(s_)} | {P(n_)} | {P(n_ - s_)} |")
    md.append("")

    # T1 200d SMA
    e_t1 = bt.s_sma200(C)["SPY"].shift(1).reindex(spy.index).fillna(0)
    md += daily_section("1. SPY 200d SMA / T-bills", res["T1"][0], spy, e_t1,
                        "Bear markets are slow enough for a 200-day filter to exit before most of the fall and re-enter after the low. "
                        "It should beat SPY in long declines (2022) and LOSE in fast V-shapes (2018 Q4, 2020, 2025) and in chop "
                        "around the average (whipsaw).")
    spells = out_periods(e_t1, spy)
    missed = sum(x for *_, x in spells if x > 0); avoided = sum(x for *_, x in spells if x < 0)
    md += ["", f"**Out-of-market spells:** {len(spells)}. SPY gains missed while out (sum): {P(missed)}; SPY losses avoided (sum): {P(avoided)}.",
           f"Spells that cost money (SPY rose while out): {sum(1 for *_, x in spells if x > 0)} of {len(spells)}. Largest five:", "",
           "| Out from | Back in | SPY while out |", "|---|---|---:|"]
    for a, b, x in sorted(spells, key=lambda s: -abs(s[2]))[:8]:
        md.append(f"| {a.date()} | {b.date()} | {P(x)} |")
    md.append("")

    # intraday
    spy_d, qqq_d = it.load("SPY"), it.load("QQQ")
    oc = lambda days: pd.Series({d: g["c"].iloc[-1] / g["o"].iloc[0] - 1 for d, g in days.items()})
    _, tr1 = it.i1(spy_d, True)
    L, df1 = intraday_section("I1b noise boundary SPY (≤4x)", tr1, oc(spy_d),
        "Intraday momentum. When price leaves the noise band, the day is more likely to keep trending. Most profit should come from "
        "large open→close days with the trade on the right side. Quiet days should cost only small stop-outs.",
        [("side", "side (1 long, -1 short)"), ("exit", "exit"),
         ("entry_hour", "entry hour")] )
    md += L + [""]
    _, tr2 = it.i2(qqq_d, True)
    L, df2 = intraday_section("I2b ORB 5-min QQQ (1% risk, ≤4x)", tr2, oc(qqq_d),
        "The first 5-min candle's direction persists on trend days. Small losses (stop at the candle's other end) and rare large wins "
        "(10R target or a strong close) should give positive skew. Profit should be concentrated in big trend-aligned days.",
        [("side", "side (1 long, -1 short)"), ("exit", "exit")])
    md += L
    text = "\n".join(md)
    (bt.HERE / "diagnostics.md").write_text(text + "\n")
    print(text)


if __name__ == "__main__":
    # I1 records entry bar index; expose entry hour for the table
    _i1 = it.i1
    def i1_hours(days, levered):
        p, trs = _i1(days, levered)
        out = []
        for d, r, info in trs:
            info = dict(info); info["entry_hour"] = f"{(570 + 5 * info['entry_k']) // 60:02d}:00" if "entry_k" in info else "n/a"
            out.append((d, r, info))
        return p, out
    it.i1 = i1_hours
    main()
