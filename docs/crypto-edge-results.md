# Crypto edge backtest — 5 published strategies on BTC / ETH / SOL

Script: `engine/scripts/crypto_edge_backtest.py` (Alpaca `v1beta3/crypto/us` bars). Run 2026-11-03. Rerun: `python engine/scripts/crypto_edge_backtest.py --out <file>`.

## What survives (plain)

- **Nothing has a statistically proven edge.** No bootstrap 95% CI on Sharpe(TSMOM) − Sharpe(buy & hold) excludes zero, on any coin, any period, with or without T-bill cash.
- **TSMOM 28d survives only as a risk overlay.** Positive net expectancy on all 3 coins over the full period, cuts max drawdown by 22–33 points versus buy & hold, and beats buy & hold Sharpe on BTC (0.78 vs 0.57) and SOL (1.31 vs 0.91). On ETH it lags buy & hold over the full period. Last 2 years: per-trade expectancy is negative on BTC and SOL, and ETH/SOL fall below 30 trades (29, 28), so the recent window fails the trade-count rule for those two.
- **SOL's strong full-period TSMOM result is mostly 2021.** Ex-2021 (and with the data hole removed): Sharpe 0.28, CAGR ≈ 1%, expectancy +0.55%/trade. It beats a falling buy & hold (Sharpe −0.33) only by being in cash; the bootstrap CI still spans zero (P(diff ≤ 0) = 8%).
- **T-bill on idle cash** adds ≈ 1.7–2.9 pp CAGR and ≈ +0.02–0.06 Sharpe. It changes no conclusion.
- **Donchian 20/10:** fewer than 30 trades on BTC and SOL → rejected. ETH passes at 32 trades with Sharpe 0.32, below buy & hold.
- **Abnormal-day momentum, intraday first→last 30m momentum, 21–23 UTC seasonality:** lose money after fees on every coin. Rejected.

## Changes in this revision

1. **Fill timing.** The previous version filled daily signals at the *signal bar's own close*. This is now fixed: orders fill at the **next bar's open** (`simulate(..., fill="next_open")`). A one-full-bar-late stress test (`next_close`) is also reported. On 24/7 crypto, next open ≈ signal close, so results barely move (TSMOM BTC Sharpe 0.776 → 0.777). The one-bar-late test costs TSMOM 0.15–0.2 Sharpe on BTC and SOL; ETH improves.
2. **Data hole found and fixed.** Alpaca SOL/USD has **no bars from 2023-06-29 to 2024-08-25 (417 days)**. The bar after the hole showed +680%. The previous version booked that jump as one daily return, which inflated SOL's buy & hold and TSMOM numbers. Strategies now run per contiguous segment, so no return is booked across a hole of more than 5 days, and CAGR counts only days with data. Earlier SOL figures (buy & hold +4,857%, TSMOM +2,509%) are void.
3. Buy & hold CAGR, volatility, max drawdown and Sharpe added for each coin: full period, last 2 years, and SOL from 2022 on.
4. Paired circular block bootstrap (block length 20 days, 5,000 reps) of the Sharpe difference between TSMOM and buy & hold.
5. TSMOM run with SOL's 2021 removed, and with idle cash earning the T-bill rate. The rate comes from Alpaca's dividend-adjusted BIL bars over a 63-day window, with the 0.1355% expense ratio added back. Mean rate 3.2%/y; 0.08% in Jan 2021, 3.95% now. "xs_sharpe" means Sharpe on returns minus the T-bill rate.

## Strategies and evidence

| # | Strategy | TF | Rule | Evidence |
|---|---|---|---|---|
| 1 | TSMOM 28d | 1D | Long while trailing 28-day return > 0, else flat | Liu & Tsyvinski (2021), *Risks and Returns of Cryptocurrency*, RFS — strong crypto time-series momentum |
| 2 | Donchian 20/10 | 1D | Long on close > prior 20d high, exit close < prior 10d low | Zarattini, Pagani & Barbon (2025), [*Catching Crypto Trends*](https://ideas.repec.org/p/chf/rpseri/rp2580.html), SFI RP 25-80; Hudson & Urquhart (2021) technical rules |
| 3 | Abnormal-day momentum | 1D | Day return > mean+1σ (30d) → long next day; < mean−1σ → short | Caporale & Plastun (2020), [FMPM](https://link.springer.com/10.1007/s11408-020-00357-1) — momentum after one-day abnormal returns |
| 4 | Intraday TS momentum | 30m | Sign of 00:00–00:30 UTC return → trade 23:30–24:00 (L/S) | Shen, Urquhart & Wang (2022), [*Bitcoin intraday time series momentum*](https://research.birmingham.ac.uk/en/publications/bitcoin-intraday-time-series-momentum/), Financial Review |
| 5 | 21–23 UTC seasonality | 30m | Long 21:00 → 23:00 UTC daily | Quantpedia, [*Seasonal intraday anomalies in Bitcoin*](https://quantpedia.com/are-there-seasonal-intraday-or-overnight-anomalies-in-bitcoin/) (costs not reported, no independent replication) |

## Method

- Daily: 2021-01-01 → 2026-11-02 (5.8 y; SOL ≈ 4.7 y of actual bars). Last 2y = 2024-11-03 →. Intraday: last 60 days of 30m bars.
- Costs: 0.25% Alpaca taker fee + 0.05% slippage **per side** (0.60% round trip).
- Daily fills at next bar open. Full-size positions, no leverage. Short legs assume a perp/margin venue with no funding cost.
- Expectancy = mean net return per trade. Sharpe = daily returns × √365. Max drawdown on compounded equity. Strategies with fewer than 30 trades are rejected.

## Data quality

**Cross-venue check against Coinbase/Binance was not possible.** The environment's network policy blocks `api.exchange.coinbase.com`, `api.binance.com`, `data-api.binance.vision` (also FRED, Treasury, Kraken, CoinGecko). To run the comparison, add one of those hosts under Allowed domains in the environment's network settings and rerun.

What was done instead:
- **Live spot check, Robinhood vs Alpaca, 2026-11-03 21:54 UTC** (mark vs mid): BTC 77,821 vs 77,809 (0.015%), ETH 2,292.2 vs 2,291.9 (0.01%), SOL 93.60 vs 93.59 (0.01%). Prices agree; this is one point in time, not a history check.
- **Alpaca internal checks** (table below):
  - SOL: 418 missing days (the 417-day hole plus a 3-day gap in June 2023).
  - BTC/ETH: no missing days.
  - Daily open vs prior close: median gap 0.02–0.04%, but there are jumps up to 6.2% (BTC), 7.9% (ETH) and 10.3% (SOL). The biggest is on 2025-12-02 on all three coins, which points to an Alpaca venue outage or repricing, not real 24/7 price action.
  - Liquidity regime change: median trades per day fell from about 50k (2021–22) to a few hundred (2023+). The source behind the bars changed; post-2022 bars come from a thin venue.
  - **30m bars (last 60 days): 0 missing, 0 zero-range, 0 stale** (same close and zero range as the prior bar). Zero-volume 30m bars: BTC 8, ETH 123, SOL 257. These have a non-zero range, so they are priced from quotes, not trades.
  - Daily close vs last 30m close of the same UTC day: max diff 0.005%. The two timeframes are consistent.

## Results

#### Main table — next-bar-open fills, cost 0.30%/side

| strategy | tf | symbol | trades | win% | exp% | maxDD% | sharpe | CAGR% | status |
|---|---|---|---|---|---|---|---|---|---|
| TSMOM 28d (long/flat) | 1D | BTC/USD | 91.0 | 35.16 | 2.11 | -48.98 | 0.78 | 24.87 | ok |
| Donchian 20/10 (long/flat) | 1D | BTC/USD | 28.0 | 39.29 | 4.73 | -46.3 | 0.56 | 14.32 | REJECT (<30 trades) |
| Abnormal-day momentum (L/S) | 1D | BTC/USD | 473.0 | 34.04 | -0.62 | -96.43 | -1.6 | -42.41 | ok |
| Buy & hold (reference) | 1D | BTC/USD |  |  |  | -76.68 | 0.57 | 17.84 | reference |
| Intraday TS momentum 1st->last 30m (L/S) | 30m | BTC/USD | 60.0 | 1.67 | -0.6 | -29.8 | -60.58 | -88.75 | ok |
| 21-23 UTC seasonality (long) | 30m | BTC/USD | 60.0 | 3.33 | -0.65 | -32.0 | -34.72 | -90.84 | ok |
| TSMOM 28d (long/flat) | 1D | ETH/USD | 91.0 | 36.26 | 1.62 | -56.96 | 0.52 | 14.68 | ok |
| Donchian 20/10 (long/flat) | 1D | ETH/USD | 32.0 | 43.75 | 2.26 | -64.8 | 0.32 | 4.77 | ok |
| Abnormal-day momentum (L/S) | 1D | ETH/USD | 476.0 | 36.97 | -0.82 | -98.78 | -1.69 | -52.58 | ok |
| Buy & hold (reference) | 1D | ETH/USD |  |  |  | -79.31 | 0.63 | 21.25 | reference |
| Intraday TS momentum 1st->last 30m (L/S) | 30m | ETH/USD | 60.0 | 1.67 | -0.59 | -29.39 | -57.66 | -88.48 | ok |
| 21-23 UTC seasonality (long) | 30m | ETH/USD | 60.0 | 6.67 | -0.69 | -33.82 | -21.7 | -92.22 | ok |
| TSMOM 28d (long/flat) | 1D | SOL/USD | 65.0 | 36.92 | 11.26 | -64.19 | 1.31 | 104.11 | ok |
| Donchian 20/10 (long/flat) | 1D | SOL/USD | 24.0 | 37.5 | 16.92 | -74.68 | 0.91 | 47.4 | REJECT (<30 trades) |
| Abnormal-day momentum (L/S) | 1D | SOL/USD | 395.0 | 42.28 | -0.67 | -97.02 | -0.94 | -52.26 | ok |
| Buy & hold (reference) | 1D | SOL/USD |  |  |  | -96.91 | 0.91 | 48.32 | reference |
| Intraday TS momentum 1st->last 30m (L/S) | 30m | SOL/USD | 60.0 | 1.67 | -0.57 | -28.65 | -41.08 | -87.67 | ok |
| 21-23 UTC seasonality (long) | 30m | SOL/USD | 60.0 | 13.33 | -0.66 | -32.28 | -16.99 | -91.05 | ok |

#### Fill timing check (daily strategies)

| strategy | symbol | fill | trades | exp% | sharpe | maxDD% |
|---|---|---|---|---|---|---|
| TSMOM 28d (long/flat) | BTC/USD | same_close | 91 | 2.12 | 0.78 | -49.05 |
| TSMOM 28d (long/flat) | BTC/USD | next_open | 91 | 2.11 | 0.78 | -48.98 |
| TSMOM 28d (long/flat) | BTC/USD | next_close | 91 | 1.65 | 0.62 | -57.72 |
| Donchian 20/10 (long/flat) | BTC/USD | same_close | 28 | 4.77 | 0.56 | -46.4 |
| Donchian 20/10 (long/flat) | BTC/USD | next_open | 28 | 4.73 | 0.56 | -46.3 |
| Donchian 20/10 (long/flat) | BTC/USD | next_close | 28 | 4.96 | 0.56 | -54.01 |
| Abnormal-day momentum (L/S) | BTC/USD | same_close | 474 | -0.64 | -1.58 | -96.72 |
| Abnormal-day momentum (L/S) | BTC/USD | next_open | 473 | -0.62 | -1.6 | -96.43 |
| Abnormal-day momentum (L/S) | BTC/USD | next_close | 473 | -0.39 | -1.07 | -92.22 |
| TSMOM 28d (long/flat) | ETH/USD | same_close | 91 | 1.59 | 0.51 | -57.07 |
| TSMOM 28d (long/flat) | ETH/USD | next_open | 91 | 1.62 | 0.52 | -56.96 |
| TSMOM 28d (long/flat) | ETH/USD | next_close | 91 | 1.85 | 0.59 | -52.86 |
| Donchian 20/10 (long/flat) | ETH/USD | same_close | 32 | 2.28 | 0.33 | -64.65 |
| Donchian 20/10 (long/flat) | ETH/USD | next_open | 32 | 2.26 | 0.32 | -64.8 |
| Donchian 20/10 (long/flat) | ETH/USD | next_close | 32 | 0.81 | 0.16 | -68.69 |
| Abnormal-day momentum (L/S) | ETH/USD | same_close | 476 | -0.84 | -1.66 | -98.91 |
| Abnormal-day momentum (L/S) | ETH/USD | next_open | 476 | -0.82 | -1.69 | -98.78 |
| Abnormal-day momentum (L/S) | ETH/USD | next_close | 476 | -0.37 | -0.72 | -95.59 |
| TSMOM 28d (long/flat) | SOL/USD | same_close | 65 | 11.29 | 1.31 | -64.09 |
| TSMOM 28d (long/flat) | SOL/USD | next_open | 65 | 11.26 | 1.31 | -64.19 |
| TSMOM 28d (long/flat) | SOL/USD | next_close | 65 | 8.59 | 1.11 | -69.31 |
| Donchian 20/10 (long/flat) | SOL/USD | same_close | 25 | 16.33 | 0.91 | -74.62 |
| Donchian 20/10 (long/flat) | SOL/USD | next_open | 24 | 16.92 | 0.91 | -74.68 |
| Donchian 20/10 (long/flat) | SOL/USD | next_close | 24 | 19.07 | 0.99 | -75.45 |
| Abnormal-day momentum (L/S) | SOL/USD | same_close | 396 | -0.69 | -0.92 | -97.24 |
| Abnormal-day momentum (L/S) | SOL/USD | next_open | 395 | -0.67 | -0.94 | -97.02 |
| Abnormal-day momentum (L/S) | SOL/USD | next_close | 395 | -0.5 | -0.63 | -94.78 |

#### Buy & hold by period (xs_sharpe = minus T-bill)

| symbol | period | from | CAGR% | vol% | maxDD% | sharpe | xs_sharpe |
|---|---|---|---|---|---|---|---|
| BTC/USD | full | 2021-01-01 | 17.84 | 56.97 | -76.68 | 0.57 | 0.52 |
| BTC/USD | last 2y | 2024-11-03 | 5.61 | 44.27 | -53.07 | 0.34 | 0.25 |
| ETH/USD | full | 2021-01-01 | 21.25 | 76.84 | -79.31 | 0.63 | 0.59 |
| ETH/USD | last 2y | 2024-11-03 | -4.31 | 69.19 | -67.61 | 0.28 | 0.22 |
| SOL/USD | full | 2021-01-01 | 48.32 | 112.0 | -96.91 | 0.91 | 0.89 |
| SOL/USD | last 2y | 2024-11-03 | -24.8 | 76.51 | -76.23 | 0.01 | -0.05 |
| SOL/USD | ex-2021 (2022+) | 2022-01-01 | -52.14 | 92.36 | -95.55 | -0.33 | -0.36 |

#### TSMOM variants (next-open fills)

| symbol | period | idle cash | trades | exp% | CAGR% | maxDD% | sharpe | xs_sharpe | B&H sharpe | B&H xs_sharpe |
|---|---|---|---|---|---|---|---|---|---|---|
| BTC/USD | full | 0% | 91 | 2.11 | 24.87 | -48.98 | 0.78 | 0.69 | 0.57 | 0.52 |
| BTC/USD | last 2y | 0% | 35 | -0.38 | 8.96 | -36.53 | 0.44 | 0.3 | 0.34 | 0.25 |
| BTC/USD | full | T-bill | 91 | 2.11 | 26.58 | -48.62 | 0.81 | 0.73 | 0.57 | 0.52 |
| BTC/USD | last 2y | T-bill | 35 | -0.38 | 10.99 | -34.69 | 0.5 | 0.36 | 0.34 | 0.25 |
| ETH/USD | full | 0% | 91 | 1.62 | 14.68 | -56.96 | 0.52 | 0.46 | 0.63 | 0.59 |
| ETH/USD | last 2y | 0% | 29 | 2.13 | 22.13 | -41.86 | 0.67 | 0.58 | 0.28 | 0.22 |
| ETH/USD | full | T-bill | 91 | 1.62 | 16.5 | -56.96 | 0.55 | 0.49 | 0.63 | 0.59 |
| ETH/USD | last 2y | T-bill | 29 | 2.13 | 24.72 | -40.94 | 0.72 | 0.62 | 0.28 | 0.22 |
| SOL/USD | full | 0% | 65 | 11.26 | 104.11 | -64.19 | 1.31 | 1.27 | 0.91 | 0.89 |
| SOL/USD | last 2y | 0% | 28 | -1.28 | -5.98 | -54.14 | 0.1 | 0.01 | 0.01 | -0.05 |
| SOL/USD | ex-2021 (2022+) | 0% | 52 | 0.55 | 1.15 | -54.14 | 0.27 | 0.21 | -0.33 | -0.36 |
| SOL/USD | full | T-bill | 65 | 11.26 | 107.04 | -64.19 | 1.33 | 1.29 | 0.91 | 0.89 |
| SOL/USD | last 2y | T-bill | 28 | -1.28 | -4.05 | -52.33 | 0.14 | 0.06 | 0.01 | -0.05 |
| SOL/USD | ex-2021 (2022+) | T-bill | 52 | 0.55 | 3.0 | -52.33 | 0.31 | 0.24 | -0.33 | -0.36 |

#### Bootstrap 95% CI: Sharpe(TSMOM) - Sharpe(B&H), circular block 20d, 5000 reps

| symbol | period | idle cash | sharpe | diff | lo95 | hi95 | P(diff<=0) | CI excludes 0 |
|---|---|---|---|---|---|---|---|---|
| BTC/USD | full | 0% | raw | 0.2 | -0.41 | 0.8 | 0.27 | no |
| BTC/USD | last 2y | 0% | raw | 0.09 | -1.02 | 1.13 | 0.48 | no |
| BTC/USD | full | T-bill | excess | 0.21 | -0.4 | 0.8 | 0.26 | no |
| BTC/USD | last 2y | T-bill | excess | 0.11 | -1.0 | 1.15 | 0.47 | no |
| ETH/USD | full | 0% | raw | -0.11 | -0.76 | 0.56 | 0.63 | no |
| ETH/USD | last 2y | 0% | raw | 0.39 | -0.65 | 1.39 | 0.25 | no |
| ETH/USD | full | T-bill | excess | -0.1 | -0.75 | 0.57 | 0.62 | no |
| ETH/USD | last 2y | T-bill | excess | 0.41 | -0.64 | 1.4 | 0.24 | no |
| SOL/USD | full | 0% | raw | 0.4 | -0.29 | 1.1 | 0.12 | no |
| SOL/USD | last 2y | 0% | raw | 0.09 | -0.97 | 1.12 | 0.45 | no |
| SOL/USD | ex-2021 (2022+) | 0% | raw | 0.6 | -0.22 | 1.36 | 0.08 | no |
| SOL/USD | full | T-bill | excess | 0.41 | -0.28 | 1.11 | 0.12 | no |
| SOL/USD | last 2y | T-bill | excess | 0.1 | -0.95 | 1.13 | 0.45 | no |
| SOL/USD | ex-2021 (2022+) | T-bill | excess | 0.61 | -0.21 | 1.37 | 0.08 | no |

#### Data quality (Alpaca only)

| symbol | daily_missing | largest_hole_days | open_vs_prev_close_med% | open_vs_prev_close_max% | gaps>1% | daily_vs_30m_close_max% | 30m_bars | 30m_missing | 30m_zero_range | 30m_stale | 30m_zero_vol |
|---|---|---|---|---|---|---|---|---|---|---|---|
| BTC/USD | 0 | 0 | 0.02 | 6.18 | 5 | 0.01 | 2880 | 0 | 0 | 0 | 8 |
| ETH/USD | 0 | 0 | 0.03 | 7.91 | 8 | 0.0 | 2880 | 0 | 0 | 0 | 123 |
| SOL/USD | 418 | 416 | 0.04 | 10.29 | 13 | 0.0 | 2880 | 0 | 0 | 0 | 257 |

