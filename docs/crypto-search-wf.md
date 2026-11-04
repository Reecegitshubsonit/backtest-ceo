# Round 4: walk-forward search on alpha, low turnover, maker costs

Script: `engine/scripts/crypto_search_wf.py` (~75 s). Tables: `docs/crypto-search-wf-tables.md`.

## Changes from round 3

- **Cost:** 0.30% round trip (Alpaca maker 0.15% per side, limit orders; the risk that a limit order doesn't fill is not modelled).
- **Bars:** 4h and 1d only.
- **Turnover:** a combination is eligible only if it trades ≤ 15 times a year per coin.
- **Score:** alpha information ratio. Daily returns are regressed on buy & hold; the score is the leftover (residual) return divided by its volatility, annualised. Being long in a bull market earns nothing.
- **Walk-forward:** 100,000 random combinations.
  - For each test year 2023, 2024, 2025 and 2026 (to 2026-11-02), train on every earlier year.
  - Pick the top 10 combinations that pass the neighbour check, pooled across BTC and ETH, and trade them as an equal-weight basket in the test year.
  - SOL gets the same baskets and is shown separately.
- **Luck benchmark:** the identical procedure on 5 shuffled datasets.
- **Caveat:** the 2025–26 folds overlap round 3's holdout, and this design was chosen after seeing it. They are not clean.

## Result: nothing survives

| Coin | OOS 2023 → Nov 2026 | Sharpe | Max DD | Alpha IR (95% CI) | Shuffled alpha IR (mean) | Buy & hold | B&H Sharpe | TSMOM 28d | TSMOM Sharpe |
|---|---|---|---|---|---|---|---|---|---|
| BTC | +1.7% | 0.11 | −9.6% | −0.54 [−1.61, 0.34] | −0.87 | +364% | 1.09 | +296% | **1.21** |
| ETH | −17.7% | −0.50 | −22.1% | −1.02 [−1.95, −0.02] | −0.34 | +88% | 0.57 | +104% | 0.65 |
| SOL | −4.2% | −0.02 | −19.9% | −0.39 [−1.30, 0.54] | — | +26% | 0.42 | +33% | 0.46 |

- Out-of-sample alpha is negative on all three coins. On ETH the confidence interval is entirely below zero, and all 5 shuffled runs did better.
- Each year's top-10 basket was mostly flat (beta ≈ 0.1). It dodged drawdowns but captured no return.
- The forward candidates (trained on all data) are listed in the tables file. They come from a procedure that failed out of sample, so **they are not paper-traded**.
- TSMOM 28d at 0.30% round trip beat everything here and beat buy & hold Sharpe on BTC (1.21 vs 1.09) and ETH (0.65 vs 0.57), with smaller drawdowns.
