Candidates from pre-2017 literature, default parameters. Costs 3 bp/side, cash = BIL, Sharpe in excess of BIL. Holm correction uses m = 12 (all strategies tested vs SPY in this project).

### 2017–2026: 2017-01-03 .. 2026-11-03

| Strategy | CAGR | Vol | Sharpe (xs T-bill) | Max DD | Longest DD (days) | Round trips | Position changes | Fills (incl. resizes) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| SPY buy & hold | 14.8% | 17.8% | 0.73 | -33.8% | 709 | 0 (+1 open) | 1 | 1 |
| N1. Vol target 15%, SPY/SSO, cap 2x | 14.4% | 16.5% | 0.76 | -19.4% | 608 | 28 (+2 open) | 58 | 656 |
| N2. 2x trend: SSO while SPY > 200d | 16.6% | 24.2% | 0.66 | -36.0% | 788 | 25 (+1 open) | 51 | 51 |
| N3. 3x trend: UPRO while SPY > 200d | 21.8% | 36.2% | 0.67 | -51.0% | 868 | 25 (+1 open) | 51 | 51 |
| N4. Turn of month, SPY | 5.5% | 7.8% | 0.43 | -10.7% | 522 | 118 (+1 open) | 237 | 237 |
| N5. 200d trend x vol target 15% | 12.2% | 14.9% | 0.69 | -22.9% | 713 | 57 (+2 open) | 116 | 661 |

**Vol-matched SPY** (SPY scaled daily to the strategy's vol, rest in T-bills, frictionless) and **bootstrap 95% CI on Sharpe(strategy) − Sharpe(SPY)** (5000 resamples, 21-day circular blocks):

| Strategy | Strategy CAGR | Vol-matched SPY CAGR | Strategy max DD | Vol-matched SPY max DD | SPY scale | ΔSharpe | 95% CI | P(boot Δ ≤ 0) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| N1. Vol target 15%, SPY/SSO, cap 2x | 14.4% | 14.0% | -19.4% | -31.6% | 0.93 | +0.02 | [-0.29, +0.32] | 0.48 |
| N2. 2x trend: SSO while SPY > 200d | 16.6% | 18.7% | -36.0% | -43.7% | 1.36 | -0.07 | [-0.49, +0.32] | 0.65 |
| N3. 3x trend: UPRO while SPY > 200d | 21.8% | 24.9% | -51.0% | -59.3% | 2.03 | -0.07 | [-0.48, +0.32] | 0.65 |
| N4. Turn of month, SPY | 5.5% | 8.1% | -10.7% | -15.9% | 0.44 | -0.31 | [-1.03, +0.41] | 0.82 |
| N5. 200d trend x vol target 15% | 12.2% | 12.9% | -22.9% | -29.0% | 0.84 | -0.05 | [-0.54, +0.42] | 0.60 |

| Strategy | one-sided p | Holm-adjusted p |
|---|---:|---:|
| N1. Vol target 15%, SPY/SSO, cap 2x | 0.477 | 1.000 |
| N2. 2x trend: SSO while SPY > 200d | 0.652 | 1.000 |
| N3. 3x trend: UPRO while SPY > 200d | 0.646 | 1.000 |
| N4. Turn of month, SPY | 0.817 | 1.000 |
| N5. 200d trend x vol target 15% | 0.599 | 1.000 |

### First half: 2017-01-03 .. 2021-12-31

| Strategy | CAGR | Vol | Sharpe (xs T-bill) | Max DD | Longest DD (days) | Round trips | Position changes | Fills (incl. resizes) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| SPY buy & hold | 18.1% | 18.3% | 0.95 | -33.8% | 204 | 0 (+1 open) | 1 | 1 |
| N1. Vol target 15%, SPY/SSO, cap 2x | 19.3% | 16.6% | 1.09 | -19.4% | 452 | 28 (+2 open) | 58 | 656 |
| N2. 2x trend: SSO while SPY > 200d | 22.1% | 25.7% | 0.87 | -36.0% | 510 | 25 (+1 open) | 51 | 51 |
| N3. 3x trend: UPRO while SPY > 200d | 31.1% | 38.4% | 0.88 | -51.0% | 868 | 25 (+1 open) | 51 | 51 |
| N4. Turn of month, SPY | 5.6% | 8.1% | 0.59 | -10.7% | 522 | 118 (+1 open) | 237 | 237 |
| N5. 200d trend x vol target 15% | 15.6% | 15.7% | 0.94 | -22.9% | 713 | 57 (+2 open) | 116 | 661 |

**Vol-matched SPY** (SPY scaled daily to the strategy's vol, rest in T-bills, frictionless) and **bootstrap 95% CI on Sharpe(strategy) − Sharpe(SPY)** (5000 resamples, 21-day circular blocks):

| Strategy | Strategy CAGR | Vol-matched SPY CAGR | Strategy max DD | Vol-matched SPY max DD | SPY scale | ΔSharpe | 95% CI | P(boot Δ ≤ 0) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| N1. Vol target 15%, SPY/SSO, cap 2x | 19.3% | 16.5% | -19.4% | -31.0% | 0.90 | +0.14 | [-0.42, +0.67] | 0.38 |
| N2. 2x trend: SSO while SPY > 200d | 22.1% | 24.6% | -36.0% | -44.8% | 1.40 | -0.08 | [-0.64, +0.45] | 0.67 |
| N3. 3x trend: UPRO while SPY > 200d | 31.1% | 34.7% | -51.0% | -60.5% | 2.09 | -0.07 | [-0.63, +0.46] | 0.67 |
| N4. Turn of month, SPY | 5.6% | 8.6% | -10.7% | -16.0% | 0.44 | -0.36 | [-1.50, +0.71] | 0.75 |
| N5. 200d trend x vol target 15% | 15.6% | 15.7% | -22.9% | -29.5% | 0.86 | -0.01 | [-0.73, +0.70] | 0.57 |

| Strategy | one-sided p | Holm-adjusted p |
|---|---:|---:|
| N1. Vol target 15%, SPY/SSO, cap 2x | 0.379 | 1.000 |
| N2. 2x trend: SSO while SPY > 200d | 0.674 | 1.000 |
| N3. 3x trend: UPRO while SPY > 200d | 0.667 | 1.000 |
| N4. Turn of month, SPY | 0.749 | 1.000 |
| N5. 200d trend x vol target 15% | 0.571 | 1.000 |

_(Trade counts in this sub-window are for the whole run from its start.)_

### Second half: 2022-01-03 .. 2026-11-03

| Strategy | CAGR | Vol | Sharpe (xs T-bill) | Max DD | Longest DD (days) | Round trips | Position changes | Fills (incl. resizes) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| SPY buy & hold | 11.4% | 17.2% | 0.50 | -24.5% | 709 | 0 (+1 open) | 1 | 1 |
| N1. Vol target 15%, SPY/SSO, cap 2x | 9.5% | 16.4% | 0.40 | -19.0% | 561 | 11 (+2 open) | 24 | 329 |
| N2. 2x trend: SSO while SPY > 200d | 11.1% | 22.5% | 0.41 | -34.9% | 788 | 15 (+1 open) | 31 | 31 |
| N3. 3x trend: UPRO while SPY > 200d | 12.8% | 33.7% | 0.42 | -48.7% | 807 | 15 (+1 open) | 31 | 31 |
| N4. Turn of month, SPY | 5.4% | 7.5% | 0.23 | -7.6% | 397 | 58 (+1 open) | 117 | 117 |
| N5. 200d trend x vol target 15% | 8.7% | 14.1% | 0.40 | -15.6% | 561 | 28 (+2 open) | 58 | 331 |

**Vol-matched SPY** (SPY scaled daily to the strategy's vol, rest in T-bills, frictionless) and **bootstrap 95% CI on Sharpe(strategy) − Sharpe(SPY)** (5000 resamples, 21-day circular blocks):

| Strategy | Strategy CAGR | Vol-matched SPY CAGR | Strategy max DD | Vol-matched SPY max DD | SPY scale | ΔSharpe | 95% CI | P(boot Δ ≤ 0) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| N1. Vol target 15%, SPY/SSO, cap 2x | 9.5% | 11.1% | -19.0% | -23.3% | 0.95 | -0.09 | [-0.41, +0.21] | 0.73 |
| N2. 2x trend: SSO while SPY > 200d | 11.1% | 13.2% | -34.9% | -31.5% | 1.31 | -0.08 | [-0.71, +0.52] | 0.62 |
| N3. 3x trend: UPRO while SPY > 200d | 12.8% | 15.9% | -48.7% | -45.1% | 1.96 | -0.08 | [-0.71, +0.52] | 0.61 |
| N4. Turn of month, SPY | 5.4% | 7.5% | -7.6% | -10.8% | 0.44 | -0.26 | [-1.18, +0.59] | 0.73 |
| N5. 200d trend x vol target 15% | 8.7% | 10.3% | -15.6% | -20.2% | 0.82 | -0.10 | [-0.76, +0.54] | 0.63 |

| Strategy | one-sided p | Holm-adjusted p |
|---|---:|---:|
| N1. Vol target 15%, SPY/SSO, cap 2x | 0.733 | 1.000 |
| N2. 2x trend: SSO while SPY > 200d | 0.616 | 1.000 |
| N3. 3x trend: UPRO while SPY > 200d | 0.614 | 1.000 |
| N4. Turn of month, SPY | 0.728 | 1.000 |
| N5. 200d trend x vol target 15% | 0.630 | 1.000 |

### Last 2 years: 2024-11-04 .. 2026-11-03

| Strategy | CAGR | Vol | Sharpe (xs T-bill) | Max DD | Longest DD (days) | Round trips | Position changes | Fills (incl. resizes) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| SPY buy & hold | 16.3% | 16.5% | 0.76 | -18.8% | 127 | 0 (+1 open) | 1 | 1 |
| N1. Vol target 15%, SPY/SSO, cap 2x | 9.9% | 17.1% | 0.41 | -18.4% | 279 | 7 (+2 open) | 16 | 165 |
| N2. 2x trend: SSO while SPY > 200d | 16.7% | 23.2% | 0.62 | -20.6% | 204 | 3 (+1 open) | 7 | 7 |
| N3. 3x trend: UPRO while SPY > 200d | 21.1% | 34.8% | 0.62 | -29.8% | 208 | 3 (+1 open) | 7 | 7 |
| N4. Turn of month, SPY | 8.6% | 6.9% | 0.66 | -7.5% | 397 | 24 (+1 open) | 49 | 49 |
| N5. 200d trend x vol target 15% | 9.3% | 15.6% | 0.40 | -12.9% | 272 | 10 (+2 open) | 22 | 162 |

**Vol-matched SPY** (SPY scaled daily to the strategy's vol, rest in T-bills, frictionless) and **bootstrap 95% CI on Sharpe(strategy) − Sharpe(SPY)** (5000 resamples, 21-day circular blocks):

| Strategy | Strategy CAGR | Vol-matched SPY CAGR | Strategy max DD | Vol-matched SPY max DD | SPY scale | ΔSharpe | 95% CI | P(boot Δ ≤ 0) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| N1. Vol target 15%, SPY/SSO, cap 2x | 9.9% | 16.6% | -18.4% | -19.4% | 1.03 | -0.35 | [-0.89, +0.07] | 0.95 |
| N2. 2x trend: SSO while SPY > 200d | 16.7% | 20.7% | -20.6% | -25.6% | 1.40 | -0.14 | [-0.93, +0.54] | 0.69 |
| N3. 3x trend: UPRO while SPY > 200d | 21.1% | 27.5% | -29.8% | -36.6% | 2.10 | -0.14 | [-0.94, +0.54] | 0.69 |
| N4. Turn of month, SPY | 8.6% | 9.3% | -7.5% | -7.9% | 0.42 | -0.10 | [-1.12, +1.09] | 0.56 |
| N5. 200d trend x vol target 15% | 9.3% | 15.6% | -12.9% | -17.8% | 0.94 | -0.36 | [-1.22, +0.40] | 0.83 |

| Strategy | one-sided p | Holm-adjusted p |
|---|---:|---:|
| N1. Vol target 15%, SPY/SSO, cap 2x | 0.952 | 1.000 |
| N2. 2x trend: SSO while SPY > 200d | 0.694 | 1.000 |
| N3. 3x trend: UPRO while SPY > 200d | 0.695 | 1.000 |
| N4. Turn of month, SPY | 0.564 | 1.000 |
| N5. 200d trend x vol target 15% | 0.834 | 1.000 |
