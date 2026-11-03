"""Option 3: judge the risk-shape strategies on the goal they are built for: more return for the same max drawdown.
Benchmark = SPY scaled (daily, frictionless, rest in T-bills) to the SAME max drawdown as the strategy over the window.
Pre-declared pass rule: strategy CAGR > drawdown-matched SPY CAGR in BOTH halves (2017-21, 2022-26).
Bootstrap (21-day blocks, 5000 paths): P(strategy CAGR > SPY scaled by the same k). No bootstrap of max DD: shuffling blocks
destroys the timing that makes a timing strategy's drawdown shallow, so that number would be meaningless.
Run: python3 research/etf_strategies/drawdown_goal.py -> drawdown_goal.md"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent))
import backtest as bt, new_strategies as ns


def mdd(r):
    eq = np.cumprod(1 + r, axis=-1)
    return (eq / np.maximum.accumulate(eq, axis=-1) - 1).min(axis=-1)


def cagr(r):
    return np.prod(1 + r, axis=-1) ** (252 / r.shape[-1]) - 1


def ulcer(r):
    eq = np.cumprod(1 + r); dd = eq / np.maximum.accumulate(eq) - 1
    return np.sqrt(np.mean(dd ** 2))


def dd_match_k(spy, rf, target):
    lo, hi = 0.0, 3.0
    for _ in range(60):
        k = (lo + hi) / 2
        if mdd(rf + k * (spy - rf)) > target: lo = k
        else: hi = k
    return (lo + hi) / 2


def boot(strat, spy, rf, k, n=5000, block=21, seed=7):
    rng = np.random.default_rng(seed); T = len(strat); nb = int(np.ceil(T / block))
    idx = ((rng.integers(0, T, (n, nb))[:, :, None] + np.arange(block)) % T).reshape(n, -1)[:, :T]
    s, m = strat[idx], (rf + k * (spy - rf))[idx]
    return (cagr(s) > cagr(m)).mean(), (mdd(s) > mdd(m)).mean(), np.percentile(cagr(s) - cagr(m), [2.5, 97.5])


def static_mix(w):
    def f(C):
        x = pd.DataFrame(np.nan, index=C.index, columns=["SPY"]); x[bt.month_end_mask(C.index)] = w
        x.iloc[0] = w
        return x
    return f


def main():
    O, C = bt.daily_panel(sorted(set(["SPY", "SSO", "UPRO", bt.CASH] + bt.TREND_SET + bt.GTAA5)))
    rf_all = (C[bt.CASH] / C[bt.CASH].shift(1) - 1).fillna(0.0)
    strats = [(bt.BENCH, bt.s_spy_bh), ("N1. Vol target 15%", ns.s_voltarget), ("N5. Trend × vol target", ns.s_trend_voltarget),
              ("1. SPY 200d SMA / cash", bt.s_sma200), ("2. TSMOM original 10", bt.make_tsmom(bt.TREND_SET)),
              ("2r. TSMOM GTAA-5", bt.make_tsmom(bt.GTAA5)), ("60% SPY / 40% T-bills, monthly", static_mix(0.6))]
    res = bt.run_window(strats, O, C, rf_all, pd.Timestamp(bt.SCORE_START))
    spy_full = res[bt.BENCH][0]
    wins = [("2017–2026", "2017-01-03", None), ("2017–2021", "2017-01-03", "2021-12-31"), ("2022–2026", "2022-01-03", None)]
    md = ["# Option 3: return for the same max drawdown", "",
          "Drawdown-matched SPY = SPY scaled down to the strategy's max DD in that window (rest in T-bills, rebalanced daily, no costs: "
          "slightly flatters SPY). Note: k is fitted in-window to the strategy's realized max DD, so this is a description, not a tradable benchmark.", ""]
    verdict = {}
    for lab, a, b in wins:
        md += [f"### {lab}", "", "| Strategy | CAGR | Max DD | Calmar | Ulcer | DD-matched SPY k | DD-matched SPY CAGR | ΔCAGR | ΔCAGR 95% CI | P(boot CAGR > SPY·k) |",
               "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
        sl = lambda s: s.loc[(s.index >= a) & ((s.index <= b) if b else True)].values
        spy, rf = sl(spy_full), sl(rf_all.reindex(spy_full.index))
        for name, (r, _) in res.items():
            x = sl(r); c, d = cagr(x), mdd(x)
            if name == bt.BENCH:
                md.append(f"| {name} | {c*100:.1f}% | {d*100:.1f}% | {c/-d:.2f} | {ulcer(x)*100:.1f} | 1.00 | | | | |"); continue
            k = dd_match_k(spy, rf, d); m = rf + k * (spy - rf)
            pc, pd_, ci = boot(x, spy, rf, k)
            md.append(f"| {name} | {c*100:.1f}% | {d*100:.1f}% | {c/-d:.2f} | {ulcer(x)*100:.1f} | {k:.2f} | {cagr(m)*100:.1f}% | {(c-cagr(m))*100:+.1f} pts | [{ci[0]*100:+.1f}, {ci[1]*100:+.1f}] | {pc:.2f} |")
            verdict.setdefault(name, {})[lab] = c - cagr(m)
        md.append("")
    md += ["### Pass rule (beat DD-matched SPY CAGR in both halves)", "", "| Strategy | 2017–21 | 2022–26 | Pass |", "|---|---:|---:|---|"]
    for name, v in verdict.items():
        ok = v["2017–2021"] > 0 and v["2022–2026"] > 0
        md.append(f"| {name} | {v['2017–2021']*100:+.1f} pts | {v['2022–2026']*100:+.1f} pts | {'yes' if ok else 'no'} |")
    text = "\n".join(md); print(text); (bt.HERE / "drawdown_goal.md").write_text(text + "\n")


if __name__ == "__main__":
    main()
