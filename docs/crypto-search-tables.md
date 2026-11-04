Split: search 2021-01-01 -> 2024-07-02, validate -> 2025-09-02, holdout 2025-09-03 -> 2026-11-02. Space 2,029,536; drawn 100,000; cost 0.60% round trip.

### Verdicts

| rank | strategy | verdict |
|---|---|---|
| 1 | 4h | volume_spike_up(3.0) | above_sma200 | vol_above_avg | hold 12 | REJECT: holdout loses on BTC or ETH |
| 2 | 4h | tsmom(24) | above_sma200 | 00-08 | weekdays | hold 48 | stop 2ATR | REJECT: holdout loses on BTC or ETH |
| 3 | 4h | ema_cross((50, 200)) | vol_above_avg | hold 48 | tp 4ATR | REJECT: holdout loses on BTC or ETH |
| 4 | 4h | ema_cross((10, 50)) | above_sma200 | vol_below_avg | 00-08 | hold 48 | stop 3ATR | REJECT: < 30 holdout trades |
| 5 | 1d | ema_cross((20, 100)) | weekend | hold 6 | REJECT: < 30 holdout trades |
| 6 | 4h | ema_cross((5, 20)) | 08-16 | weekend | hold 48 | stop 3ATR | REJECT: holdout loses on BTC or ETH |
| 7 | 4h | tsmom(192) | 00-08 | weekdays | hold 48 | stop 3ATR | REJECT: holdout loses on BTC or ETH |

### Holdout, top 10 robust (BTC, ETH; SOL separately)

| rank | strategy | symbol | search sharpe | valid sharpe | H trades | H win% | H exp% | H maxDD% | H sharpe | DSR search (N=100k) | DSR holdout (N=10) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 4h | volume_spike_up(3.0) | above_sma200 | vol_above_avg | hold 12 | BTC/USD | 0.12 | 1.18 | 42 | 35.71 | -0.44 | -29.1 | -0.92 | 0.0 | 0.0 |
| 1 | 4h | volume_spike_up(3.0) | above_sma200 | vol_above_avg | hold 12 | ETH/USD | 1.24 | 0.69 | 41 | 34.15 | -0.84 | -33.9 | -1.34 | 0.0 | 0.0 |
| 1 | 4h | volume_spike_up(3.0) | above_sma200 | vol_above_avg | hold 12 | SOL/USD |  |  | 32 | 34.38 | -0.69 | -27.13 | -0.96 | 0.0 | 0.0 |
| 2 | 4h | tsmom(24) | above_sma200 | 00-08 | weekdays | hold 48 | stop 2ATR | BTC/USD | 0.49 | 0.17 | 31 | 35.48 | -0.43 | -27.84 | -0.52 | 0.0 | 0.0 |
| 2 | 4h | tsmom(24) | above_sma200 | 00-08 | weekdays | hold 48 | stop 2ATR | ETH/USD | 0.78 | 1.21 | 37 | 18.92 | -1.34 | -56.97 | -1.23 | 0.0 | 0.0 |
| 2 | 4h | tsmom(24) | above_sma200 | 00-08 | weekdays | hold 48 | stop 2ATR | SOL/USD |  |  | 27 | 33.33 | 0.71 | -28.18 | 0.45 | 0.0 | 0.0 |
| 3 | 4h | ema_cross((50, 200)) | vol_above_avg | hold 48 | tp 4ATR | BTC/USD | 0.53 | 0.29 | 32 | 43.75 | -0.99 | -33.18 | -1.11 | 0.0 | 0.0 |
| 3 | 4h | ema_cross((50, 200)) | vol_above_avg | hold 48 | tp 4ATR | ETH/USD | 0.75 | 1.07 | 30 | 40.0 | -1.39 | -47.93 | -0.9 | 0.0 | 0.0 |
| 3 | 4h | ema_cross((50, 200)) | vol_above_avg | hold 48 | tp 4ATR | SOL/USD |  |  | 30 | 43.33 | -1.0 | -55.95 | -0.59 | 0.0 | 0.0 |
| 4 | 4h | ema_cross((10, 50)) | above_sma200 | vol_below_avg | 00-08 | hold 48 | stop 3ATR | BTC/USD | 0.22 | 0.12 | 26 | 46.15 | 0.09 | -20.55 | 0.08 | 0.0 | 0.0 |
| 4 | 4h | ema_cross((10, 50)) | above_sma200 | vol_below_avg | 00-08 | hold 48 | stop 3ATR | ETH/USD | 0.89 | 0.93 | 31 | 32.26 | -0.77 | -46.76 | -0.57 | 0.0 | 0.0 |
| 4 | 4h | ema_cross((10, 50)) | above_sma200 | vol_below_avg | 00-08 | hold 48 | stop 3ATR | SOL/USD |  |  | 24 | 37.5 | 0.97 | -29.17 | 0.58 | 0.0 | 0.0 |
| 5 | 1d | ema_cross((20, 100)) | weekend | hold 6 | BTC/USD | 0.33 | 0.35 | 22 | 36.36 | -0.91 | -27.03 | -0.86 | 0.0 | 0.0 |
| 5 | 1d | ema_cross((20, 100)) | weekend | hold 6 | ETH/USD | 0.46 | 0.47 | 20 | 40.0 | -1.93 | -40.75 | -1.06 | 0.0 | 0.0 |
| 5 | 1d | ema_cross((20, 100)) | weekend | hold 6 | SOL/USD |  |  | 18 | 38.89 | 0.17 | -26.68 | 0.07 | 0.0 | 0.0 |
| 6 | 4h | ema_cross((5, 20)) | 08-16 | weekend | hold 48 | stop 3ATR | BTC/USD | 0.22 | 0.26 | 32 | 31.25 | -1.82 | -48.06 | -2.02 | 0.0 | 0.0 |
| 6 | 4h | ema_cross((5, 20)) | 08-16 | weekend | hold 48 | stop 3ATR | ETH/USD | 0.74 | 0.53 | 30 | 30.0 | -2.23 | -51.42 | -1.75 | 0.0 | 0.0 |
| 6 | 4h | ema_cross((5, 20)) | 08-16 | weekend | hold 48 | stop 3ATR | SOL/USD |  |  | 29 | 31.03 | -0.97 | -33.38 | -0.68 | 0.0 | 0.0 |
| 7 | 4h | tsmom(192) | 00-08 | weekdays | hold 48 | stop 3ATR | BTC/USD | 0.17 | 0.07 | 40 | 40.0 | -0.58 | -37.49 | -0.71 | 0.0 | 0.0 |
| 7 | 4h | tsmom(192) | 00-08 | weekdays | hold 48 | stop 3ATR | ETH/USD | 0.54 | 0.71 | 39 | 38.46 | -0.6 | -45.93 | -0.52 | 0.0 | 0.0 |
| 7 | 4h | tsmom(192) | 00-08 | weekdays | hold 48 | stop 3ATR | SOL/USD |  |  | 40 | 35.0 | -1.14 | -60.3 | -0.96 | 0.0 | 0.0 |

### Holdout references

| symbol | B&H sharpe | B&H maxDD% | B&H return% | TSMOM28 trades | TSMOM28 sharpe | TSMOM28 maxDD% | TSMOM28 return% |
|---|---|---|---|---|---|---|---|
| BTC/USD | -0.53 | -53.07 | -31.07 | 19 | -0.0 | -23.96 | -3.86 |
| ETH/USD | -0.61 | -66.8 | -47.99 | 20 | -0.58 | -37.0 | -24.77 |
| SOL/USD | -0.74 | -74.89 | -56.16 | 16 | -0.65 | -51.95 | -30.93 |

### Luck benchmark summary

| metric | real | shuffled mean | shuffled max | share of shuffles >= real |
|---|---|---|---|---|
| best search score | 1.24 | 1.37 | 1.63 | 0.6 |
| search p99 | 0.45 | 0.55 | 0.84 | 0.6 |
| top-1000 pass validation | 16.0 | 52.1 | 149.0 | 0.7 |
| robust found | 7.0 | 7.7 | 10.0 | 0.7 |
| median valid score of top 10 | 0.53 | 1.15 | 1.58 | 1.0 |
| best valid score | 0.94 | 1.5 | 2.11 | 0.8 |

### Luck benchmark per run

| data | eligible combos | best search score | search p99 | top-1000 pass validation | robust found | median valid score of top 10 | best valid score |
|---|---|---|---|---|---|---|---|
| real | 48569 | 1.24 | 0.45 | 16 | 7 | 0.53 | 0.94 |
| shuffled_0 | 53273 | 1.63 | 0.84 | 3 | 1 | 0.79 | 0.79 |
| shuffled_1 | 54193 | 1.61 | 0.83 | 30 | 10 | 0.76 | 1.69 |
| shuffled_2 | 52719 | 1.44 | 0.4 | 62 | 10 | 1.13 | 1.4 |
| shuffled_3 | 53702 | 1.36 | 0.62 | 6 | 1 | 0.88 | 0.88 |
| shuffled_4 | 52622 | 1.18 | 0.47 | 149 | 10 | 1.58 | 2.01 |
| shuffled_5 | 53598 | 1.48 | 0.4 | 84 | 10 | 1.4 | 2.11 |
| shuffled_6 | 52758 | 1.1 | 0.38 | 72 | 10 | 1.54 | 1.81 |
| shuffled_7 | 53003 | 1.19 | 0.49 | 66 | 10 | 0.94 | 1.26 |
| shuffled_8 | 53654 | 1.53 | 0.69 | 14 | 5 | 1.24 | 1.44 |
| shuffled_9 | 53021 | 1.19 | 0.41 | 35 | 10 | 1.25 | 1.62 |

### Neighbour checks

| rank | strategy | neighbours ok | robust |
|---|---|---|---|
| 1 | 4h | volume_spike_up(3.0) | above_sma200 | vol_above_avg | hold 12 | 4/6 | True |
| 2 | 4h | rsi2_below(10) | 00-08 | hold 48 | 2/5 | False |
| 3 | 4h | ema_cross((5, 20)) | above_sma200 | vol_below_avg | 08-16 | hold 48 | stop 2ATR | 5/8 | False |
| 4 | 4h | tsmom(24) | above_sma200 | 00-08 | weekdays | hold 48 | stop 2ATR | 7/9 | True |
| 5 | 4h | ema_cross((50, 200)) | vol_above_avg | hold 48 | tp 4ATR | 4/5 | True |
| 6 | 4h | ema_cross((5, 20)) | above_sma50 | 08-16 | weekend | hold 48 | stop 3ATR | 3/7 | False |
| 7 | 4h | ema_cross((10, 50)) | above_sma200 | vol_below_avg | 00-08 | hold 48 | stop 3ATR | 7/8 | True |
| 8 | 4h | tsmom(192) | atr_high | weekdays | hold 24 | tp 2ATR | 4/8 | False |
| 9 | 4h | tsmom(12) | above_sma200 | atr_low | vol_below_avg | 08-16 | hold 24 | stop 2ATR | 5/10 | False |
| 10 | 1d | ema_cross((20, 100)) | weekend | hold 6 | 5/7 | True |
| 11 | 4h | ema_cross((5, 20)) | 08-16 | weekend | hold 48 | stop 3ATR | 4/6 | True |
| 12 | 4h | tsmom(192) | 00-08 | weekdays | hold 48 | stop 3ATR | 4/6 | True |
| 13 | 4h | tsmom(24) | above_sma200 | hold 24 | 3/7 | False |
| 14 | 4h | tsmom(192) | 00-08 | hold 48 | tp 2ATR | 3/6 | False |
| 15 | 4h | ema_cross((50, 200)) | vol_above_avg | 08-16 | weekdays | hold 24 | 4/8 | False |
| 16 | 4h | bb_upper(2.0) | above_sma50 | vol_above_avg | 16-24 | hold 12 | tp 4ATR | 2/7 | False |
