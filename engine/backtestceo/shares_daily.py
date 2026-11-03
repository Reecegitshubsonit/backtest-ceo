"""Replacement for the dead intraday share signals: daily-bar RSI / EMA mean-reversion on an ETF basket.

    python3 -m backtestceo.shares_daily

Train 2016-01-04 .. day before the 3-month test window; test = last 63 sessions (same as options_v2).
Signals are evaluated on the daily close and filled at that close (market-on-close; in live use the
signal is computed from the 15:55 price). Costs: 2 bp per side (slippage + fees, conservative for these ETFs).
Long only, max one position per ETF. Each trade is $5,000 notional; account $25,000, max 5 open.
"""
import itertools, json, math
from collections import defaultdict
from datetime import date

from . import options60 as o

UNIVERSE = ["SPY", "QQQ", "IWM", "DIA", "XLK", "XLF", "XLE", "XLV", "XLY", "XLP", "XLI", "XLU", "XLB", "SMH",
            "GLD", "TLT", "EEM", "EFA"]
COST = 0.0002
NOTIONAL, ACCOUNT, MAX_OPEN = 5_000.0, 25_000.0, 5
TEST_DAYS, MIN_TRADES = 63, 30
OUT = o.ROOT / "docs/backtests/options-v2"


def daily():
    raw = o.cached("daily-etf.json", lambda: o.bars("stocks", UNIVERSE, "2015-01-01T00:00:00Z",
                                                     f"{o.END}T23:59:00Z", tf="1Day", adjustment="all"))
    out = {}
    for s, rows in raw.items():
        out[s] = [dict(d=o.ts(r["t"]).date().isoformat(), o=r["o"], h=r["h"], l=r["l"], c=r["c"]) for r in rows]
    return out


def add_ind(rows):
    e5 = e10 = e20 = e50 = e200 = None; g2 = l2 = g14 = l14 = None; prev = None; closes = []
    for r in rows:
        c = r["c"]; closes.append(c)
        e = lambda p, n: c if p is None else p + 2 / (n + 1) * (c - p)
        e5, e10, e20, e50, e200 = e(e5, 5), e(e10, 10), e(e20, 20), e(e50, 50), e(e200, 200)
        if prev is not None:
            up, dn = max(c - prev, 0), max(prev - c, 0)
            g2 = up if g2 is None else (g2 + up) / 2; l2 = dn if l2 is None else (l2 + dn) / 2
            g14 = up if g14 is None else (g14 * 13 + up) / 14; l14 = dn if l14 is None else (l14 * 13 + dn) / 14
        rs = lambda g, l: 50 if g is None else (100 if l == 0 else 100 - 100 / (1 + g / l))
        r.update(e5=e5, e10=e10, e20=e20, e50=e50, e200=e200, rsi2=rs(g2, l2), rsi14=rs(g14, l14),
                 sma200=sum(closes[-200:]) / min(len(closes), 200), sma5=sum(closes[-5:]) / min(len(closes), 5),
                 ibs=(c - r["l"]) / (r["h"] - r["l"]) if r["h"] > r["l"] else 0.5,
                 down=(r.get("down", 0)), n=len(closes))
        r["down"] = 0
        prev = c
    for i in range(1, len(rows)):
        rows[i]["down"] = rows[i - 1]["down"] + 1 if rows[i]["c"] < rows[i - 1]["c"] else 0
    return rows


# entry(r, p, k) -> bool ; exit(r, k, held) -> bool ; k = threshold param
STRATS = {
    "RSI(2) pullback in uptrend (Connors)": (
        lambda r, p, k: r["n"] > 200 and r["c"] > r["sma200"] and r["rsi2"] < k,
        lambda r, k, h: r["c"] > r["sma5"] or h >= 10, [5, 10, 15]),
    "EMA200 trend + close below EMA5 by k% (EMA snap-back)": (
        lambda r, p, k: r["n"] > 200 and r["c"] > r["e200"] and r["c"] < r["e5"] * (1 - k / 100),
        lambda r, k, h: r["c"] > r["e5"] or h >= 10, [0.5, 1.0, 1.5]),
    "IBS < k in uptrend, 1-3 day hold": (
        lambda r, p, k: r["n"] > 200 and r["c"] > r["sma200"] and r["ibs"] < k,
        lambda r, k, h: r["ibs"] > 0.7 or h >= 3, [0.1, 0.15, 0.2]),
    "k down closes above EMA200": (
        lambda r, p, k: r["n"] > 200 and r["c"] > r["e200"] and r["down"] >= k,
        lambda r, k, h: r["c"] > r["sma5"] or h >= 10, [3, 4]),
    "RSI(2) < k AND IBS < 0.25 in uptrend": (
        lambda r, p, k: r["n"] > 200 and r["c"] > r["sma200"] and r["rsi2"] < k and r["ibs"] < 0.25,
        lambda r, k, h: r["c"] > r["sma5"] or r["ibs"] > 0.8 or h >= 5, [10, 20, 30]),
    "RSI(14) < k above EMA50 (trend pullback)": (
        lambda r, p, k: r["n"] > 200 and r["c"] > r["e50"] and r["e50"] > r["e200"] and r["rsi14"] < k,
        lambda r, k, h: r["rsi14"] > 55 or h >= 10, [40, 45]),
}


def backtest(data, name, k, d0, d1):
    entry, exit_, _ = STRATS[name]
    cands = defaultdict(list)                        # day -> [(rsi2 rank, sym, idx)]
    for s, rows in data.items():
        for i in range(1, len(rows)):
            r = rows[i]
            if d0 <= r["d"] <= d1 and entry(r, rows[i - 1], k): cands[r["d"]].append((r["rsi2"], s, i))
    alldays = sorted({r["d"] for rows in data.values() for r in rows if d0 <= r["d"] <= d1})
    idx = {s: {r["d"]: i for i, r in enumerate(rows)} for s, rows in data.items()}
    open_, trades = {}, []
    for d in alldays:
        for s in list(open_):
            i0 = open_[s]; i = idx[s].get(d)
            if i is None or i <= i0: continue
            r = data[s][i]
            if exit_(r, k, i - i0) or d == alldays[-1]:
                ep, xp = data[s][i0]["c"], r["c"]; q = NOTIONAL / ep
                cost = COST * (ep + xp) * q
                trades.append(dict(day=d, sym=s, pnl=(xp - ep) * q - cost, cost=cost, entry_day=data[s][i0]["d"]))
                del open_[s]
        for _, s, i in sorted(cands.get(d, [])):
            if len(open_) >= MAX_OPEN: break
            if s not in open_: open_[s] = i
    return trades, alldays


def metrics(trades, days):
    m = o.metrics(trades, days)
    if not m["trades"]: return m
    daily_ = defaultdict(float)
    for t in trades: daily_[t["day"]] += t["pnl"]
    r = [daily_.get(d, 0) / ACCOUNT for d in days]; mu = sum(r) / len(r)
    sd = math.sqrt(sum((x - mu) ** 2 for x in r) / (len(r) - 1))
    m.update(sharpe=mu / sd * math.sqrt(252) if sd else 0, ret=sum(r), worst=min(t["pnl"] for t in trades))
    return m


def main():
    data = {s: add_ind(rows) for s, rows in daily().items()}
    days = sorted({r["d"] for r in data["SPY"]})
    test0 = days[-TEST_DAYS]; train_end = days[-TEST_DAYS - 1]
    rows = []
    for name, (_, _, ks) in STRATS.items():
        best = None
        for k in ks:
            tr, ds = backtest(data, name, k, "2016-01-04", train_end)
            m = metrics(tr, ds)
            if m["trades"] >= MIN_TRADES and (best is None or m["sharpe"] > best[1]["sharpe"]): best = (k, m)
        k, mtr = best
        tt, ds = backtest(data, name, k, test0, days[-1])
        mte = metrics(tt, ds)
        ok = mte.get("trades", 0) >= MIN_TRADES and mte.get("exp", -1) > 0 and mte.get("sharpe", 0) > 1
        rows.append(dict(name=f"{name} (k={k})", train=mtr, test=mte, ok=ok, trades=tt))
    L = ["## Daily ETF signals on shares (replacement for the dead intraday share signals)", "",
         f"Universe {len(UNIVERSE)} ETFs. Train 2016-01-04..{train_end}; test {test0}..{days[-1]} ({TEST_DAYS} sessions). "
         f"$5k per trade, max 5 open, $25k account, 2 bp/side cost, market-on-close fills.", "",
         "| Strategy | Train trades | Train win % | Train exp $ | Train Sharpe | Test trades | Test win % | Test exp $ | "
         "Test total $ | Test max DD $ | Test Sharpe | Verdict |", "|---|" + "---:|" * 10 + "---|"]
    for r in rows:
        a, b = r["train"], r["test"]
        L.append(f"| {r['name']} | {a['trades']} | {a['win']:.1%} | {a['exp']:.2f} | {a['sharpe']:.2f} | {b.get('trades',0)} | "
                 + (f"{b['win']:.1%} | {b['exp']:.2f} | {b['total']:.0f} | {b['mdd']:.0f} | {b['sharpe']:.2f} | " if b.get("trades") else "- | - | - | - | - | ")
                 + ("PASS" if r["ok"] else "FAIL") + " |")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "shares_daily.md").write_text("\n".join(L) + "\n")
    with open(OUT / "shares_trades.csv", "w") as fh:
        fh.write("strategy,entry_day,exit_day,symbol,pnl,cost\n")
        for r in rows:
            for t in r["trades"]: fh.write(f"\"{r['name']}\",{t['entry_day']},{t['day']},{t['sym']},{t['pnl']:.2f},{t['cost']:.2f}\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
