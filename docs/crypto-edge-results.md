# Crypto edge backtest — 5 published strategies on BTC / ETH / SOL

Script: `engine/scripts/crypto_edge_backtest.py` (Alpaca `v1beta3/crypto/us` bars, run 2026-11-03).

## Strategies and evidence

| # | Strategy | TF | Rule | Evidence |
|---|---|---|---|---|
| 1 | TSMOM 28d | 1D | Long while trailing 28-day return > 0, else flat | Liu & Tsyvinski (2021), *Risks and Returns of Cryptocurrency*, RFS — strong crypto time-series momentum |
| 2 | Donchian 20/10 | 1D | Long on close > prior 20d high, exit close < prior 10d low | Zarattini, Pagani & Barbon (2025), [*Catching Crypto Trends*](https://ideas.repec.org/p/chf/rpseri/rp2580.html), SFI RP 25-80; Hudson & Urquhart (2021) technical rules |
| 3 | Abnormal-day momentum | 1D | Day return > mean+1σ (30d) → long next day; < mean−1σ → short | Caporale & Plastun (2020), [FMPM](https://link.springer.com/10.1007/s11408-020-00357-1) — momentum after one-day abnormal returns |
| 4 | Intraday TS momentum | 30m | Sign of 00:00–00:30 UTC return → trade 23:30–24:00 (L/S) | Shen, Urquhart & Wang (2022), [*Bitcoin intraday time series momentum*](https://research.birmingham.ac.uk/en/publications/bitcoin-intraday-time-series-momentum/), Financial Review |
| 5 | 21–23 UTC seasonality | 30m | Long 21:00 → 23:00 UTC daily | Quantpedia, [*Seasonal intraday anomalies in Bitcoin*](https://quantpedia.com/are-there-seasonal-intraday-or-overnight-anomalies-in-bitcoin/) (costs not reported, no independent replication) |

## Method

- Daily: 2021-01-01 → 2026-11-02 (5.8 y). Intraday: last 60 days of 30m bars (2026-09-04 → 2026-11-02).
- Costs: Alpaca crypto taker 0.25% + 0.05% slippage **per side** (0.60% round trip). Sensitivity: 0.06%/side (perp-exchange taker level).
- Full-size position per trade, no leverage. Short legs (3, 4) assume a perp/margin venue; Alpaca spot is long-only.
- Expectancy = mean net return per trade. Gross exp. = before costs. Max DD on compounded equity. Sharpe = daily returns × √365 (flat days = 0).
- Reject if < 30 trades.

## Results — Alpaca costs (0.30%/side)

| strategy | tf | symbol | trades | win% | exp% | gross_exp% | maxDD% | sharpe | total% | status |
|---|---|---|---|---|---|---|---|---|---|---|
| TSMOM 28d (long/flat) | 1D | BTC/USD | 91 | 35.16 | 2.12 | 2.72 | -48.77 | 0.78 | 267.15 | ok |
| Donchian 20/10 (long/flat) | 1D | BTC/USD | 28 | 39.29 | 4.77 | 5.37 | -46.16 | 0.56 | 119.85 | REJECT (<30 trades) |
| Abnormal-day momentum (L/S) | 1D | BTC/USD | 474 | 34.39 | -0.66 | -0.06 | -96.95 | -1.64 | -96.57 | ok |
| Buy & hold (reference) | 1D | BTC/USD | 1 | 100.0 | 160.04 | 160.64 | -76.68 | 0.57 | 160.64 | reference |
| Intraday TS momentum 1st->last 30m (L/S) | 30m | BTC/USD | 60 | 1.67 | -0.6 | 0.0 | -29.8 | -60.58 | -30.16 | ok |
| 21-23 UTC seasonality (long) | 30m | BTC/USD | 60 | 3.33 | -0.65 | -0.05 | -32.0 | -34.72 | -32.48 | ok |
| TSMOM 28d (long/flat) | 1D | ETH/USD | 91 | 36.26 | 1.59 | 2.19 | -56.89 | 0.51 | 114.75 | ok |
| Donchian 20/10 (long/flat) | 1D | ETH/USD | 32 | 43.75 | 2.28 | 2.88 | -64.53 | 0.33 | 32.01 | ok |
| Abnormal-day momentum (L/S) | 1D | ETH/USD | 476 | 36.34 | -0.86 | -0.26 | -99.01 | -1.71 | -98.95 | ok |
| Buy & hold (reference) | 1D | ETH/USD | 1 | 100.0 | 207.31 | 207.91 | -79.31 | 0.63 | 207.91 | reference |
| Intraday TS momentum 1st->last 30m (L/S) | 30m | ETH/USD | 60 | 1.67 | -0.59 | 0.01 | -29.39 | -57.66 | -29.88 | ok |
| 21-23 UTC seasonality (long) | 30m | ETH/USD | 60 | 6.67 | -0.69 | -0.09 | -33.82 | -21.7 | -34.26 | ok |
| TSMOM 28d (long/flat) | 1D | SOL/USD | 66 | 36.36 | 10.99 | 11.59 | -63.92 | 1.28 | 2508.58 | ok |
| Donchian 20/10 (long/flat) | 1D | SOL/USD | 24 | 41.67 | 41.91 | 42.51 | -62.61 | 0.64 | 4348.12 | REJECT (<30 trades) |
| Abnormal-day momentum (L/S) | 1D | SOL/USD | 396 | 41.41 | 0.81 | 1.41 | -93.96 | 0.26 | -84.57 | ok |
| Buy & hold (reference) | 1D | SOL/USD | 1 | 100.0 | 4856.1 | 4856.7 | -96.27 | 0.74 | 4856.7 | reference |
| Intraday TS momentum 1st->last 30m (L/S) | 30m | SOL/USD | 60 | 1.67 | -0.57 | 0.03 | -28.65 | -41.08 | -29.1 | ok |
| 21-23 UTC seasonality (long) | 30m | SOL/USD | 60 | 13.33 | -0.66 | -0.06 | -32.28 | -16.99 | -32.73 | ok |

## Sensitivity — low costs (0.06%/side)

| strategy | tf | symbol | trades | win% | exp% | gross_exp% | maxDD% | sharpe | total% | status |
|---|---|---|---|---|---|---|---|---|---|---|
| TSMOM 28d (long/flat) | 1D | BTC/USD | 91 | 39.56 | 2.6 | 2.72 | -44.04 | 0.98 | 467.89 | ok |
| Donchian 20/10 (long/flat) | 1D | BTC/USD | 28 | 39.29 | 5.25 | 5.37 | -44.7 | 0.63 | 151.52 | REJECT (<30 trades) |
| Abnormal-day momentum (L/S) | 1D | BTC/USD | 474 | 43.04 | -0.18 | -0.06 | -75.4 | -0.43 | -66.43 | ok |
| Buy & hold (reference) | 1D | BTC/USD | 1 | 100.0 | 160.52 | 160.64 | -76.68 | 0.57 | 160.64 | reference |
| Intraday TS momentum 1st->last 30m (L/S) | 30m | BTC/USD | 60 | 18.33 | -0.12 | 0.0 | -7.02 | -11.81 | -6.75 | ok |
| 21-23 UTC seasonality (long) | 30m | BTC/USD | 60 | 31.67 | -0.17 | -0.05 | -9.72 | -9.15 | -9.83 | ok |
| TSMOM 28d (long/flat) | 1D | ETH/USD | 91 | 38.46 | 2.07 | 2.19 | -56.35 | 0.66 | 232.76 | ok |
| Donchian 20/10 (long/flat) | 1D | ETH/USD | 32 | 46.88 | 2.76 | 2.88 | -61.42 | 0.39 | 53.88 | ok |
| Abnormal-day momentum (L/S) | 1D | ETH/USD | 476 | 42.86 | -0.38 | -0.26 | -93.5 | -0.76 | -89.59 | ok |
| Buy & hold (reference) | 1D | ETH/USD | 1 | 100.0 | 207.79 | 207.91 | -79.31 | 0.63 | 207.91 | reference |
| Intraday TS momentum 1st->last 30m (L/S) | 30m | ETH/USD | 60 | 23.33 | -0.11 | 0.01 | -6.54 | -10.73 | -6.39 | ok |
| 21-23 UTC seasonality (long) | 30m | ETH/USD | 60 | 35.0 | -0.21 | -0.09 | -12.63 | -6.71 | -12.21 | ok |
| TSMOM 28d (long/flat) | 1D | SOL/USD | 66 | 37.88 | 11.47 | 11.59 | -63.29 | 1.37 | 3482.56 | ok |
| Donchian 20/10 (long/flat) | 1D | SOL/USD | 24 | 41.67 | 42.39 | 42.51 | -61.59 | 0.64 | 4882.93 | REJECT (<30 trades) |
| Abnormal-day momentum (L/S) | 1D | SOL/USD | 396 | 47.47 | 1.29 | 1.41 | -85.51 | 0.39 | 4.16 | ok |
| Buy & hold (reference) | 1D | SOL/USD | 1 | 100.0 | 4856.58 | 4856.7 | -96.27 | 0.74 | 4856.7 | reference |
| Intraday TS momentum 1st->last 30m (L/S) | 30m | SOL/USD | 60 | 31.67 | -0.09 | 0.03 | -5.57 | -6.55 | -5.34 | ok |
| 21-23 UTC seasonality (long) | 30m | SOL/USD | 60 | 41.67 | -0.18 | -0.06 | -10.83 | -4.56 | -10.17 | ok |

## Robustness — daily strategies, last 2 years only (2024-11-01 →), Alpaca costs

| strategy | tf | symbol | trades | win% | exp% | gross_exp% | maxDD% | sharpe | total% | status |
|---|---|---|---|---|---|---|---|---|---|---|
| TSMOM 28d (long/flat) | 1D | BTC/USD | 36 | 36.11 | -0.38 | 0.22 | -36.26 | -0.21 | -16.41 | ok |
| Donchian 20/10 (long/flat) | 1D | BTC/USD | 11 | 36.36 | -1.65 | -1.05 | -40.47 | -0.33 | -20.03 | REJECT (<30 trades) |
| Abnormal-day momentum (L/S) | 1D | BTC/USD | 159 | 35.85 | -0.52 | 0.08 | -59.88 | -1.52 | -58.38 | ok |
| Buy & hold (reference) | 1D | BTC/USD | 1 | 100.0 | 9.76 | 10.36 | -53.07 | 0.33 | 10.36 | reference |
| TSMOM 28d (long/flat) | 1D | ETH/USD | 29 | 31.03 | 1.12 | 1.72 | -41.75 | 0.39 | 16.66 | REJECT (<30 trades) |
| Donchian 20/10 (long/flat) | 1D | ETH/USD | 13 | 30.77 | -3.89 | -3.29 | -57.82 | -0.67 | -45.53 | REJECT (<30 trades) |
| Abnormal-day momentum (L/S) | 1D | ETH/USD | 149 | 44.97 | -0.33 | 0.27 | -51.51 | -0.7 | -45.9 | ok |
| Buy & hold (reference) | 1D | ETH/USD | 1 | 0.0 | -10.99 | -10.39 | -67.61 | 0.26 | -10.39 | reference |
| TSMOM 28d (long/flat) | 1D | SOL/USD | 29 | 27.59 | -1.64 | -1.04 | -53.98 | -0.39 | -41.33 | REJECT (<30 trades) |
| Donchian 20/10 (long/flat) | 1D | SOL/USD | 10 | 30.0 | -1.84 | -1.24 | -35.39 | -0.16 | -20.98 | REJECT (<30 trades) |
| Abnormal-day momentum (L/S) | 1D | SOL/USD | 166 | 41.57 | -0.63 | -0.03 | -72.45 | -1.24 | -69.09 | ok |
| Buy & hold (reference) | 1D | SOL/USD | 1 | 0.0 | -45.3 | -44.7 | -76.23 | -0.01 | -44.7 | reference |

## Verdict

- **Only survivor: TSMOM 28d.** Positive net expectancy on all 3 coins over 5.8 y, beats buy & hold Sharpe on BTC (0.78 vs 0.57) and SOL (1.28 vs 0.74), ~halves drawdown. But last 2 years it is flat-to-negative on BTC/SOL and <30 trades on ETH/SOL — edge is concentrated in 2021–2023 trends. Treat as a drawdown-reducing overlay, not alpha.
- **Donchian 20/10:** profitable but rejected on BTC/SOL (<30 trades); ETH passes at 32 trades with weak Sharpe 0.33. Not enough evidence.
- **Abnormal-day momentum:** gross expectancy ≈ 0 on BTC/ETH; costs destroy it (−97% / −99%). SOL slightly positive gross, negative net equity. Rejected on merit.
- **Intraday TS momentum, 21–23 UTC seasonality:** gross expectancy ≈ 0 (−0.09% … +0.03%) over 60 days; a 0.60% round trip guarantees loss. Even at 0.06%/side both lose. No edge in recent data.
- Caveats: 60-day intraday sample is tiny; Alpaca crypto bars are thin-volume (Alpaca venue), fills at bar open/close assumed; no funding costs on shorts; single parameter set per strategy (no optimisation, so no in-sample tuning bias, but also no parameter robustness check).
