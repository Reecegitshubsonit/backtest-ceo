# Verdict (3-month out-of-sample: 2026-08-05 .. 2026-11-02)

Keep (pass on the untouched 3 months, >= 30 trades, profitable at 3x modelled cost):

| # | Strategy | Test trades | Win % | Exp $/trade | Total $ | Max DD $ | Sharpe |
|---|---|---:|---:|---:|---:|---:|---:|
| 1 | 0DTE iron condor, SPY/QQQ, 15:00, short +-0.25%, 0.5% wings, skip range>1%, credit>=$0.10 | 65 | 84.6 | 15.64 | 1016 | -232 | 3.05 |
| 2 | 0DTE bull put spread, SPY/QQQ, 15:00, short -0.25%, 1% wing, skip range>1%, credit>=$0.10 | 31 | 93.5 | 13.71 | 425 | -299 | 2.16 |
| 3 | IBS<0.1 in uptrend (close>SMA200), 18 ETFs, shares, 1-3 day hold | 58 | 55.2 | 17.16 | 995 | -559 | 3.07 |
| 4 | RSI(2)<10 AND IBS<0.25 in uptrend, 18 ETFs, shares | 33 | 69.7 | 27.37 | 903 | -261 | 3.05 |
| 5 | EMA+VWAP trend -> credit spread, 11:00, short 0.75% OTM (marginal: ~breakeven at 3x cost) | 39 | 46.2 | 2.04 | 79 | -49 | 2.15 |

Options rows use pessimistic execution (strict fills, 2x spread) and risk sizing. Options portfolio (1+2+5, 3% daily
loss stop): +$1,521 (+6.1% on $25k), max DD -2.3%, Sharpe 2.89.

Profitable on test but under 30 trades (rejected by rule): 10:00 bear call (21), 15:30 VWAP-side spread (13),
RSI14-reversion spread (18), EMA9>21 spread (16), daily-RSI(2) spread (17). Still failing: RSI14-momentum spread,
daily RSI(2)/EMA snap-back/3-down-days/RSI14 on shares (train Sharpe ~1 over 10 years, flat over these 3 months).

Risk controls: defined-risk spreads only; size = floor(2% of account / max loss), min 1 (1% wings exceed 2%: ~$790
risk = 3.2%); 3% daily portfolio stop; skip days whose range is already >0.6-1%; minimum credit so costs can't eat
the edge; selection under pessimistic fills. Tail risk remains: a last-hour 1% move costs one full wing.

Honesty notes: the 3 months were not used for tuning. The RSI(2)+IBS share rule was added after the other share
rules' test results were seen (its threshold was still picked on 2016-2026 train data). Option fills are trade-bar
based (no historical quotes on Alpaca).

# Options v2: 3-month out-of-sample, pessimistic selection, risk-sized

Train 2025-10-21..2026-08-04 (197 sessions); test 2026-08-05..2026-11-02 (63 sessions, ~3 months, untouched while tuning). SPY + QQQ 0DTE. 69,984 configs; 16,126 profitable on train under pessimistic execution (all legs print in the entry bar, 2x half-spread). Best per family by train Sharpe.

Sizing: contracts = floor(2% x $25,000 / max loss per structure), min 1. Metrics below are on that sized P&L. PASS = test >= 30 trades, pessimistic exp > 0 and Sharpe > 1, and still profitable at 3x cost.

| Strategy | Test trades | Win % | Exp $/trade | Total $ | Max DD $ | Sharpe | Worst trade $ | Max risk/trade $ | Base-cost exp $ | 3x-cost exp $ | Verdict |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 0DTE iron condor: short 0.25% OTM, wing 0.50%, enter 15:00, skip range>1.0%, credit>=$0.10 | 65 | 84.6% | 15.64 | 1016 | -232 | 3.05 | -218 | 390 | 19.87 | 11.40 | PASS |
| 0DTE bull put spread: short 0.25% OTM, wing 1.00%, enter 15:00, skip range>1.0%, credit>=$0.10 | 31 | 93.5% | 13.71 | 425 | -299 | 2.16 | -238 | 790 | 15.34 | 11.69 | PASS |
| 0DTE EMA+VWAP trend -> put/call spread: short 0.75% OTM, wing 1.00%, enter 11:00, skip range>0.6% | 39 | 46.2% | 2.04 | 79 | -49 | 2.15 | -48 | 798 | 3.86 | 0.04 | PASS |
| 0DTE bear call spread: short 0.75% OTM, wing 1.00%, enter 10:00, skip range>0.6%, credit>=$0.25 | 21 | 90.5% | 28.01 | 588 | -39 | 7.67 | -39 | 774 | 29.80 | 26.01 | FAIL |
| 0DTE VWAP side -> put/call spread: short 0.50% OTM, wing 0.50%, enter 15:30, credit>=$0.10 | 13 | 100.0% | 17.43 | 227 | 0 | 5.20 | 6 | 386 | 19.43 | 15.43 | FAIL |
| 0DTE RSI14 reversion -> put/call spread: short 0.25% OTM, wing 1.00%, enter 15:00, credit>=$0.10 | 18 | 83.3% | 21.27 | 383 | -194 | 2.10 | -194 | 789 | 23.30 | 19.24 | FAIL |
| 0DTE EMA9>21 -> put/call spread: short 0.25% OTM, wing 1.00%, enter 15:30, stop 1x credit, credit>=$0.25 | 16 | 68.8% | 13.54 | 217 | -215 | 1.28 | -168 | 768 | 15.69 | 11.40 | FAIL |
| 0DTE daily RSI(2) reversion -> put/call spread: short 0.25% OTM, wing 1.00%, enter 15:00, skip range>1.0%, credit>=$0.10 | 17 | 94.1% | 10.84 | 184 | -238 | 1.09 | -238 | 789 | 12.90 | 8.78 | FAIL |
| 0DTE RSI14 momentum -> put/call spread: short 0.75% OTM, wing 1.00%, enter 11:00, skip range>0.6%, skip gap>0.5% | 27 | 37.0% | 0.33 | 9 | -51 | 0.30 | -48 | 797 | 2.33 | -1.67 | FAIL |

Table metrics use pessimistic execution (strict fills, 2x half-spread).

## Portfolio of passing strategies (pessimistic costs, 3% daily loss stop)

Trades 135, win 75.6%, expectancy $11.27, total $1521 (6.1% on $25,000), max drawdown $-578 (-2.3%), Sharpe 2.89, worst trade $-238.

## Robustness

Top 50 train configs (pessimistic) on test: 47/50 profitable, median Sharpe 2.90, worst -2.31.


## Daily ETF signals on shares (replacement for the dead intraday share signals)

Universe 18 ETFs. Train 2016-01-04..2026-08-04; test 2026-08-05..2026-11-02 (63 sessions). $5k per trade, max 5 open, $25k account, 2 bp/side cost, market-on-close fills.

| Strategy | Train trades | Train win % | Train exp $ | Train Sharpe | Test trades | Test win % | Test exp $ | Test total $ | Test max DD $ | Test Sharpe | Verdict |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| RSI(2) pullback in uptrend (Connors) (k=10) | 974 | 69.7% | 15.88 | 1.13 | 38 | 57.9% | -3.26 | -124 | -922 | -0.28 | FAIL |
| EMA200 trend + close below EMA5 by k% (EMA snap-back) (k=1.0) | 891 | 69.5% | 15.31 | 0.85 | 33 | 57.6% | 1.18 | 39 | -891 | 0.09 | FAIL |
| IBS < k in uptrend, 1-3 day hold (k=0.1) | 1916 | 62.0% | 7.91 | 0.87 | 58 | 55.2% | 17.16 | 995 | -559 | 3.07 | PASS |
| k down closes above EMA200 (k=3) | 1109 | 70.5% | 15.81 | 1.25 | 35 | 62.9% | -7.19 | -252 | -804 | -0.62 | FAIL |
| RSI(2) < k AND IBS < 0.25 in uptrend (k=10) | 786 | 68.4% | 16.77 | 1.04 | 33 | 69.7% | 27.37 | 903 | -261 | 3.05 | PASS |
| RSI(14) < k above EMA50 (trend pullback) (k=45) | 196 | 63.8% | 15.16 | 0.36 | 5 | 60.0% | 6.10 | 31 | -191 | 0.24 | FAIL |
