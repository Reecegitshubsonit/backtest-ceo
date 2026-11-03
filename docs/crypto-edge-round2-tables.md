cost/side 0.30%; daily variants tried 41; holdout 2024-07-01 -> 2026-11-02; intraday 2026-09-04 -> 2026-11-02

### Daily verdicts

| family | kind | chosen param | source | verdict |
|---|---|---|---|---|
| Dual-momentum rotation | practitioner | 28 | Antonacci dual momentum across BTC/ETH/SOL | SURVIVES (edge): beats B&H holdout Sharpe on 1/1 |
| TSMOM + ATR trail | own | 2 | TSMOM 28d with m x ATR20 trailing stop | REJECT: holdout Sharpe/expectancy > 0 on only 1/3 |
| TSMOM | published | 28 | Liu & Tsyvinski 2021 (RFS) | SURVIVES (edge): beats B&H holdout Sharpe on 2/3 |
| Weekly TSMOM | own | 28 | TSMOM checked Mondays only (less whipsaw) | REJECT: < 30 trades on SOL/USD |
| BTC-trend gate | own | 100 | hold coin only while BTC > its SMA | SURVIVES (edge): beats B&H holdout Sharpe on 3/3 |
| TSMOM + low vol | own | (28, 0.9) | TSMOM and 20d vol below its 1y quantile | REJECT: holdout Sharpe/expectancy > 0 on only 1/3 |
| Price > SMA | practitioner | 200 | 200-day MA rule (Faber-style), common BTC filter | REJECT: < 30 trades on BTC/USD, ETH/USD, SOL/USD |
| Donchian ensemble | published | 0.34 | Zarattini, Pagani & Barbon 2025 (SFI 25-80), simplified | REJECT: < 30 trades on ETH/USD, SOL/USD |
| SMA cross | practitioner | (10, 30) | golden-cross family | SURVIVES (edge): beats B&H holdout Sharpe on 2/3 |
| TSMOM vote 10-90d | published | 3 | Moskowitz-Ooi-Pedersen style multi-lookback; arXiv 2009.12155 | SURVIVES (edge): beats B&H holdout Sharpe on 3/3 |
| Low-vol regime | published | 0.9 | Moreira & Muir 2017 (JF) vol-managed, binary | REJECT: < 30 trades on BTC/USD, ETH/USD, SOL/USD |
| Trend dip-buy | own | 30 | close > SMA100 and RSI(3) < x; exit RSI(3) > 70 or 10 days | REJECT: holdout Sharpe/expectancy > 0 on only 1/3 |
| RSI(2) pullback | practitioner | 5 | Connors RSI(2), SMA200 filter, exit > SMA5 | REJECT: < 30 trades on BTC/USD, ETH/USD, SOL/USD |

### Daily holdout results (chosen variant per family)

| family | kind | param | symbol | design sharpe | H trades | H win% | H exp% | H maxDD% | H sharpe | H CAGR% | B&H H sharpe | B&H H maxDD% | dSharpe CI | full trades | DSR(holdout) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Dual-momentum rotation | practitioner | 28 | BTC/ETH/SOL | 1.39 | 37 | 43.24 | 1.64 | -51.1 | 0.48 | 12.43 | 0.14 | -64.32 | [-0.60, 1.17] | 81 | 0.3 |
| TSMOM + ATR trail | own | 2 | BTC/USD | 1.15 | 41 | 34.15 | -0.97 | -44.33 | -0.69 | -17.21 | 0.41 | -53.07 | [-2.36, 0.04] | 91 | 0.01 |
| TSMOM + ATR trail | own | 2 | ETH/USD | 0.92 | 37 | 35.14 | -0.17 | -39.7 | -0.07 | -7.92 | 0.07 | -67.61 | [-1.38, 0.89] | 91 | 0.09 |
| TSMOM + ATR trail | own | 2 | SOL/USD | 2.11 | 29 | 41.38 | 1.1 | -37.83 | 0.44 | 10.22 | 0.05 | -76.23 | [-0.75, 1.37] | 65 | 0.29 |
| TSMOM | published | 28 | BTC/USD | 1.12 | 41 | 36.59 | 0.31 | -36.53 | 0.08 | -1.95 | 0.41 | -53.07 | [-1.46, 0.76] | 91 | 0.13 |
| TSMOM | published | 28 | ETH/USD | 0.69 | 37 | 32.43 | 0.58 | -41.86 | 0.21 | 0.08 | 0.07 | -67.61 | [-0.92, 1.04] | 91 | 0.17 |
| TSMOM | published | 28 | SOL/USD | 1.9 | 29 | 31.03 | 0.18 | -54.14 | 0.17 | -2.96 | 0.05 | -76.23 | [-0.91, 1.08] | 65 | 0.17 |
| Weekly TSMOM | own | 28 | BTC/USD | 0.67 | 18 | 44.44 | 1.37 | -30.27 | 0.26 | 3.22 | 0.41 | -53.07 | [-1.30, 0.93] | 35 | 0.19 |
| Weekly TSMOM | own | 28 | ETH/USD | 0.88 | 12 | 33.33 | 5.4 | -36.46 | 0.68 | 22.96 | 0.07 | -67.61 | [-0.50, 1.64] | 32 | 0.41 |
| Weekly TSMOM | own | 28 | SOL/USD | 1.88 | 15 | 40.0 | -0.77 | -58.86 | -0.05 | -12.33 | 0.05 | -76.23 | [-1.24, 0.90] | 28 | 0.1 |
| BTC-trend gate | own | 100 | BTC/USD | 0.51 | 19 | 15.79 | 1.81 | -27.8 | 0.47 | 9.62 | 0.41 | -53.07 | [-0.99, 0.97] | 40 | 0.29 |
| BTC-trend gate | own | 100 | ETH/USD | 1.05 | 19 | 15.79 | 4.13 | -42.95 | 0.39 | 7.75 | 0.07 | -67.61 | [-0.64, 1.24] | 40 | 0.25 |
| BTC-trend gate | own | 100 | SOL/USD | 1.5 | 16 | 37.5 | 1.74 | -41.65 | 0.41 | 8.67 | 0.05 | -76.23 | [-0.56, 1.23] | 33 | 0.27 |
| TSMOM + low vol | own | (28, 0.9) | BTC/USD | 1.2 | 41 | 39.02 | 0.52 | -36.53 | 0.2 | 1.72 | 0.41 | -53.07 | [-1.31, 0.83] | 79 | 0.17 |
| TSMOM + low vol | own | (28, 0.9) | ETH/USD | 0.63 | 39 | 30.77 | -0.15 | -41.86 | -0.05 | -9.49 | 0.07 | -67.61 | [-1.14, 0.80] | 87 | 0.09 |
| TSMOM + low vol | own | (28, 0.9) | SOL/USD | 1.2 | 23 | 21.74 | -1.29 | -51.95 | -0.24 | -14.48 | 0.05 | -76.23 | [-1.48, 0.84] | 56 | 0.06 |
| Price > SMA | practitioner | 200 | BTC/USD | 0.68 | 14 | 28.57 | 1.3 | -33.41 | 0.22 | 2.01 | 0.41 | -53.07 | [-1.21, 0.86] | 25 | 0.18 |
| Price > SMA | practitioner | 200 | ETH/USD | 0.97 | 10 | 20.0 | 0.73 | -39.72 | 0.1 | -3.63 | 0.07 | -67.61 | [-1.16, 1.04] | 15 | 0.14 |
| Price > SMA | practitioner | 200 | SOL/USD | 1.16 | 4 | 25.0 | -1.06 | -33.29 | 0.12 | -1.98 | 0.05 | -76.23 | [-1.16, 1.26] | 9 | 0.15 |
| Donchian ensemble | published | 0.34 | BTC/USD | 0.07 | 13 | 30.77 | 2.61 | -27.24 | 0.54 | 11.25 | 0.41 | -53.07 | [-1.05, 1.20] | 33 | 0.34 |
| Donchian ensemble | published | 0.34 | ETH/USD | 0.85 | 11 | 36.36 | 2.72 | -42.95 | 0.36 | 6.82 | 0.07 | -67.61 | [-1.05, 1.43] | 29 | 0.24 |
| Donchian ensemble | published | 0.34 | SOL/USD | 1.66 | 12 | 25.0 | -1.2 | -50.76 | -0.13 | -8.94 | 0.05 | -76.23 | [-1.65, 1.14] | 21 | 0.08 |
| SMA cross | practitioner | (10, 30) | BTC/USD | 0.46 | 19 | 26.32 | -0.57 | -39.83 | -0.23 | -10.09 | 0.41 | -53.07 | [-1.77, 0.45] | 45 | 0.06 |
| SMA cross | practitioner | (10, 30) | ETH/USD | 0.55 | 17 | 41.18 | 2.6 | -47.3 | 0.35 | 6.02 | 0.07 | -67.61 | [-0.83, 1.25] | 38 | 0.23 |
| SMA cross | practitioner | (10, 30) | SOL/USD | 1.47 | 14 | 42.86 | 2.08 | -50.73 | 0.29 | 3.2 | 0.05 | -76.23 | [-1.01, 1.36] | 34 | 0.22 |
| TSMOM vote 10-90d | published | 3 | BTC/USD | 0.51 | 25 | 24.0 | 1.89 | -27.64 | 0.58 | 13.67 | 0.41 | -53.07 | [-0.87, 1.08] | 77 | 0.36 |
| TSMOM vote 10-90d | published | 3 | ETH/USD | 0.47 | 33 | 33.33 | 1.47 | -51.0 | 0.42 | 9.38 | 0.07 | -67.61 | [-0.79, 1.32] | 81 | 0.27 |
| TSMOM vote 10-90d | published | 3 | SOL/USD | 0.96 | 31 | 29.03 | 0.64 | -53.16 | 0.31 | 3.26 | 0.05 | -76.23 | [-0.79, 1.27] | 72 | 0.22 |
| Low-vol regime | published | 0.9 | BTC/USD | 0.78 | 4 | 50.0 | 3.82 | -57.03 | 0.27 | 2.22 | 0.41 | -53.07 | [-0.45, 0.09] | 13 | 0.2 |
| Low-vol regime | published | 0.9 | ETH/USD | 0.45 | 6 | 33.33 | -2.72 | -66.37 | -0.02 | -19.58 | 0.07 | -67.61 | [-0.48, 0.33] | 16 | 0.1 |
| Low-vol regime | published | 0.9 | SOL/USD | 0.37 | 3 | 66.67 | 4.91 | -72.52 | 0.1 | -10.6 | 0.05 | -76.23 | [-0.76, 0.87] | 11 | 0.15 |
| Trend dip-buy | own | 30 | BTC/USD | 0.47 | 23 | 47.83 | -0.98 | -34.94 | -0.46 | -10.8 | 0.41 | -53.07 | [-2.12, 0.30] | 57 | 0.03 |
| Trend dip-buy | own | 30 | ETH/USD | 0.15 | 18 | 61.11 | 0.59 | -16.65 | 0.17 | 1.23 | 0.07 | -67.61 | [-1.33, 1.37] | 53 | 0.16 |
| Trend dip-buy | own | 30 | SOL/USD | 0.13 | 15 | 33.33 | -3.5 | -47.97 | -0.68 | -24.28 | 0.05 | -76.23 | [-2.04, 0.50] | 32 | 0.01 |
| RSI(2) pullback | practitioner | 5 | BTC/USD | 0.25 | 12 | 75.0 | 1.08 | -8.56 | 0.67 | 5.41 | 0.41 | -53.07 | [-1.20, 1.73] | 23 | 0.41 |
| RSI(2) pullback | practitioner | 5 | ETH/USD | 0.1 | 7 | 57.14 | 2.09 | -8.52 | 0.55 | 6.15 | 0.07 | -67.61 | [nan, nan] | 21 | 0.33 |
| RSI(2) pullback | practitioner | 5 | SOL/USD | 0.16 | 6 | 50.0 | -0.28 | -17.43 | -0.03 | -1.85 | 0.05 | -76.23 | [nan, nan] | 12 | 0.11 |

### Intraday verdicts

| strategy | verdict |
|---|---|
| SuperTrend+EMA200+ADX 4h (live leg, L/S) | REJECT: < 30 trades on BTC/USD, ETH/USD, SOL/USD |
| EMA200+ADX25 4h (live leg, L/S) | REJECT: < 30 trades on BTC/USD, ETH/USD, SOL/USD |
| EMA 9/21 1h + 2% stop (live leg, long) | REJECT: net expectancy > 0 on only 0/3 |
| RSI(2) 1h, EMA200 filter (long) | REJECT: < 30 trades on BTC/USD, ETH/USD, SOL/USD |
| Bollinger 20/2 1h reversion (long) | REJECT: < 30 trades on BTC/USD, ETH/USD, SOL/USD |
| Donchian 20/10 4h breakout (long) | REJECT: < 30 trades on BTC/USD, ETH/USD, SOL/USD |
| Grid bot single-slot 2% 1h (long) | REJECT: < 30 trades on BTC/USD, ETH/USD, SOL/USD |

### Intraday results (60 days)

| strategy | symbol | tf | trades | win% | exp% | maxDD% | sharpe | CAGR% | gross exp% | status |
|---|---|---|---|---|---|---|---|---|---|---|
| SuperTrend+EMA200+ADX 4h (live leg, L/S) | BTC/USD | 4h | 5 | 40.0 | 0.13 | -11.2 | 0.15 | 0.64 | 0.73 | REJECT (<30) |
| EMA200+ADX25 4h (live leg, L/S) | BTC/USD | 4h | 12 | 8.33 | -1.3 | -20.1 | -3.83 | -61.79 | -0.7 | REJECT (<30) |
| EMA 9/21 1h + 2% stop (live leg, long) | BTC/USD | 1h | 34 | 5.88 | -0.77 | -24.3 | -5.05 | -80.03 | -0.17 | ok |
| RSI(2) 1h, EMA200 filter (long) | BTC/USD | 1h | 22 | 4.55 | -0.65 | -12.82 | -9.04 | -58.11 | -0.05 | REJECT (<30) |
| Bollinger 20/2 1h reversion (long) | BTC/USD | 1h | 25 | 24.0 | -0.6 | -13.97 | -7.78 | -60.05 | 0.0 | REJECT (<30) |
| Donchian 20/10 4h breakout (long) | BTC/USD | 4h | 5 | 20.0 | -1.78 | -14.69 | -2.15 | -42.66 | -1.18 | REJECT (<30) |
| Grid bot single-slot 2% 1h (long) | BTC/USD | 1h | 5 | 80.0 | -0.84 | -11.55 | -0.85 | -25.49 | -0.44 | REJECT (<30) |
| SuperTrend+EMA200+ADX 4h (live leg, L/S) | ETH/USD | 4h | 5 | 40.0 | -0.47 | -12.24 | -0.68 | -20.61 | 0.13 | REJECT (<30) |
| EMA200+ADX25 4h (live leg, L/S) | ETH/USD | 4h | 11 | 27.27 | -0.98 | -12.41 | -2.56 | -51.59 | -0.38 | REJECT (<30) |
| EMA 9/21 1h + 2% stop (live leg, long) | ETH/USD | 1h | 42 | 11.9 | -0.8 | -34.29 | -6.21 | -87.48 | -0.2 | ok |
| RSI(2) 1h, EMA200 filter (long) | ETH/USD | 1h | 24 | 16.67 | -0.72 | -15.87 | -7.36 | -65.56 | -0.12 | REJECT (<30) |
| Bollinger 20/2 1h reversion (long) | ETH/USD | 1h | 27 | 51.85 | -0.44 | -13.33 | -3.77 | -52.62 | 0.16 | REJECT (<30) |
| Donchian 20/10 4h breakout (long) | ETH/USD | 4h | 5 | 20.0 | -2.9 | -16.49 | -3.64 | -59.4 | -2.3 | REJECT (<30) |
| Grid bot single-slot 2% 1h (long) | ETH/USD | 1h | 6 | 83.33 | -1.65 | -17.79 | -1.81 | -51.14 | -1.25 | REJECT (<30) |
| SuperTrend+EMA200+ADX 4h (live leg, L/S) | SOL/USD | 4h | 3 | 66.67 | 6.14 | -7.26 | 2.83 | 173.6 | 6.74 | REJECT (<30) |
| EMA200+ADX25 4h (live leg, L/S) | SOL/USD | 4h | 8 | 50.0 | -0.35 | -12.74 | -0.76 | -19.93 | 0.25 | REJECT (<30) |
| EMA 9/21 1h + 2% stop (live leg, long) | SOL/USD | 1h | 35 | 8.57 | -1.04 | -36.0 | -5.03 | -89.83 | -0.44 | ok |
| RSI(2) 1h, EMA200 filter (long) | SOL/USD | 1h | 24 | 25.0 | -0.72 | -15.13 | -7.27 | -65.31 | -0.12 | REJECT (<30) |
| Bollinger 20/2 1h reversion (long) | SOL/USD | 1h | 27 | 40.74 | -0.62 | -16.33 | -4.07 | -64.98 | -0.02 | REJECT (<30) |
| Donchian 20/10 4h breakout (long) | SOL/USD | 4h | 3 | 33.33 | -0.58 | -12.79 | -0.33 | -12.61 | 0.02 | REJECT (<30) |
| Grid bot single-slot 2% 1h (long) | SOL/USD | 1h | 8 | 87.5 | -1.73 | -24.84 | -2.17 | -65.77 | -1.33 | REJECT (<30) |

### Design grid (2021-01-01 -> 2024-06-30, all variants)

| family | param | symbol | trades | win% | exp% | maxDD% | sharpe | CAGR% |
|---|---|---|---|---|---|---|---|---|
| TSMOM | 14 | BTC/USD | 80 | 35.0 | 1.07 | -57.24 | 0.5 | 12.95 |
| TSMOM | 14 | ETH/USD | 72 | 30.56 | 1.97 | -50.24 | 0.66 | 23.39 |
| TSMOM | 14 | SOL/USD | 53 | 30.19 | 12.36 | -84.44 | 1.34 | 128.48 |
| TSMOM | 28 | BTC/USD | 50 | 34.0 | 3.58 | -48.98 | 1.12 | 46.81 |
| TSMOM | 28 | ETH/USD | 54 | 38.89 | 2.34 | -56.96 | 0.69 | 25.63 |
| TSMOM | 28 | SOL/USD | 36 | 41.67 | 20.19 | -64.19 | 1.9 | 290.68 |
| TSMOM | 56 | BTC/USD | 29 | 37.93 | 4.94 | -44.34 | 0.97 | 36.03 |
| TSMOM | 56 | ETH/USD | 29 | 34.48 | 3.84 | -60.24 | 0.69 | 26.06 |
| TSMOM | 56 | SOL/USD | 25 | 28.0 | 15.69 | -70.8 | 1.15 | 90.18 |
| TSMOM | 90 | BTC/USD | 28 | 28.57 | 2.02 | -59.74 | 0.22 | 0.74 |
| TSMOM | 90 | ETH/USD | 22 | 27.27 | 2.52 | -71.13 | 0.36 | 3.82 |
| TSMOM | 90 | SOL/USD | 17 | 11.76 | 12.01 | -70.34 | 0.73 | 29.59 |
| TSMOM vote 10-90d | 3 | BTC/USD | 52 | 30.77 | 1.45 | -64.66 | 0.51 | 13.3 |
| TSMOM vote 10-90d | 3 | ETH/USD | 48 | 29.17 | 1.35 | -63.15 | 0.47 | 11.05 |
| TSMOM vote 10-90d | 3 | SOL/USD | 41 | 19.51 | 10.89 | -76.23 | 0.96 | 60.57 |
| TSMOM vote 10-90d | 4 | BTC/USD | 41 | 26.83 | 2.38 | -37.46 | 0.76 | 21.74 |
| TSMOM vote 10-90d | 4 | ETH/USD | 51 | 23.53 | 0.19 | -58.99 | 0.17 | -2.99 |
| TSMOM vote 10-90d | 4 | SOL/USD | 44 | 27.27 | 7.04 | -65.09 | 0.85 | 43.43 |
| TSMOM vote 10-90d | 5 | BTC/USD | 45 | 31.11 | 0.67 | -28.73 | 0.33 | 5.4 |
| TSMOM vote 10-90d | 5 | ETH/USD | 44 | 36.36 | 1.15 | -43.0 | 0.45 | 10.29 |
| TSMOM vote 10-90d | 5 | SOL/USD | 17 | 29.41 | 11.3 | -48.07 | 0.98 | 45.28 |
| Donchian ensemble | 0.34 | BTC/USD | 20 | 35.0 | 0.02 | -51.04 | 0.07 | -3.66 |
| Donchian ensemble | 0.34 | ETH/USD | 18 | 50.0 | 6.55 | -41.84 | 0.85 | 32.79 |
| Donchian ensemble | 0.34 | SOL/USD | 9 | 55.56 | 60.26 | -48.77 | 1.66 | 180.68 |
| Donchian ensemble | 0.5 | BTC/USD | 20 | 35.0 | 0.02 | -51.04 | 0.07 | -3.66 |
| Donchian ensemble | 0.5 | ETH/USD | 18 | 50.0 | 6.55 | -41.84 | 0.85 | 32.79 |
| Donchian ensemble | 0.5 | SOL/USD | 9 | 55.56 | 60.26 | -48.77 | 1.66 | 180.68 |
| Donchian ensemble | 0.67 | BTC/USD | 12 | 50.0 | 0.47 | -24.52 | 0.12 | 0.25 |
| Donchian ensemble | 0.67 | ETH/USD | 9 | 66.67 | 7.5 | -18.61 | 0.77 | 18.29 |
| Donchian ensemble | 0.67 | SOL/USD | 5 | 80.0 | 32.72 | -44.02 | 1.05 | 46.26 |
| Price > SMA | 50 | BTC/USD | 34 | 20.59 | 2.34 | -60.9 | 0.53 | 14.09 |
| Price > SMA | 50 | ETH/USD | 38 | 23.68 | 1.34 | -59.79 | 0.35 | 4.49 |
| Price > SMA | 50 | SOL/USD | 25 | 20.0 | 24.85 | -69.48 | 1.27 | 111.09 |
| Price > SMA | 100 | BTC/USD | 21 | 28.57 | 4.15 | -39.9 | 0.51 | 13.02 |
| Price > SMA | 100 | ETH/USD | 33 | 12.12 | -0.14 | -76.39 | 0.1 | -9.7 |
| Price > SMA | 100 | SOL/USD | 20 | 10.0 | 11.86 | -81.19 | 0.34 | -6.79 |
| Price > SMA | 150 | BTC/USD | 13 | 30.77 | 8.94 | -37.58 | 0.74 | 22.89 |
| Price > SMA | 150 | ETH/USD | 16 | 37.5 | 3.72 | -50.61 | 0.47 | 11.92 |
| Price > SMA | 150 | SOL/USD | 11 | 18.18 | 29.24 | -71.89 | 0.83 | 39.58 |
| Price > SMA | 200 | BTC/USD | 11 | 18.18 | 8.11 | -36.88 | 0.68 | 19.71 |
| Price > SMA | 200 | ETH/USD | 5 | 60.0 | 26.54 | -36.33 | 0.97 | 39.59 |
| Price > SMA | 200 | SOL/USD | 5 | 20.0 | 74.42 | -61.9 | 1.16 | 65.08 |
| SMA cross | (10, 30) | BTC/USD | 26 | 34.62 | 2.99 | -65.92 | 0.46 | 11.26 |
| SMA cross | (10, 30) | ETH/USD | 21 | 42.86 | 4.34 | -54.91 | 0.55 | 16.37 |
| SMA cross | (10, 30) | SOL/USD | 20 | 40.0 | 31.42 | -77.71 | 1.47 | 161.04 |
| SMA cross | (20, 50) | BTC/USD | 15 | 26.67 | 0.39 | -60.49 | 0.12 | -3.46 |
| SMA cross | (20, 50) | ETH/USD | 14 | 57.14 | 3.24 | -56.52 | 0.43 | 8.15 |
| SMA cross | (20, 50) | SOL/USD | 7 | 28.57 | 70.99 | -69.1 | 1.19 | 95.77 |
| SMA cross | (50, 100) | BTC/USD | 8 | 37.5 | 1.82 | -62.9 | 0.05 | -6.87 |
| SMA cross | (50, 100) | ETH/USD | 8 | 37.5 | -4.2 | -78.56 | 0.04 | -13.28 |
| SMA cross | (50, 100) | SOL/USD | 6 | 33.33 | 8.02 | -80.16 | 0.43 | -1.3 |
| SMA cross | (50, 200) | BTC/USD | 3 | 66.67 | 24.23 | -44.95 | 0.62 | 17.11 |
| SMA cross | (50, 200) | ETH/USD | 4 | 75.0 | 17.4 | -51.38 | 0.74 | 25.67 |
| SMA cross | (50, 200) | SOL/USD | 2 | 50.0 | 161.03 | -75.29 | 0.99 | 52.62 |
| Low-vol regime | 0.5 | BTC/USD | 27 | 40.74 | 1.03 | -76.23 | 0.17 | -1.79 |
| Low-vol regime | 0.5 | ETH/USD | 25 | 44.0 | 3.59 | -80.69 | 0.42 | 8.98 |
| Low-vol regime | 0.5 | SOL/USD | 23 | 43.48 | 11.81 | -86.73 | 0.64 | 22.69 |
| Low-vol regime | 0.7 | BTC/USD | 17 | 52.94 | 4.1 | -71.82 | 0.43 | 9.78 |
| Low-vol regime | 0.7 | ETH/USD | 21 | 52.38 | 6.64 | -78.23 | 0.62 | 20.57 |
| Low-vol regime | 0.7 | SOL/USD | 7 | 28.57 | 53.21 | -93.43 | 0.41 | -1.93 |
| Low-vol regime | 0.9 | BTC/USD | 9 | 44.44 | 19.36 | -72.77 | 0.78 | 30.64 |
| Low-vol regime | 0.9 | ETH/USD | 10 | 50.0 | 5.96 | -81.84 | 0.45 | 9.51 |
| Low-vol regime | 0.9 | SOL/USD | 8 | 25.0 | 7.84 | -95.64 | 0.37 | -11.8 |
| RSI(2) pullback | 5 | BTC/USD | 11 | 63.64 | 0.73 | -12.12 | 0.25 | 1.97 |
| RSI(2) pullback | 5 | ETH/USD | 14 | 64.29 | 0.13 | -19.59 | 0.1 | 0.3 |
| RSI(2) pullback | 5 | SOL/USD | 6 | 66.67 | 0.76 | -20.41 | 0.16 | 1.2 |
| RSI(2) pullback | 10 | BTC/USD | 28 | 64.29 | 0.73 | -13.34 | 0.41 | 5.38 |
| RSI(2) pullback | 10 | ETH/USD | 26 | 53.85 | -0.44 | -23.82 | -0.09 | -3.78 |
| RSI(2) pullback | 10 | SOL/USD | 11 | 45.45 | -0.34 | -23.54 | 0.03 | -2.08 |
| RSI(2) pullback | 15 | BTC/USD | 36 | 61.11 | 0.44 | -15.54 | 0.32 | 4.0 |
| RSI(2) pullback | 15 | ETH/USD | 35 | 60.0 | -0.12 | -20.51 | 0.02 | -2.0 |
| RSI(2) pullback | 15 | SOL/USD | 17 | 52.94 | -0.68 | -48.82 | -0.12 | -8.27 |
| BTC-trend gate | 50 | BTC/USD | 34 | 20.59 | 2.34 | -60.9 | 0.53 | 14.09 |
| BTC-trend gate | 50 | ETH/USD | 34 | 35.29 | 3.87 | -54.12 | 0.83 | 32.86 |
| BTC-trend gate | 50 | SOL/USD | 25 | 32.0 | 27.67 | -75.31 | 1.55 | 155.81 |
| BTC-trend gate | 100 | BTC/USD | 21 | 28.57 | 4.15 | -39.9 | 0.51 | 13.02 |
| BTC-trend gate | 100 | ETH/USD | 21 | 52.38 | 8.48 | -36.92 | 1.05 | 46.32 |
| BTC-trend gate | 100 | SOL/USD | 17 | 58.82 | 21.64 | -49.07 | 1.5 | 132.97 |
| BTC-trend gate | 200 | BTC/USD | 11 | 18.18 | 8.11 | -36.88 | 0.68 | 19.71 |
| BTC-trend gate | 200 | ETH/USD | 11 | 36.36 | 7.17 | -33.19 | 0.63 | 18.96 |
| BTC-trend gate | 200 | SOL/USD | 9 | 55.56 | 20.56 | -50.0 | 1.06 | 60.94 |
| TSMOM + low vol | (28, 0.7) | BTC/USD | 40 | 35.0 | 2.36 | -43.86 | 0.84 | 23.95 |
| TSMOM + low vol | (28, 0.7) | ETH/USD | 46 | 39.13 | 3.13 | -44.48 | 0.92 | 34.32 |
| TSMOM + low vol | (28, 0.7) | SOL/USD | 30 | 36.67 | 9.49 | -53.56 | 1.09 | 60.04 |
| TSMOM + low vol | (28, 0.9) | BTC/USD | 38 | 36.84 | 4.2 | -48.98 | 1.2 | 42.43 |
| TSMOM + low vol | (28, 0.9) | ETH/USD | 48 | 39.58 | 1.97 | -45.19 | 0.63 | 19.76 |
| TSMOM + low vol | (28, 0.9) | SOL/USD | 33 | 33.33 | 10.89 | -44.28 | 1.2 | 76.25 |
| TSMOM + low vol | (56, 0.7) | BTC/USD | 25 | 40.0 | 3.26 | -42.55 | 0.7 | 18.76 |
| TSMOM + low vol | (56, 0.7) | ETH/USD | 35 | 40.0 | 1.89 | -60.4 | 0.53 | 14.46 |
| TSMOM + low vol | (56, 0.7) | SOL/USD | 24 | 25.0 | 6.94 | -79.2 | 0.42 | 7.84 |
| TSMOM + low vol | (56, 0.9) | BTC/USD | 27 | 37.04 | 4.97 | -44.34 | 0.96 | 31.52 |
| TSMOM + low vol | (56, 0.9) | ETH/USD | 31 | 35.48 | 1.27 | -58.88 | 0.4 | 8.35 |
| TSMOM + low vol | (56, 0.9) | SOL/USD | 27 | 22.22 | 8.18 | -73.95 | 0.58 | 18.77 |
| Trend dip-buy | 20 | BTC/USD | 22 | 59.09 | 0.34 | -25.51 | 0.15 | 0.99 |
| Trend dip-buy | 20 | ETH/USD | 22 | 40.91 | -1.25 | -37.93 | -0.04 | -7.59 |
| Trend dip-buy | 20 | SOL/USD | 9 | 44.44 | -3.22 | -35.08 | -0.16 | -12.25 |
| Trend dip-buy | 30 | BTC/USD | 34 | 61.76 | 1.06 | -26.02 | 0.47 | 8.91 |
| Trend dip-buy | 30 | ETH/USD | 35 | 48.57 | -0.02 | -44.37 | 0.15 | -2.18 |
| Trend dip-buy | 30 | SOL/USD | 17 | 52.94 | 0.0 | -64.97 | 0.13 | -8.24 |
| Weekly TSMOM | 28 | BTC/USD | 17 | 41.18 | 6.76 | -65.59 | 0.67 | 22.03 |
| Weekly TSMOM | 28 | ETH/USD | 20 | 45.0 | 7.51 | -49.82 | 0.88 | 41.79 |
| Weekly TSMOM | 28 | SOL/USD | 13 | 46.15 | 71.32 | -56.18 | 1.88 | 287.01 |
| Weekly TSMOM | 56 | BTC/USD | 12 | 25.0 | 10.64 | -55.89 | 0.63 | 19.46 |
| Weekly TSMOM | 56 | ETH/USD | 9 | 44.44 | 13.84 | -61.27 | 0.67 | 24.69 |
| Weekly TSMOM | 56 | SOL/USD | 9 | 44.44 | 21.36 | -73.9 | 0.87 | 46.43 |
| TSMOM + ATR trail | 2 | BTC/USD | 50 | 38.0 | 3.44 | -44.27 | 1.15 | 45.72 |
| TSMOM + ATR trail | 2 | ETH/USD | 54 | 38.89 | 2.96 | -38.2 | 0.92 | 38.43 |
| TSMOM + ATR trail | 2 | SOL/USD | 36 | 41.67 | 20.28 | -59.89 | 2.11 | 324.67 |
| TSMOM + ATR trail | 3 | BTC/USD | 50 | 34.0 | 2.79 | -48.98 | 0.94 | 34.65 |
| TSMOM + ATR trail | 3 | ETH/USD | 54 | 38.89 | 2.54 | -49.97 | 0.76 | 30.2 |
| TSMOM + ATR trail | 3 | SOL/USD | 36 | 41.67 | 18.36 | -59.89 | 1.9 | 268.6 |
| TSMOM + ATR trail | 4 | BTC/USD | 50 | 34.0 | 3.58 | -48.98 | 1.12 | 46.81 |
| TSMOM + ATR trail | 4 | ETH/USD | 54 | 38.89 | 2.48 | -49.97 | 0.71 | 27.24 |
| TSMOM + ATR trail | 4 | SOL/USD | 36 | 41.67 | 20.14 | -64.19 | 1.9 | 288.23 |
| Dual-momentum rotation | 14 | BTC/ETH/SOL | 62 | 40.32 | 6.2 | -86.45 | 0.76 | 32.99 |
| Dual-momentum rotation | 28 | BTC/ETH/SOL | 44 | 50.0 | 22.38 | -63.77 | 1.39 | 127.43 |
| Dual-momentum rotation | 56 | BTC/ETH/SOL | 28 | 39.29 | 14.52 | -70.19 | 1.01 | 63.97 |
