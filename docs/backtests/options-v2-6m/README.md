# Options v2: 6-month out-of-sample, pessimistic selection, risk-sized

Train 2025-10-21..2026-05-04 (134 sessions); test 2026-05-05..2026-11-02 (126 sessions, ~6 months, untouched while tuning). SPY + QQQ 0DTE. 69,984 configs; 15,506 profitable on train under pessimistic execution (all legs print in the entry bar, 2x half-spread). Best per family by train Sharpe.

Sizing: contracts = floor(2% x $25,000 / max loss per structure), min 1. Metrics below are on that sized P&L. PASS = test >= 30 trades, pessimistic exp > 0 and Sharpe > 1, and still profitable at 3x cost.

| Strategy | Test trades | Win % | Exp $/trade | Total $ | Max DD $ | Sharpe | Worst trade $ | Max risk/trade $ | Base-cost exp $ | 3x-cost exp $ | Verdict |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 0DTE RSI14 reversion -> put/call spread: short 0.25% OTM, wing 1.00%, enter 15:00, credit>=$0.10 | 53 | 90.6% | 27.41 | 1453 | -194 | 4.26 | -194 | 789 | 29.43 | 25.38 | PASS |
| 0DTE bear call spread: short 0.75% OTM, wing 0.50%, enter 10:00, skip range>0.6%, credit>=$0.25 | 32 | 90.6% | 18.77 | 601 | -143 | 3.66 | -143 | 374 | 20.77 | 16.77 | PASS |
| 0DTE iron condor: short 0.75% OTM, wing 1.00%, enter 11:00, target 50%, skip gap>0.5%, credit>=$0.25 | 50 | 76.0% | 1.52 | 76 | -581 | 0.15 | -580 | 774 | 7.64 | -4.26 | FAIL |
| 0DTE EMA9>21 -> put/call spread: short 0.75% OTM, wing 0.25%, enter 12:30, skip gap>0.5%, credit>=$0.10 | 18 | 83.3% | 0.75 | 13 | -675 | 0.03 | -363 | 497 | 7.10 | -5.60 | FAIL |
| 0DTE EMA+VWAP trend -> put/call spread: short 0.75% OTM, wing 0.25%, enter 12:30, skip gap>0.5%, credit>=$0.10 | 18 | 83.3% | 0.75 | 13 | -675 | 0.03 | -363 | 497 | 7.10 | -5.60 | FAIL |
| 0DTE VWAP side -> put/call spread: short 0.75% OTM, wing 0.25%, enter 12:30, skip gap>0.5%, credit>=$0.10 | 21 | 81.0% | -15.13 | -318 | -913 | -0.64 | -363 | 497 | -9.12 | -21.15 | FAIL |
| 0DTE RSI14 momentum -> put/call spread: short 0.75% OTM, wing 0.25%, enter 12:30, credit>=$0.10 | 27 | 88.9% | -12.00 | -324 | -677 | -0.70 | -378 | 496 | -7.52 | -16.49 | FAIL |
| 0DTE bull put spread: short 0.75% OTM, wing 1.00%, enter 11:00, skip gap>0.5% | 138 | 75.4% | -5.15 | -710 | -1194 | -0.94 | -587 | 797 | -3.01 | -7.15 | FAIL |
| 0DTE daily RSI(2) reversion -> put/call spread: short 0.75% OTM, wing 0.25%, enter 12:30, credit>=$0.10 | 32 | 81.2% | -20.60 | -659 | -1089 | -1.20 | -382 | 496 | -15.46 | -25.74 | FAIL |

Table metrics use pessimistic execution (strict fills, 2x half-spread).

## Portfolio of passing strategies (pessimistic costs, 3% daily loss stop)

Trades 85, win 90.6%, expectancy $24.16, total $2053 (8.2% on $25,000), max drawdown $-166 (-0.7%), Sharpe 5.16, worst trade $-194.

## Robustness

Top 50 train configs (pessimistic) on test: 22/50 profitable, median Sharpe -0.36, worst -2.00.

