"""Last-3-months run of every daily strategy (rounds 2-3) under the same engine/costs/T-bill cash.
Run: python3 research/etf_strategies/three_month.py  -> three_month_results.md"""
import sys
from pathlib import Path
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent))
import backtest as bt, new_strategies as ns

def main():
    syms = sorted(set(["SPY", bt.CASH, "SSO", "UPRO"] + bt.SECTORS + bt.TREND_SET + bt.ROT_SET + bt.GTAA5))
    O, C = bt.daily_panel(syms)
    rf = (C[bt.CASH] / C[bt.CASH].shift(1) - 1).fillna(0.0)
    last = C.index[-1]
    start = C.index[C.index >= last - pd.DateOffset(months=3)][0]
    strats = [(bt.BENCH, bt.s_spy_bh), ("1. SPY 200d SMA / cash", bt.s_sma200), ("2. TSMOM 10 ETFs", bt.make_tsmom(bt.TREND_SET)),
              ("2r. TSMOM sectors pre-2017", bt.make_tsmom(bt.SECTORS_2017)), ("2r. TSMOM GTAA-5", bt.make_tsmom(bt.GTAA5)),
              ("3. Top-3 sectors", bt.s_sector_rot), ("4. Dual momentum", bt.s_dual_mom), ("5a. RSI(2)", bt.s_rsi2)]
    strats += [s for s in ns.STRATS if s[0] != bt.BENCH]
    res = bt.run_window(strats, O, C, rf, start)
    rows = []
    for name, (r, tr) in res.items():
        s = bt.stats(r, rf)
        rows.append(f"| {name} | {((1+r).prod()-1)*100:.1f}% | {s['Vol']*100:.1f}% | {s['Sharpe']:.2f} | {s['MaxDD']*100:.1f}% | {tr['round_trips']} (+{tr['open_at_end']}) |")
    text = (f"### Last 3 months: {start.date()} .. {last.date()} ({len(res[bt.BENCH][0])} sessions)\n\n"
            "| Strategy | Return (not annualized) | Vol | Sharpe | Max DD | Round trips |\n|---|---:|---:|---:|---:|---:|\n" + "\n".join(rows))
    print(text); (bt.HERE / "three_month_results.md").write_text(text + "\n")

if __name__ == "__main__":
    main()
