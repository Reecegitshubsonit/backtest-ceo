### OOS summary

| symbol | OOS 2023-2026 return% | sharpe | maxDD% | alpha IR | alpha IR 95% CI | beta | shuffled alpha IR mean | shuffles >= real | B&H return% | B&H sharpe | B&H maxDD% |
|---|---|---|---|---|---|---|---|---|---|---|---|
| BTC/USD | 1.74 | 0.11 | -9.61 | -0.54 | [-1.61, 0.34] | 0.07 | -0.87 | 1/5 | 363.98 | 1.09 | -53.07 |
| ETH/USD | -17.7 | -0.5 | -22.13 | -1.02 | [-1.95, -0.02] | 0.09 | -0.34 | 5/5 | 88.16 | 0.57 | -67.61 |
| SOL/USD | -4.22 | -0.02 | -19.94 | -0.39 | [-1.30, 0.54] | 0.12 |  |  | 26.2 | 0.42 | -76.25 |

### TSMOM 28d

| symbol | TSMOM28 return% | TSMOM28 sharpe | TSMOM28 maxDD% |
|---|---|---|---|
| BTC/USD | 296.03 | 1.21 | -36.41 |
| ETH/USD | 104.28 | 0.65 | -46.32 |
| SOL/USD | 33.49 | 0.46 | -50.33 |

### Per fold

| run | test year | symbol | eligible | picked | trades (all picks) | win% | exp%/trade | return% | sharpe | maxDD% | alpha IR | beta | B&H return% | B&H sharpe |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| real | 2023 | BTC/USD | 1672 | 10 | 68 | 29.41 | -0.22 | -1.51 | -0.51 | -4.05 | -1.82 | 0.03 | 155.88 | 2.35 |
| real | 2023 | ETH/USD | 1672 | 10 | 81 | 48.15 | 0.18 | 1.47 | 0.46 | -5.36 | -0.3 | 0.03 | 90.84 | 1.61 |
| real | 2023 | SOL/USD | 1672 | 10 | 49 | 59.18 | 1.28 | 6.38 | 1.35 | -4.44 | 0.86 | 0.03 | 116.05 | 1.41 |
| real | 2024 | BTC/USD | 3553 | 10 | 58 | 50.0 | -0.78 | -4.49 | -1.03 | -5.84 | -2.06 | 0.04 | 120.93 | 1.75 |
| real | 2024 | ETH/USD | 3553 | 10 | 75 | 48.0 | -0.8 | -6.11 | -0.67 | -9.98 | -1.63 | 0.09 | 45.98 | 0.9 |
| real | 2024 | SOL/USD | 3553 | 10 | 14 | 35.71 | -2.44 | -3.17 | -0.83 | -3.7 | -1.35 | 0.05 | 20.14 | 0.64 |
| real | 2025 | BTC/USD | 4681 | 10 | 55 | 52.73 | 0.48 | 2.73 | 0.43 | -3.62 | 0.67 | 0.13 | -6.35 | 0.05 |
| real | 2025 | ETH/USD | 4681 | 10 | 61 | 50.82 | -0.49 | -3.97 | -0.22 | -14.97 | -0.51 | 0.13 | -10.89 | 0.22 |
| real | 2025 | SOL/USD | 4681 | 10 | 78 | 43.59 | -1.4 | -9.57 | -0.34 | -19.94 | -0.54 | 0.22 | -34.11 | -0.06 |
| real | 2026 | BTC/USD | 5564 | 10 | 38 | 44.74 | 1.59 | 5.28 | 0.76 | -4.69 | 0.92 | 0.09 | -12.36 | -0.13 |
| real | 2026 | ETH/USD | 5564 | 10 | 43 | 20.93 | -2.36 | -10.04 | -1.66 | -11.36 | -1.69 | 0.05 | -24.2 | -0.25 |
| real | 2026 | SOL/USD | 5564 | 10 | 50 | 40.0 | 0.63 | 2.84 | 0.37 | -8.57 | 0.67 | 0.1 | -26.22 | -0.27 |

### Forward candidates

| # | strategy |
|---|---|
| 1 | 1d | rsi2_below(5) | vol_below_avg | weekdays | hold 24 | stop 2ATR |
| 2 | 1d | rsi2_below(5) | vol_below_avg | weekdays | hold 48 | stop 2ATR |
| 3 | 1d | volume_spike_up(3.0) | above_sma50 | atr_low | weekdays | hold 6 | stop 1ATR |
| 4 | 1d | volume_spike_up(3.0) | above_sma50 | vol_above_avg | weekdays | hold 6 | stop 1ATR | tp 4ATR |
| 5 | 1d | volume_spike_up(3.0) | above_sma50 | atr_low | vol_above_avg | hold 6 | stop 1ATR |
| 6 | 1d | volume_spike_up(3.0) | above_sma50 | weekdays | hold 6 | stop 1ATR | tp 2ATR |
| 7 | 4h | hammer | below_sma200 | atr_high | 08-16 | weekend | hold 24 | tp 2ATR |
| 8 | 4h | big_bar_up(2.0) | above_sma200 | vol_above_avg | 16-24 | weekdays | hold 12 | tp 4ATR |
| 9 | 1d | inside_breakout | above_sma50 | vol_above_avg | hold 12 | stop 1ATR |
| 10 | 1d | up3 | above_sma200 | atr_low | vol_above_avg | hold 6 | tp 4ATR |
