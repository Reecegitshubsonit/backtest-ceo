## Round 6b: mean reversion and candles with market-on-close fills

Look-ahead check (SPY RSI(2) < 10): the 15:55-price signal agrees with the close-based one on 99.0% of days; of 224 close-based entries, 208 would also have fired at 15:55.

SPY Sharpe: search 0.64, validate 1.22, holdout 0.70.

| Family | Combos | Median search | Median validate | Median holdout (second look) | Share beating SPY on search AND validate |
|---|---:|---:|---:|---:|---:|
| F3_meanrev | 10,123 | -0.00 | 0.42 | 0.53 | 0.2% |
| F4_candles | 734 | 0.08 | 0.12 | 0.27 | 0.1% |

Next-open fills (round 6 search) for comparison: F3 median search -0.05 / validate 0.32; F4 0.13 / 0.16.

Top 10 by the same pipeline (279 of 500 pass neighbors):

| Family | Params | Search | Validate | Holdout (second look) | Search trades |
|---|---|---:|---:|---:|---:|
| F3_meanrev | ind=26, exit=revert, maxhold=10, trend=sma200, sizing=slot, univ=GTAA5 | 0.62 | 1.69 | -0.07 | 80 |
| F3_meanrev | ind=27, exit=sma5, maxhold=20, trend=none, sizing=slot, univ=SPY | 0.98 | 1.64 | 1.00 | 212 |
| F3_meanrev | ind=27, exit=sma5, maxhold=10, trend=none, sizing=slot, univ=SPY | 0.98 | 1.64 | 1.00 | 212 |
| F3_meanrev | ind=27, exit=sma5, maxhold=2, trend=none, sizing=slot, univ=SPY | 0.64 | 1.60 | 0.40 | 244 |
| F3_meanrev | ind=27, exit=sma5, maxhold=5, trend=none, sizing=slot, univ=SPY | 0.81 | 1.54 | 0.91 | 214 |
| F4_candles | pattern=nr7_up, hold=10, trend=above200, sizing=slot, univ=SPY | 0.70 | 1.49 | -0.96 | 94 |
| F3_meanrev | ind=28, exit=revert, maxhold=5, trend=none, sizing=slot, univ=SPY | 0.59 | 1.48 | 0.27 | 298 |
| F3_meanrev | ind=29, exit=sma5, maxhold=10, trend=none, sizing=slot, univ=SPY | 0.66 | 1.45 | 0.87 | 338 |
| F3_meanrev | ind=29, exit=sma5, maxhold=20, trend=none, sizing=slot, univ=SPY | 0.69 | 1.45 | 0.87 | 338 |
| F3_meanrev | ind=34, exit=sma5, maxhold=20, trend=none, sizing=slot, univ=ALL16 | 0.63 | 1.40 | -0.02 | 546 |
