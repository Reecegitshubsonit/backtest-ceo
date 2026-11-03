Daily data: Alpaca SIP adjusted, 2016-01-04 .. 2026-11-03. Costs 3 bp/side. Cash and Sharpe risk-free = BIL daily total return (BIL CAGR over window shown in the T-bill row of results.csv).

### 2017–2026: 2017-01-03 .. 2026-11-03

| Strategy | CAGR | Vol | Sharpe (xs T-bill) | Max DD | Longest DD (days) | Round trips | Position changes | Fills (incl. resizes) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| SPY buy & hold | 14.8% | 17.8% | 0.73 | -33.8% | 709 | 0 (+1 open) | 1 | 1 |
| 1. Trend: SPY 200d SMA / cash | 10.7% | 12.1% | 0.71 | -19.3% | 746 | 25 (+1 open) | 51 | 51 |
| 2. Trend: TSMOM, original 10 ETFs | 7.1% | 6.7% | 0.71 | -8.4% | 583 | 75 (+6 open) | 156 | 728 |
| 3. Rotation: top-3 sectors | 10.3% | 17.1% | 0.52 | -32.6% | 839 | 124 (+3 open) | 251 | 457 |
| 4. Rotation: dual momentum | 10.6% | 19.6% | 0.49 | -36.5% | 1968 | 33 (+1 open) | 67 | 67 |
| 5a. Mean rev: SPY RSI(2) | 4.7% | 6.2% | 0.39 | -12.1% | 1006 | 86 (+1 open) | 173 | 173 |

**Vol-matched SPY** (SPY scaled daily to the strategy's vol, rest in T-bills, frictionless) and **bootstrap 95% CI on Sharpe(strategy) − Sharpe(SPY)** (5000 resamples, 21-day circular blocks):

| Strategy | Strategy CAGR | Vol-matched SPY CAGR | Strategy max DD | Vol-matched SPY max DD | SPY scale | ΔSharpe | 95% CI | P(boot Δ ≤ 0) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1. Trend: SPY 200d SMA / cash | 10.7% | 11.0% | -19.3% | -23.9% | 0.68 | -0.02 | [-0.44, +0.37] | 0.56 |
| 2. Trend: TSMOM, original 10 ETFs | 7.1% | 7.3% | -8.4% | -13.8% | 0.38 | -0.02 | [-0.53, +0.44] | 0.56 |
| 3. Rotation: top-3 sectors | 10.3% | 14.3% | -32.6% | -32.6% | 0.96 | -0.21 | [-0.58, +0.16] | 0.86 |
| 4. Rotation: dual momentum | 10.6% | 16.0% | -36.5% | -36.8% | 1.10 | -0.24 | [-0.81, +0.28] | 0.81 |
| 5a. Mean rev: SPY RSI(2) | 4.7% | 6.9% | -12.1% | -12.6% | 0.35 | -0.34 | [-0.97, +0.28] | 0.87 |

### Universe robustness, 2017–2026: 2017-01-03 .. 2026-11-03

| Strategy | CAGR | Vol | Sharpe (xs T-bill) | Max DD | Longest DD (days) | Round trips | Position changes | Fills (incl. resizes) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| SPY buy & hold | 14.8% | 17.8% | 0.73 | -33.8% | 709 | 0 (+1 open) | 1 | 1 |
| 2. TSMOM, original 10 ETFs | 7.1% | 6.7% | 0.71 | -8.4% | 583 | 75 (+6 open) | 156 | 728 |
| 2r. TSMOM, 10 sector SPDRs listed before 2017 | 6.8% | 8.4% | 0.55 | -12.4% | 814 | 103 (+7 open) | 213 | 870 |
| 2r. TSMOM, Faber 2007 GTAA-5 | 5.7% | 6.1% | 0.55 | -8.0% | 497 | 40 (+4 open) | 84 | 367 |

**Vol-matched SPY** (SPY scaled daily to the strategy's vol, rest in T-bills, frictionless) and **bootstrap 95% CI on Sharpe(strategy) − Sharpe(SPY)** (5000 resamples, 21-day circular blocks):

| Strategy | Strategy CAGR | Vol-matched SPY CAGR | Strategy max DD | Vol-matched SPY max DD | SPY scale | ΔSharpe | 95% CI | P(boot Δ ≤ 0) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2. TSMOM, original 10 ETFs | 7.1% | 7.3% | -8.4% | -13.8% | 0.38 | -0.02 | [-0.53, +0.44] | 0.56 |
| 2r. TSMOM, 10 sector SPDRs listed before 2017 | 6.8% | 8.5% | -12.4% | -17.0% | 0.47 | -0.18 | [-0.62, +0.23] | 0.82 |
| 2r. TSMOM, Faber 2007 GTAA-5 | 5.7% | 6.9% | -8.0% | -12.6% | 0.34 | -0.18 | [-0.73, +0.32] | 0.78 |

### Last 2 years: 2024-11-04 .. 2026-11-03

| Strategy | CAGR | Vol | Sharpe (xs T-bill) | Max DD | Longest DD (days) | Round trips | Position changes | Fills (incl. resizes) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| SPY buy & hold | 16.3% | 16.5% | 0.76 | -18.8% | 127 | 0 (+1 open) | 1 | 1 |
| 1. Trend: SPY 200d SMA / cash | 11.8% | 11.7% | 0.68 | -10.2% | 175 | 3 (+1 open) | 7 | 7 |
| 2. Trend: TSMOM, original 10 ETFs | 11.1% | 8.8% | 0.80 | -6.9% | 112 | 18 (+6 open) | 42 | 203 |
| 3. Rotation: top-3 sectors | 12.1% | 13.8% | 0.62 | -14.8% | 208 | 24 (+3 open) | 51 | 93 |
| 4. Rotation: dual momentum | 18.0% | 23.6% | 0.66 | -25.8% | 278 | 6 (+1 open) | 13 | 13 |
| 5a. Mean rev: SPY RSI(2) | 10.4% | 5.4% | 1.14 | -4.1% | 182 | 22 (+1 open) | 45 | 45 |

**Vol-matched SPY** (SPY scaled daily to the strategy's vol, rest in T-bills, frictionless) and **bootstrap 95% CI on Sharpe(strategy) − Sharpe(SPY)** (5000 resamples, 21-day circular blocks):

| Strategy | Strategy CAGR | Vol-matched SPY CAGR | Strategy max DD | Vol-matched SPY max DD | SPY scale | ΔSharpe | 95% CI | P(boot Δ ≤ 0) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1. Trend: SPY 200d SMA / cash | 11.8% | 12.8% | -10.2% | -13.4% | 0.70 | -0.08 | [-0.87, +0.61] | 0.63 |
| 2. Trend: TSMOM, original 10 ETFs | 11.1% | 10.7% | -6.9% | -10.1% | 0.53 | +0.04 | [-0.93, +0.87] | 0.48 |
| 3. Rotation: top-3 sectors | 12.1% | 14.4% | -14.8% | -15.8% | 0.84 | -0.14 | [-1.10, +0.80] | 0.63 |
| 4. Rotation: dual momentum | 18.0% | 21.0% | -25.8% | -26.1% | 1.43 | -0.10 | [-1.86, +1.48] | 0.56 |
| 5a. Mean rev: SPY RSI(2) | 10.4% | 8.1% | -4.1% | -6.1% | 0.33 | +0.38 | [-1.07, +1.57] | 0.30 |

### Universe robustness, Last 2 years: 2024-11-04 .. 2026-11-03

| Strategy | CAGR | Vol | Sharpe (xs T-bill) | Max DD | Longest DD (days) | Round trips | Position changes | Fills (incl. resizes) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| SPY buy & hold | 16.3% | 16.5% | 0.76 | -18.8% | 127 | 0 (+1 open) | 1 | 1 |
| 2. TSMOM, original 10 ETFs | 11.1% | 8.8% | 0.80 | -6.9% | 112 | 18 (+6 open) | 42 | 203 |
| 2r. TSMOM, 10 sector SPDRs listed before 2017 | 8.0% | 8.0% | 0.51 | -8.9% | 290 | 23 (+7 open) | 53 | 199 |
| 2r. TSMOM, Faber 2007 GTAA-5 | 9.4% | 7.2% | 0.75 | -8.0% | 129 | 9 (+4 open) | 22 | 104 |

**Vol-matched SPY** (SPY scaled daily to the strategy's vol, rest in T-bills, frictionless) and **bootstrap 95% CI on Sharpe(strategy) − Sharpe(SPY)** (5000 resamples, 21-day circular blocks):

| Strategy | Strategy CAGR | Vol-matched SPY CAGR | Strategy max DD | Vol-matched SPY max DD | SPY scale | ΔSharpe | 95% CI | P(boot Δ ≤ 0) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2. TSMOM, original 10 ETFs | 11.1% | 10.7% | -6.9% | -10.1% | 0.53 | +0.04 | [-0.93, +0.87] | 0.48 |
| 2r. TSMOM, 10 sector SPDRs listed before 2017 | 8.0% | 10.1% | -8.9% | -9.2% | 0.49 | -0.25 | [-1.44, +0.77] | 0.68 |
| 2r. TSMOM, Faber 2007 GTAA-5 | 9.4% | 9.5% | -8.0% | -8.2% | 0.43 | -0.01 | [-0.99, +1.03] | 0.51 |
