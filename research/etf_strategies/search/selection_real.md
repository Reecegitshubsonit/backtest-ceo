## Selection, real data

Combinations tried: 100,176; eligible: 88,835. SPY Sharpe (xs T-bill): search 0.64, validate 1.23.
Best search-split Sharpe of any combination: 1.62. Expected max Sharpe of 100,176 unskilled trials (deflated-Sharpe hurdle): 1.39.
White's Reality Check (H0: nothing beats vol-matched SPY): search split p = 0.974; validate split over the 500 shortlisted p = 0.702.
Shortlist 500 → 485 pass the neighbor test → top 10 (6 under the 2-per-group cap, 4 filled uncapped).

| # | Family | Params | Search Sharpe | Validate Sharpe | Neighbors (median search / validate) | DSR vs 0 | DSR vs vol-matched SPY |
|---|---|---|---:|---:|---|---:|---:|
| 1 | I2_noiseband | look=14, mult=1.0, freq=6, stop=max, last=71, quiet=False, size=vol2, side=both, sym=QQQ | 1.35 | 2.19 | 6 (1.28 / 1.94) | 0.453 | 0.006 |
| 2 | I2_noiseband | look=14, mult=1.0, freq=6, stop=band, last=71, quiet=False, size=vol2, side=both, sym=QQQ | 1.35 | 2.19 | 6 (1.28 / 1.94) | 0.453 | 0.006 |
| 3 | I2_noiseband | look=14, mult=1.0, freq=6, stop=vwap, last=71, quiet=False, size=vol2, side=both, sym=SPY | 1.25 | 1.77 | 6 (1.05 / 1.30) | 0.354 | 0.004 |
| 4 | I2_noiseband | look=7, mult=1.25, freq=3, stop=vwap, last=71, quiet=False, size=vol2, side=long, sym=SPY | 1.24 | 1.65 | 4 (1.20 / 1.34) | 0.347 | 0.008 |
| 5 | I1_orb | orbars=3, dir=both, entry=break, stop=mid, target=5, quiet=False, gapf=with, size=1x, sym=QQQ | 1.23 | 1.56 | 6 (0.95 / 1.24) | 0.333 | 0.004 |
| 6 | I1_orb | orbars=2, dir=both, entry=break, stop=mid, target=10, quiet=False, gapf=with, size=risk1, sym=QQQ | 1.21 | 1.51 | 5 (1.00 / 1.48) | 0.302 | 0.003 |
| 7 | I2_noiseband | look=7, mult=1.0, freq=6, stop=vwap, last=71, quiet=False, size=vol2, side=both, sym=QQQ | 1.55 | 2.16 | 5 (1.43 / 1.87) | 0.664 | 0.015 |
| 8 | I2_noiseband | look=7, mult=1.0, freq=6, stop=band, last=71, quiet=False, size=vol2, side=both, sym=QQQ | 1.42 | 2.14 | 5 (1.22 / 1.88) | 0.529 | 0.008 |
| 9 | I2_noiseband | look=7, mult=1.0, freq=6, stop=max, last=71, quiet=False, size=vol2, side=both, sym=QQQ | 1.42 | 2.14 | 5 (1.22 / 1.88) | 0.529 | 0.008 |
| 10 | I2_noiseband | look=14, mult=1.0, freq=12, stop=band, last=71, quiet=False, size=vol2, side=both, sym=QQQ | 1.22 | 2.09 | 5 (1.23 / 1.69) | 0.333 | 0.004 |

| Family | Combos | Eligible | Median search Sharpe | Best search Sharpe | Median validate Sharpe | Share beating SPY on both splits |
|---|---:|---:|---:|---:|---:|---:|
| F1_trend | 5,760 | 5,435 | 0.44 | 0.99 | 0.26 | 0.0% |
| F2_rotation | 53,568 | 53,496 | 0.44 | 1.10 | 0.49 | 0.0% |
| F3_meanrev | 11,025 | 7,840 | -0.05 | 1.09 | 0.32 | 0.1% |
| F4_candles | 735 | 601 | 0.13 | 1.05 | 0.16 | 0.3% |
| F5_voltarget | 10,080 | 8,215 | 0.60 | 0.94 | 1.13 | 7.7% |
| I1_orb | 14,400 | 8,640 | 0.18 | 1.39 | 0.17 | 2.0% |
| I2_noiseband | 4,608 | 4,608 | 0.84 | 1.62 | 0.72 | 22.0% |
