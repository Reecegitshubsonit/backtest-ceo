# 100,000-combination crypto search, plus the live 4h legs on full history

Scripts: `engine/scripts/crypto_search.py` (search, ~75 s) and `engine/scripts/live_legs_4h.py` (live legs, ~15 s).
Generated tables: `docs/crypto-search-tables.md`, `docs/live-legs-4h-tables.md`. Data: Alpaca 1h bars 2021-01-01 → 2026-11-02 (4h and daily built from them).
Costs: 0.60% round trip (0.25% fee + 0.05% slippage per side). Long only, signal at the close, fill at the next bar's open.

## Bottom line

- **Nothing survives the search.**
  - All 7 strategies that reached the holdout lose money on BTC or ETH, or trade fewer than 30 times.
  - The search found no more on real data than on shuffled data. On 10 shuffled copies with all time structure destroyed, the same pipeline found about as many "winners", and they scored higher in validation (median 1.15 vs 0.53 real).
  - Adjusted for 100,000 combinations, the deflated Sharpe is 0.00 for every finalist. Whatever looked good was luck.
- **Live leg SuperTrend 4h on ETH (long only) is the one rule that holds up on full history.**
  - 2021+: +1.79% per trade, Sharpe 0.67 vs buy & hold 0.46.
  - Last 2 years: +1.69% per trade, Sharpe 0.63 vs 0.28.
  - Caveats: its parameters were fixed in earlier work on overlapping data, and it is 1 of 6 live leg/coin pairs tested here, so treat it as promising, not proven.
- **Live legs that lose:**
  - EMA200 + ADX25 4h loses on BTC and SOL in both windows.
  - SuperTrend on BTC is negative over the last 2 years.

## Level 2 data

Not used. Alpaca serves only the latest crypto order-book snapshot (`/latest/orderbooks`); the historical order-book endpoint returns 404. No other venue was reachable: Coinbase is blocked by the network policy, and Binance is excluded by choice. So the search has no order-book features.

## Search design

- **Space:** 2,029,536 combinations, of which 100,000 were drawn at random (seed 20261103). Each combination is one choice from each of:
  - Timeframe: 1h, 4h, 1d.
  - Entry signal (30):
    - momentum over 12–192 bars;
    - EMA crosses 5/20, 10/50, 20/100, 50/200;
    - Donchian breakouts over 10–100 bars;
    - RSI(14) < 25/30, RSI(2) < 5/10, RSI(14) > 60/70;
    - Bollinger lower/upper band;
    - z-score below −2;
    - candle patterns: engulfing, hammer, inside-bar breakout, 3 down closes, 3 up closes, big range bar;
    - volume spike.
  - Trend filter: none, above SMA50, above SMA200, below SMA200.
  - Volatility filter: none, ATR below / above its 500-bar median.
  - Volume filter: none, above / below its 20-bar average.
  - Time of day (UTC): none, 00–08, 08–16, 16–24.
  - Day of week: none, weekdays, weekend.
  - Holding period: 1–48 bars.
  - ATR stop: none, 1, 2, 3.
  - ATR take-profit: none, 2, 4.
- **Time split (calendar days):**
  - Search: 2021-01-01 → 2024-07-02 (60%).
  - Validate: → 2025-09-02 (20%).
  - Holdout: 2025-09-03 → 2026-11-02 (20%).
- **Pipeline:**
  1. Rank by mean daily Sharpe on BTC and ETH in the search window, requiring ≥ 30 trades per coin.
  2. Take the top 1,000 and keep those positive on both coins in both search and validation, with ≥ 30 validation trades each. 16 remained.
  3. Neighbour check: change one step in holding period, stop, target or entry lookback, or drop one filter. At least 2/3 of neighbours must stay positive in search and validation. 7 of 16 passed; fewer than 10, so 7 went to the holdout.
  4. Holdout run **once**. The result is written to disk on first evaluation and reused, never recomputed.
- **Corrections for trying so many combinations:**
  - Deflated Sharpe (Bailey & López de Prado) with N = 100,000 on the search Sharpe and N = 10 on the holdout.
  - The same 100,000 combinations and the same pipeline on 10 shuffled datasets. In each, 1h bar shapes in the search and validation windows are permuted jointly for BTC and ETH, which keeps the return distribution and destroys every time pattern.
- **Checks:**
  - The search engine (numba) matches a plain-Python reimplementation exactly (780 trades, same expectancy).
  - SOL is not in the search; it is shown separately in the holdout. Its 417-day data hole lies before the holdout.

## Luck benchmark — real vs 10 shuffled datasets

| Metric | Real | Shuffled mean | Shuffled max | Share of shuffles ≥ real |
|---|---|---|---|---|
| Best search score (mean Sharpe BTC/ETH) | 1.24 | 1.37 | 1.63 | 60% |
| 99th percentile search score | 0.45 | 0.56 | 0.84 | 60% |
| Top-1,000 passing validation | 16 | 52 | 149 | 70% |
| Robust after neighbour check | 7 | 7.7 | 10 | 70% |
| Median validation score of finalists | 0.53 | 1.15 | 1.58 | 100% |

Real data is not distinguishable from noise; if anything it does worse. A possible reason, not tested here: short-horizon mean reversion and volatility clustering in real crypto returns, which would hurt long-only rules after fees.

## Holdout 2025-09-03 → 2026-11-02 (tested once)

| # | Strategy | Coin | Trades | Win % | Exp %/trade | Max DD % | Sharpe | Verdict |
|---|---|---|---|---|---|---|---|---|
| 1 | 4h volume spike ×3, above SMA200, volume above average, hold 12 | BTC | 42 | 35.7 | −0.44 | −29.1 | −0.92 | loses |
| | | ETH | 41 | 34.1 | −0.84 | −33.9 | −1.34 | |
| | | SOL | 32 | 34.4 | −0.69 | −27.1 | −0.96 | |
| 2 | 4h momentum 24, above SMA200, 00–08 UTC, weekdays, hold 48, stop 2 ATR | BTC | 31 | 35.5 | −0.43 | −27.8 | −0.52 | loses |
| | | ETH | 37 | 18.9 | −1.34 | −57.0 | −1.23 | |
| | | SOL | 27 | 33.3 | +0.71 | −28.2 | 0.45 | |
| 3 | 4h EMA 50/200, volume above average, hold 48, target 4 ATR | BTC | 32 | 43.8 | −0.99 | −33.2 | −1.11 | loses |
| | | ETH | 30 | 40.0 | −1.39 | −47.9 | −0.90 | |
| | | SOL | 30 | 43.3 | −1.00 | −56.0 | −0.59 | |
| 4 | 4h EMA 10/50, above SMA200, volume below average, 00–08 UTC, hold 48, stop 3 ATR | BTC | 26 | 46.2 | +0.09 | −20.6 | 0.08 | < 30 trades |
| | | ETH | 31 | 32.3 | −0.77 | −46.8 | −0.57 | |
| | | SOL | 24 | 37.5 | +0.97 | −29.2 | 0.58 | |
| 5 | 1d EMA 20/100, weekend, hold 6 | BTC | 22 | 36.4 | −0.91 | −27.0 | −0.86 | < 30 trades |
| | | ETH | 20 | 40.0 | −1.93 | −40.8 | −1.06 | |
| | | SOL | 18 | 38.9 | +0.17 | −26.7 | 0.07 | |
| 6 | 4h EMA 5/20, 08–16 UTC, weekend, hold 48, stop 3 ATR | BTC | 32 | 31.3 | −1.82 | −48.1 | −2.02 | loses |
| | | ETH | 30 | 30.0 | −2.23 | −51.4 | −1.75 | |
| | | SOL | 29 | 31.0 | −0.97 | −33.4 | −0.68 | |
| 7 | 4h momentum 192, 00–08 UTC, weekdays, hold 48, stop 3 ATR | BTC | 40 | 40.0 | −0.58 | −37.5 | −0.71 | loses |
| | | ETH | 39 | 38.5 | −0.60 | −45.9 | −0.52 | |
| | | SOL | 40 | 35.0 | −1.14 | −60.3 | −0.96 | |

Deflated Sharpe: 0.00 for every finalist, both on search (N = 100,000) and on holdout (N = 10).

**References, same holdout:**

| Coin | Buy & hold return | B&H Sharpe | B&H max DD | TSMOM 28d return | TSMOM Sharpe | TSMOM max DD | TSMOM trades |
|---|---|---|---|---|---|---|---|
| BTC | −31.1% | −0.53 | −53.1% | −3.9% | 0.00 | −24.0% | 19 |
| ETH | −48.0% | −0.61 | −66.8% | −24.8% | −0.58 | −37.0% | 20 |
| SOL | −56.2% | −0.74 | −74.9% | −30.9% | −0.65 | −52.0% | 16 |

The holdout was a bear market. The search finalists lost less than buy & hold on max drawdown, but so did TSMOM 28d, which is simpler. None beat TSMOM 28d on both BTC and ETH. Rank 4 edged it on BTC only (Sharpe 0.08 vs 0.00, 26 trades), and lost on ETH.

## Live 4h legs on full history (2021+, and last 2 years)

Long only as traded live. Trades held across the SOL data hole are excluded. Full table in `docs/live-legs-4h-tables.md`.

| Leg | Coin | Window | Trades | Win % | Exp %/trade | Max DD % | Sharpe | B&H Sharpe |
|---|---|---|---|---|---|---|---|---|
| SuperTrend + EMA200 + ADX | BTC | 2021+ | 106 | 34.9 | +0.51 | −44.4 | 0.24 | 0.41 |
| | BTC | last 2y | 40 | 35.0 | −0.20 | −42.8 | −0.19 | 0.34 |
| | **ETH** | **2021+** | **96** | **39.6** | **+1.79** | **−38.9** | **0.67** | **0.46** |
| | **ETH** | **last 2y** | **32** | **37.5** | **+1.69** | **−37.1** | **0.63** | **0.28** |
| | SOL | 2021+ | 74 | 36.5 | +1.69 | −88.1 | 0.23 | 0.49 |
| | SOL | last 2y | 32 | 40.6 | +0.65 | −44.3 | 0.30 | 0.01 |
| EMA200 + ADX25 | BTC | 2021+ | 158 | 27.2 | −0.07 | −40.8 | −0.10 | 0.41 |
| | BTC | last 2y | 61 | 27.9 | −0.29 | −37.0 | −0.41 | 0.34 |
| | ETH | 2021+ | 134 | 34.3 | +1.19 | −38.1 | 0.81 | 0.46 |
| | ETH | last 2y | 51 | 21.6 | +0.11 | −38.1 | 0.03 | 0.28 |
| | SOL | 2021+ | 128 | 23.4 | −0.29 | −91.9 | −0.22 | 0.49 |
| | SOL | last 2y | 51 | 25.5 | −0.73 | −58.1 | −0.54 | 0.01 |

## Recommendation

1. Keep the paper legs **SuperTrend ETH 4h** and, for now, **SuperTrend BTC 4h** (positive over 2021+, slightly negative over the last 2 years).
2. Switch off **EMA200 + ADX BTC 4h**: negative in both windows. EMA200 + ADX ETH 4h has been flat for 2 years; it is a candidate to switch off. Not changed in this commit.
3. Stop searching for new rules on Alpaca price bars alone. 100,000 combinations did no better than shuffled data. A real edge needs different information (funding, basis, order flow), lower costs, or both.
