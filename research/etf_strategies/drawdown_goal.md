# Option 3: return for the same max drawdown

Drawdown-matched SPY = SPY scaled down to the strategy's max DD in that window (rest in T-bills, rebalanced daily, no costs: slightly flatters SPY). Note: k is fitted in-window to the strategy's realized max DD, so this is a description, not a tradable benchmark.

### 2017–2026

| Strategy | CAGR | Max DD | Calmar | Ulcer | DD-matched SPY k | DD-matched SPY CAGR | ΔCAGR | ΔCAGR 95% CI | P(boot CAGR > SPY·k) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| SPY buy & hold | 14.8% | -33.8% | 0.44 | 7.2 | 1.00 | | | | |
| N1. Vol target 15% | 14.4% | -19.4% | 0.75 | 7.9 | 0.54 | 9.4% | +5.1 pts | [-1.1, +12.0] | 0.95 |
| N5. Trend × vol target | 12.2% | -22.9% | 0.53 | 8.8 | 0.65 | 10.7% | +1.5 pts | [-5.4, +8.6] | 0.67 |
| 1. SPY 200d SMA / cash | 10.8% | -19.3% | 0.56 | 7.4 | 0.54 | 9.3% | +1.4 pts | [-3.6, +6.5] | 0.71 |
| 2. TSMOM original 10 | 7.1% | -8.4% | 0.85 | 2.1 | 0.23 | 5.4% | +1.8 pts | [-1.0, +4.6] | 0.90 |
| 2r. TSMOM GTAA-5 | 5.7% | -8.0% | 0.71 | 2.4 | 0.22 | 5.3% | +0.4 pts | [-2.3, +3.2] | 0.62 |
| 60% SPY / 40% T-bills, monthly | 10.0% | -21.0% | 0.48 | 4.1 | 0.59 | 10.0% | +0.1 pts | [-0.1, +0.2] | 0.77 |

### 2017–2021

| Strategy | CAGR | Max DD | Calmar | Ulcer | DD-matched SPY k | DD-matched SPY CAGR | ΔCAGR | ΔCAGR 95% CI | P(boot CAGR > SPY·k) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| SPY buy & hold | 18.1% | -33.8% | 0.54 | 5.6 | 1.00 | | | | |
| N1. Vol target 15% | 19.3% | -19.4% | 1.00 | 7.3 | 0.54 | 10.3% | +9.0 pts | [-0.9, +20.3] | 0.96 |
| N5. Trend × vol target | 15.6% | -22.9% | 0.68 | 10.3 | 0.65 | 12.2% | +3.4 pts | [-7.4, +15.2] | 0.73 |
| 1. SPY 200d SMA / cash | 12.6% | -19.3% | 0.65 | 7.9 | 0.54 | 10.3% | +2.3 pts | [-5.3, +9.9] | 0.73 |
| 2. TSMOM original 10 | 7.1% | -8.4% | 0.85 | 2.2 | 0.23 | 4.9% | +2.2 pts | [-1.0, +5.6] | 0.91 |
| 2r. TSMOM GTAA-5 | 5.7% | -6.6% | 0.87 | 2.4 | 0.18 | 4.1% | +1.7 pts | [-1.8, +5.2] | 0.83 |
| 60% SPY / 40% T-bills, monthly | 11.3% | -21.0% | 0.54 | 3.3 | 0.59 | 11.2% | +0.1 pts | [-0.2, +0.4] | 0.84 |

### 2022–2026

| Strategy | CAGR | Max DD | Calmar | Ulcer | DD-matched SPY k | DD-matched SPY CAGR | ΔCAGR | ΔCAGR 95% CI | P(boot CAGR > SPY·k) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| SPY buy & hold | 11.5% | -24.5% | 0.47 | 8.6 | 1.00 | | | | |
| N1. Vol target 15% | 9.6% | -19.0% | 0.50 | 8.4 | 0.77 | 10.0% | -0.4 pts | [-6.0, +5.8] | 0.45 |
| N5. Trend × vol target | 8.8% | -15.6% | 0.56 | 6.9 | 0.63 | 9.0% | -0.2 pts | [-9.3, +9.0] | 0.48 |
| 1. SPY 200d SMA / cash | 8.9% | -17.9% | 0.50 | 6.9 | 0.72 | 9.7% | -0.8 pts | [-8.8, +6.8] | 0.42 |
| 2. TSMOM original 10 | 7.2% | -6.9% | 1.03 | 2.0 | 0.29 | 6.3% | +0.8 pts | [-3.8, +5.5] | 0.63 |
| 2r. TSMOM GTAA-5 | 5.6% | -8.0% | 0.70 | 2.3 | 0.33 | 6.7% | -1.1 pts | [-5.8, +3.8] | 0.32 |
| 60% SPY / 40% T-bills, monthly | 8.7% | -14.9% | 0.58 | 4.9 | 0.60 | 8.8% | -0.1 pts | [-0.3, +0.0] | 0.04 |

### Pass rule (beat DD-matched SPY CAGR in both halves)

| Strategy | 2017–21 | 2022–26 | Pass |
|---|---:|---:|---|
| N1. Vol target 15% | +9.0 pts | -0.4 pts | no |
| N5. Trend × vol target | +3.4 pts | -0.2 pts | no |
| 1. SPY 200d SMA / cash | +2.3 pts | -0.8 pts | no |
| 2. TSMOM original 10 | +2.2 pts | +0.8 pts | yes |
| 2r. TSMOM GTAA-5 | +1.7 pts | -1.1 pts | no |
| 60% SPY / 40% T-bills, monthly | +0.1 pts | -0.1 pts | no |
