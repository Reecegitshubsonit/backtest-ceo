# Options strategy search: 100,000 combinations, walk-forward, multiple-testing corrected

Data: all Alpaca options history usable here (2024-02-01 .. 2026-11-02), SPY QQQ IWM NVDA TSLA AAPL, 30-min option trade bars + SIP underlying bars. Split by time: search 2024-02-01..2025-09-26 (60%), validate 2025-09-26..2026-04-16 (20%), holdout 2026-04-16..2026-11-02 (20%).

Space 3,735,552 combinations; 100,000 sampled (same list for the shuffled run). 68,995 had >= 90 search trades. Top 1000 by search Sharpe went to validation; finalists = best validation Sharpe that pass the neighbour test (>= 2/3 of one-step neighbours profitable in search and validation). Top 10 were run on the holdout once.

Bug found and fixed before the holdout was touched: the first run picked strikes using the entry bar's own VWAP (the next 30 minutes), which let 0DTE 15:30 condors 'see' the close (validation Sharpe 12.8, same in the shuffled run). Now strikes are picked from the last print of a bar that closed before entry, and entry fills at the worse of that print and the entry-bar VWAP, then +- half-spread. All numbers below are after the fix.

## Luck benchmark (same search, signals shuffled in time)

| Run | Eligible | Best search Sharpe | 95th pct search Sharpe | Passed validation | Best validation Sharpe | Neighbour rejects | Finalists |
|---|---:|---:|---:|---:|---:|---:|---:|
| real | 68,995 | 3.29 | 0.04 | 110 | 9.22 | 19 | 10 |
| shuffled | 69,167 | 2.94 | 0.20 | 47 | 9.49 | 40 | 7 |

## Real: finalists on the holdout (run once)

| # | Strategy | Search n / Sharpe / DSR | Validate n / Sharpe / DSR | Neighbours | Holdout trades | Win % | Exp $ | Total $ | Max DD $ | Sharpe | p (1-sided) | 2x spread exp $ / Sharpe | Survives |
|---:|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|---|
| 1 | d_ibs 0.3 [high-vol] -> 30DTE credit 0.15d, wing -0.10d @ 14:00, PT 0.75x, SL None | 581 / 2.30 / 0.00 | 109 / 7.09 / 0.02 | 6/8 | 192 | 95.8 | 67.51 | 12961 | -9283 | 1.75 | 0.0967 | 57.70 / 1.50 | no |
| 2 | d_rsi2 10/90 [high-vol] -> 7DTE credit 0.15d, wing -0.10d @ 14:00, PT 0.5x, SL None | 379 / 2.24 / 0.00 | 66 / 6.34 / 0.00 | 8/10 | 108 | 95.4 | -15.58 | -1682 | -4512 | -0.48 | 0.6379 | -22.71 / -0.69 | no |
| 3 | d_rsi2 10/90 -> 7DTE credit 0.15d, wing -0.10d @ 14:00, PT None, SL None | 674 / 1.79 / 0.00 | 185 / 6.02 / 0.00 | 8/9 | 203 | 91.1 | 14.22 | 2886 | -5878 | 0.59 | 0.3304 | 10.26 / 0.43 | no |
| 4 | breakout 4 inverted [trend-aligned, high-vol] -> 30DTE condor 0.15d, wing -0.10d @ 12:00, PT 0.5x, SL 3x | 104 / 1.83 / 0.00 | 28 / 5.68 / 0.00 | 7/9 | 38 | 89.5 | 18.78 | 714 | -2962 | 0.47 | 0.3645 | -0.95 / -0.02 | no |
| 5 | d_ibs 0.2 [trend-aligned, high-vol] -> 30DTE credit 0.15d, wing -0.05d @ 14:00, PT 0.5x, SL None | 188 / 1.43 / 0.00 | 33 / 5.59 / 0.00 | 6/9 | 60 | 95.0 | 32.11 | 1927 | -5 | 7.07 | 0.0000 | 19.94 / 5.98 | no |
| 6 | gap 0.003 [trend-aligned, high-vol] -> 30DTE condor 0.15d, wing -0.10d @ 12:00, PT 0.5x, SL 3x | 422 / 1.02 / 0.00 | 118 / 5.54 / 0.00 | 6/9 | 182 | 94.0 | 60.33 | 10980 | -5075 | 2.47 | 0.0330 | 39.50 / 1.64 | no |
| 7 | vwap 0.002 inverted [trend-aligned, high-vol] -> 30DTE condor 0.15d, wing -0.10d @ 12:00, PT 0.5x, SL 3x | 418 / 0.97 / 0.00 | 106 / 5.53 / 0.01 | 7/10 | 164 | 92.7 | 48.13 | 7894 | -5275 | 1.99 | 0.0698 | 26.72 / 1.11 | no |
| 8 | hammer_star [trend-aligned, high-vol] -> 30DTE condor 0.15d, wing -0.10d @ 14:00, PT 0.75x, SL 3x | 99 / 1.74 / 0.00 | 27 / 5.12 / 0.00 | 7/7 | 29 | 89.7 | 100.65 | 2919 | -1873 | 1.73 | 0.0997 | 80.54 / 1.40 | no |
| 9 | d_ibs 0.2 [trend-aligned, high-vol] -> 30DTE condor 0.15d, wing -0.10d @ 10:00, PT 0.5x, SL None | 284 / 1.97 / 0.00 | 69 / 4.77 / 0.00 | 6/8 | 107 | 92.5 | 36.94 | 3953 | -5847 | 0.71 | 0.2982 | 19.29 / 0.37 | no |
| 10 | d_breakout 20 [trend-aligned, low-vol] -> 7DTE condor 0.15d, wing -0.10d @ 15:30, PT 0.75x, SL None | 161 / 1.80 / 0.00 | 53 / 4.72 / 0.00 | 5/7 | 59 | 76.3 | -41.83 | -2468 | -3626 | -0.80 | 0.7243 | -51.51 / -0.99 | no |

## Shuffled (luck benchmark): finalists on the holdout (run once)

| # | Strategy | Search n / Sharpe / DSR | Validate n / Sharpe / DSR | Neighbours | Holdout trades | Win % | Exp $ | Total $ | Max DD $ | Sharpe | p (1-sided) | 2x spread exp $ / Sharpe | Survives |
|---:|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|---|
| 1 | ema_cross 5/20 inverted -> 30DTE credit 0.15d, wing -0.10d @ 10:00, PT 0.5x, SL None | 262 / 1.04 / 0.00 | 108 / 8.92 / 1.00 | 6/8 | 108 | 97.2 | 58.33 | 6300 | -1293 | 3.85 | 0.0021 | - | YES |
| 2 | rsi2 10/90 inverted [trend-aligned, high-vol] -> 7DTE credit 0.15d, wing -0.10d @ 14:00, PT 0.75x, SL None | 141 / 0.88 / 0.00 | 57 / 7.81 / 0.98 | 6/9 | 45 | 95.6 | 14.61 | 657 | -2233 | 0.38 | 0.3883 | - | no |
| 3 | rsi14 30/70 inverted [trend-aligned] -> 30DTE credit 0.15d, wing -0.10d @ 14:00, PT 0.5x, SL 3x | 142 / 2.94 / 0.00 | 43 / 3.37 / 0.05 | 9/9 | 37 | 83.8 | -0.47 | -18 | -1633 | -0.01 | 0.5042 | - | no |
| 4 | hammer_star inverted [trend-aligned] -> 30DTE long 0.50d @ 15:30, PT 1x, SL None | 118 / 0.75 / 0.00 | 33 / 1.64 / 0.00 | 4/6 | 36 | 58.3 | 172.64 | 6215 | -7486 | 0.77 | 0.2839 | - | no |
| 5 | d_breakout 20 [high-vol] -> 1DTE long 0.25d @ 14:00, PT 2x, SL None | 97 / 0.80 / 0.00 | 32 / 1.53 / 0.00 | 6/8 | 37 | 29.7 | 8.83 | 327 | -777 | 0.36 | 0.3944 | - | no |
| 6 | d_rsi2 10/90 inverted [low-vol] -> 30DTE long 0.50d @ 12:00, PT 2x, SL None | 215 / 0.77 / 0.00 | 63 / 0.91 / 0.00 | 5/7 | 71 | 26.8 | -534.41 | -37943 | -42394 | -1.96 | 0.9274 | - | no |
| 7 | d_breakout 20 [high-vol] -> 1DTE long 0.35d @ 14:00, PT 0.5x, SL None | 99 / 1.30 / 0.00 | 33 / 0.74 / 0.00 | 7/9 | 36 | 36.1 | -11.26 | -405 | -1523 | -0.35 | 0.6038 | - | no |

Survives = holdout >= 30 trades, positive expectancy, one-sided p < 0.05/10 (Bonferroni over the 10 holdout tests) and validation Deflated Sharpe >= 0.95.

**Survivors: 0 of 10.** Nothing survives.

## Earlier best strategies on the same holdout window

In-sample warning: these were tuned on data that overlaps this window, so they had an advantage here.

| Strategy | Trades | Win % | Exp $ | Total $ | Max DD $ | Sharpe |
|---|---:|---:|---:|---:|---:|---:|
| v2 (3m): 0DTE iron condor 15:00 (SPY+QQQ, 1 contract, strict fill, 2x spread) | 125 | 88.8 | 16.31 | 2039 | -232 | 4.43 |
| v2 (3m): 0DTE bull put 15:00 (SPY+QQQ, 1 contract, strict fill, 2x spread) | 82 | 93.9 | 15.99 | 1311 | -299 | 3.74 |
| v2 (3m): EMA+VWAP trend spread 11:00 (SPY+QQQ, 1 contract, strict fill, 2x spread) | 77 | 66.2 | 5.27 | 406 | -49 | 5.11 |
| v2 (6m): RSI14 reversion spread 15:00 (SPY+QQQ, 1 contract, strict fill, 2x spread) | 59 | 91.5 | 29.38 | 1734 | -194 | 4.61 |
| v2 (6m): 0DTE bear call 10:00 (SPY+QQQ, 1 contract, strict fill, 2x spread) | 35 | 91.4 | 20.24 | 708 | -143 | 3.87 |
| shares daily: RSI(2) pullback in uptrend (Connors) (k=10), $5k/trade | 82 | 70.7 | 34.87 | 2859 | -922 | 2.75 |
| shares daily: EMA200 trend + close below EMA5 by k% (EMA snap-back) (k=1.0), $5k/trade | 89 | 71.9 | 34.66 | 3084 | -891 | 3.06 |
| shares daily: IBS < k in uptrend, 1-3 day hold (k=0.1), $5k/trade | 143 | 56.6 | 15.25 | 2181 | -1040 | 1.75 |
| shares daily: k down closes above EMA200 (k=3), $5k/trade | 82 | 73.2 | 28.97 | 2376 | -804 | 2.55 |
| shares daily: RSI(2) < k AND IBS < 0.25 in uptrend (k=10), $5k/trade | 61 | 73.8 | 56.63 | 3454 | -261 | 3.42 |
| shares daily: RSI(14) < k above EMA50 (trend pullback) (k=45), $5k/trade | 10 | 80.0 | 89.30 | 893 | -191 | 2.58 |

## Data limits (stated plainly)

* No historical option quotes on Alpaca (endpoint 404), so fills cannot use real bid/ask. Fills are trade-bar VWAP +- a modelled half-spread (index ETFs max($0.01, 1%), single stocks max($0.02, 2%)); buys at the modelled ask, sells at the modelled bid, never the midpoint. A live-quote calibration was attempted and rejected (`spread_model.md`).
* No Level 2 / depth history anywhere on Alpaca. Option trade prints exist but cannot be signed without quotes; stock L1 quote/trade history exists but was not pulled (tick volume for 2.7 years x 6 symbols). So no order-flow features were used.
* Contract lists are not reachable here; OCC symbols were constructed. Expiries that did not exist (e.g. early-2024 IWM Tue/Thu) simply have no trades.
* Delta from Black-Scholes implied vol of each contract's own price (r = 4.5%).
* Settlement at intrinsic on the expiry close; no assignment/pin modelling; daily P&L booked on exit day.
