## Selection, shuffled data

Combinations tried: 100,176; eligible: 88,370. SPY Sharpe (xs T-bill): search 0.92, validate 0.36.
Best search-split Sharpe of any combination: 1.61. Expected max Sharpe of 100,176 unskilled trials (deflated-Sharpe hurdle): 1.56.
White's Reality Check (H0: nothing beats vol-matched SPY): search split p = 1.000; validate split over the 500 shortlisted p = 0.142.
Shortlist 500 → 360 pass the neighbor test → top 10 (10 under the 2-per-group cap, 0 filled uncapped).

| # | Family | Params | Search Sharpe | Validate Sharpe | Neighbors (median search / validate) | DSR vs 0 | DSR vs vol-matched SPY |
|---|---|---|---:|---:|---|---:|---:|
| 1 | I1_orb | orbars=1, dir=long, entry=break, stop=atr25, target=3, quiet=False, gapf=none, size=risk1, sym=QQQ | 1.42 | 3.03 | 4 (1.48 / 2.62) | 0.355 | 0.012 |
| 2 | I1_orb | orbars=1, dir=long, entry=break, stop=atr25, target=2, quiet=False, gapf=none, size=risk1, sym=QQQ | 1.49 | 2.93 | 4 (1.40 / 2.47) | 0.431 | 0.017 |
| 3 | F4_candles | pattern=inside_up, hold=5, trend=below200, sizing=slot, univ=SPY | 1.06 | 2.30 | 2 (1.07 / 1.99) | 0.103 | 0.002 |
| 4 | F4_candles | pattern=inside_up, hold=10, trend=below200, sizing=slot, univ=SPY | 1.41 | 2.20 | 1 (1.06 / 2.30) | 0.352 | 0.017 |
| 5 | F3_meanrev | ind=25, exit=revert, maxhold=20, trend=none, sizing=allin, univ=GTAA5 | 1.02 | 2.15 | 3 (0.83 / 1.80) | 0.091 | 0.002 |
| 6 | I1_orb | orbars=1, dir=long, entry=break, stop=atr25, target=2, quiet=True, gapf=none, size=1x, sym=SPY | 1.02 | 1.55 | 4 (0.72 / 1.17) | 0.085 | 0.002 |
| 7 | F3_meanrev | ind=7, exit=revert, maxhold=20, trend=sma200, sizing=allin, univ=GTAA5 | 1.05 | 1.33 | 3 (0.87 / 1.22) | 0.087 | 0.002 |
| 8 | I1_orb | orbars=1, dir=long, entry=break, stop=atr25, target=2, quiet=False, gapf=none, size=1x, sym=SPY | 1.05 | 1.22 | 4 (0.86 / 0.69) | 0.100 | 0.002 |
| 9 | F2_rotation | looks=23, skip=21, K=4, absf=none, weight=invvol, rebal=quarterly, vt=None, univ=GTAA5 | 1.06 | 0.94 | 4 (0.92 / 0.74) | 0.107 | 0.005 |
| 10 | F2_rotation | looks=14, skip=21, K=4, absf=none, weight=invvol, rebal=quarterly, vt=None, univ=GTAA5 | 1.06 | 0.89 | 4 (0.86 / 0.60) | 0.108 | 0.006 |

| Family | Combos | Eligible | Median search Sharpe | Best search Sharpe | Median validate Sharpe | Share beating SPY on both splits |
|---|---:|---:|---:|---:|---:|---:|
| F1_trend | 5,760 | 5,520 | 0.58 | 1.11 | 0.06 | 0.3% |
| F2_rotation | 53,568 | 53,268 | 0.61 | 1.12 | 0.14 | 0.8% |
| F3_meanrev | 11,025 | 8,073 | 0.17 | 1.26 | 0.33 | 0.3% |
| F4_candles | 735 | 628 | 0.12 | 1.41 | 0.35 | 0.6% |
| F5_voltarget | 10,080 | 7,633 | 0.66 | 0.96 | -0.77 | 0.0% |
| I1_orb | 14,400 | 8,640 | 0.14 | 1.61 | 0.25 | 3.8% |
| I2_noiseband | 4,608 | 4,608 | -0.20 | 0.78 | 0.72 | 0.0% |
