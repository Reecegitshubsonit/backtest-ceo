## Holdout (run once): 2024-11-18 .. 2026-11-03, 491 sessions

| Strategy | CAGR | Vol | Sharpe | Max DD | Longest DD (d) | Trades | Vol-matched SPY CAGR / DD | ΔSharpe vs SPY [95% CI] | Holm p | Survives |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| SPY buy & hold | 15.1% | 16.6% | 0.70 | -18.8% | 127 | 1 | | | | |
| 10-ETF TSMOM (round 2) | 11.5% | 8.8% | 0.84 | -6.9% | 112 | 24 | 10.1% / -10.1% | +0.14 [-0.82, +0.98] | | benchmark |
| #1 I2_noiseband: look=14, mult=1.0, freq=6, stop=max, last=71, quiet=False, size=vol2, side=both, sym=QQQ | 18.1% | 15.9% | 0.88 | -14.6% | 385 | 279 | 14.7% / -18.0% | +0.18 [-2.12, +1.98] | 1.000 | no |
| #2 I2_noiseband: look=14, mult=1.0, freq=6, stop=band, last=71, quiet=False, size=vol2, side=both, sym=QQQ | 18.1% | 15.9% | 0.88 | -14.6% | 385 | 279 | 14.7% / -18.0% | +0.18 [-2.12, +1.98] | 1.000 | no |
| #3 I2_noiseband: look=14, mult=1.0, freq=6, stop=vwap, last=71, quiet=False, size=vol2, side=both, sym=SPY | -6.3% | 15.4% | -0.60 | -25.6% | 355 | 304 | 14.4% / -17.6% | -1.30 [-3.55, +0.41] | 1.000 | no |
| #4 I2_noiseband: look=7, mult=1.25, freq=3, stop=vwap, last=71, quiet=False, size=vol2, side=long, sym=SPY | 3.2% | 6.8% | -0.07 | -8.1% | 417 | 141 | 8.8% / -7.8% | -0.77 [-2.19, +0.43] | 1.000 | no |
| #5 I1_orb: orbars=3, dir=both, entry=break, stop=mid, target=5, quiet=False, gapf=with, size=1x, sym=QQQ | 4.9% | 5.5% | 0.19 | -3.2% | 177 | 255 | 7.9% / -6.2% | -0.51 [-2.45, +1.17] | 1.000 | no |
| #6 I1_orb: orbars=2, dir=both, entry=break, stop=mid, target=10, quiet=False, gapf=with, size=risk1, sym=QQQ | 7.3% | 19.5% | 0.26 | -14.2% | 276 | 261 | 16.9% / -21.8% | -0.44 [-2.32, +1.01] | 1.000 | no |
| #7 I2_noiseband: look=7, mult=1.0, freq=6, stop=vwap, last=71, quiet=False, size=vol2, side=both, sym=QQQ | 13.1% | 16.6% | 0.59 | -13.2% | 334 | 295 | 15.1% / -18.8% | -0.11 [-2.36, +1.58] | 1.000 | no |
| #8 I2_noiseband: look=7, mult=1.0, freq=6, stop=band, last=71, quiet=False, size=vol2, side=both, sym=QQQ | 11.3% | 16.0% | 0.50 | -18.5% | 558 | 295 | 14.8% / -18.2% | -0.20 [-2.61, +1.64] | 1.000 | no |
| #9 I2_noiseband: look=7, mult=1.0, freq=6, stop=max, last=71, quiet=False, size=vol2, side=both, sym=QQQ | 11.3% | 16.0% | 0.50 | -18.5% | 558 | 295 | 14.8% / -18.2% | -0.20 [-2.61, +1.64] | 1.000 | no |
| #10 I2_noiseband: look=14, mult=1.0, freq=12, stop=band, last=71, quiet=False, size=vol2, side=both, sym=QQQ | 12.4% | 14.5% | 0.61 | -10.0% | 381 | 249 | 13.9% / -16.6% | -0.09 [-2.39, +1.63] | 1.000 | no |

**Survivors: 0 of 10.** Holdout Sharpe above SPY's (0.70): 2; above 10-ETF TSMOM's (0.84): 2.
