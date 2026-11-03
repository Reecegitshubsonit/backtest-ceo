# Options strategy fix-up: verdict

**Keep (robust):** walk-forward picks that stay profitable on the untouched test window with strict
same-bar fills and up to 3x modelled spread cost (see `audit.md`):

| Strategy | Test trades | Test win % | Test exp $/trade | Test max DD $ | Test Sharpe | Strict + 3x cost exp $ / Sharpe |
|---|---:|---:|---:|---:|---:|---:|
| 0DTE bear call spread, short 0.25% OTM, 1.0% wing, enter 14:00, skip if session range >1.0% | 88 | 96.6 | 13.59 | -223 | 6.40 | 13.19 / 7.47 |
| 0DTE iron fly, 1.0% wings, enter 15:00, stop at 2x credit, skip if range >1.0% | 85 | 67.1 | 21.91 | -247 | 4.92 | 15.38 / 3.34 |
| 0DTE iron condor, short +-0.25%, 0.5% wings, enter 15:00, skip if range >1.0% | 87 | 77.0 | 10.87 | -224 | 4.00 | 2.83 / 1.05 |
| 0DTE bull put spread, short 0.25% OTM, 1.0% wing, enter 15:00, skip if range >1.0% | 86 | 93.0 | 7.37 | -295 | 3.29 | 3.47 / 1.46 |
| VWAP-side credit spread (above VWAP = bull put, below = bear call), short 0.75% OTM, 1.0% wing, 11:00, range <0.6% | 59 | 74.6 | 5.07 | -46 | 6.60 | 1.22 / 1.63 |

**Fragile (pass at base cost, fail at 2-3x):** RSI14-momentum, EMA+VWAP-trend and EMA9>21 credit spreads.
Their credits are a few cents, so the edge is the size of the cost assumption.

**Dead:** every indicator signal traded directionally (shares or long options). Re-tuning bar size,
entry window and a daily trend filter did not make any of them profitable out of sample. Daily RSI(2)
-> credit spread looked good in train and lost $1,232 in test.

What changed vs the original: enter late (14:00-15:00) instead of 10:00, skip days whose session range
is already >0.6-1.0% (trend days), and use indicators only to pick the side of a short premium trade,
not to take direction.

Risks not shown by 60 sessions: max loss per structure is the wing width x 100 (SPY 1% wing = about $700)
minus credit; one gap-like move in the last hour wipes out weeks of wins. Fills are trade-bar VWAP plus
a modelled spread (Alpaca has no historical option quotes); real 0DTE late-day fills need limit orders.
Picks were chosen from 6,480 configs on train only; 45 of the top 50 train configs were profitable on
test (median test Sharpe 3.49), so the result is not one lucky config.

## Full walk-forward results

Train 2025-10-21..2026-08-07 (200 sessions), test 2026-08-10..2026-11-02 (60 sessions, the original window, untouched while tuning). SPY + QQQ. 6480 option configs searched; best per family by train Sharpe (>= 30 train trades), then run once on test. PASS = test >= 30 trades, expectancy > 0, Sharpe > 1.

## Options (0DTE premium selling, plain and indicator-sided)

| Config (chosen on train) | Train trades | Train Sharpe | Test trades | Test win % | Test exp $ | Test total $ | Test max DD $ | Test Sharpe | Verdict |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| RSI14 momentum -> put/call spread; short 0.75% OTM, wing 1.0%, enter 12:30, stop none, target none, range filter <1.0% | 135 | 4.51 | 42 | 71.4 | 2.82 | 118 | -3 | 7.05 | PASS |
| VWAP side -> put/call spread; short 0.75% OTM, wing 1.0%, enter 11:00, stop none, target none, range filter <0.6% | 110 | 4.38 | 59 | 74.6 | 5.07 | 299 | -46 | 6.60 | PASS |
| bear call spread; short 0.25% OTM, wing 1.0%, enter 14:00, stop none, target none, range filter <1.0% | 160 | 5.02 | 88 | 96.6 | 13.59 | 1196 | -223 | 6.40 | PASS |
| iron fly; short 0.00% OTM, wing 1.0%, enter 15:00, stop 2x credit, target none, range filter <1.0% | 161 | 4.50 | 85 | 67.1 | 21.91 | 1863 | -247 | 4.92 | PASS |
| iron condor; short 0.25% OTM, wing 0.5%, enter 15:00, stop none, target none, range filter <1.0% | 168 | 5.17 | 87 | 77.0 | 10.87 | 945 | -224 | 4.00 | PASS |
| RSI14 reversion -> put/call spread; short 0.50% OTM, wing 0.5%, enter 15:00, stop none, target none, range filter none | 113 | 6.49 | 23 | 78.3 | 12.09 | 278 | -54 | 3.90 | REJECTED (<30) |
| EMA+VWAP trend -> put/call spread; short 0.75% OTM, wing 1.0%, enter 11:00, stop none, target none, range filter <0.6% | 83 | 6.83 | 39 | 71.8 | 3.41 | 133 | -46 | 3.59 | PASS |
| EMA9>21 -> put/call spread; short 0.75% OTM, wing 1.0%, enter 14:00, stop none, target 50%, range filter none | 298 | 4.03 | 61 | 41.0 | 2.00 | 122 | -13 | 3.54 | PASS |
| bull put spread; short 0.25% OTM, wing 1.0%, enter 15:00, stop none, target none, range filter <1.0% | 165 | 5.23 | 86 | 93.0 | 7.37 | 634 | -295 | 3.29 | PASS |
| daily RSI(2) reversion -> put/call spread; short 0.75% OTM, wing 1.0%, enter 11:00, stop none, target none, range filter <1.0% | 133 | 3.97 | 49 | 77.6 | -25.14 | -1232 | -1413 | -2.21 | FAIL |

## Indicator signals on shares (re-tuned)

| Config (chosen on train) | Train trades | Train Sharpe | Test trades | Test win % | Test exp $ | Test total $ | Test max DD $ | Test Sharpe | Verdict |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| EMA 9/21 cross on shares; 5-min bars, entries 10:30-15:00, daily-trend filter on | 391 | -0.96 | 133 | 27.8 | -11.50 | -1529 | -2446 | -2.41 | FAIL |
| VWAP cross on shares; 5-min bars, entries 10:30-15:00, daily-trend filter on | 712 | -1.41 | 263 | 15.2 | -12.65 | -3327 | -4435 | -4.32 | FAIL |
| RSI(2) 10/90 reversion on shares; 30-min bars, entries 09:45-15:30, daily-trend filter off | 840 | 0.55 | 253 | 49.0 | -6.82 | -1725 | -2405 | -2.56 | FAIL |
| EMA9 pullback w/ VWAP+EMA21 trend on shares; 5-min bars, entries 10:30-15:00, daily-trend filter on | 585 | -1.21 | 162 | 26.5 | -5.66 | -918 | -2211 | -1.47 | FAIL |
| RSI(14) 50-cross w/ VWAP filter on shares; 5-min bars, entries 09:45-15:30, daily-trend filter on | 539 | -0.58 | 165 | 17.6 | -15.85 | -2615 | -3542 | -3.78 | FAIL |

## Robustness: top 50 train configs (all families) on test

45/50 profitable on test; median test Sharpe 3.49; worst -2.21; best 7.05.

| Train rank | Config | Train Sharpe | Test trades | Test exp $ | Test Sharpe |
|---:|---|---:|---:|---:|---:|
| 1 | EMA+VWAP trend -> put/call spread; short 0.75% OTM, wing 1.0%, enter 11:00, stop none, target none, range filter <0.6% | 6.83 | 39 | 3.41 | 3.59 |
| 2 | RSI14 reversion -> put/call spread; short 0.50% OTM, wing 0.5%, enter 15:00, stop none, target none, range filter none | 6.49 | 23 | 12.09 | 3.90 |
| 3 | RSI14 reversion -> put/call spread; short 0.50% OTM, wing 1.0%, enter 15:00, stop none, target none, range filter none | 6.06 | 16 | 16.37 | 3.87 |
| 4 | RSI14 reversion -> put/call spread; short 0.25% OTM, wing 1.0%, enter 15:00, stop none, target 50%, range filter none | 5.98 | 32 | 8.01 | 1.69 |
| 5 | EMA+VWAP trend -> put/call spread; short 0.75% OTM, wing 0.5%, enter 11:00, stop none, target none, range filter <0.6% | 5.83 | 34 | 1.05 | 1.02 |
| 6 | RSI14 reversion -> put/call spread; short 0.25% OTM, wing 1.0%, enter 15:00, stop none, target none, range filter none | 5.78 | 32 | 15.45 | 2.78 |
| 7 | RSI14 reversion -> put/call spread; short 0.25% OTM, wing 1.0%, enter 14:00, stop none, target none, range filter none | 5.31 | 36 | 2.97 | 0.27 |
| 8 | bull put spread; short 0.25% OTM, wing 1.0%, enter 15:00, stop none, target none, range filter <1.0% | 5.23 | 86 | 7.37 | 3.29 |
| 9 | iron condor; short 0.25% OTM, wing 0.5%, enter 15:00, stop none, target none, range filter <1.0% | 5.17 | 87 | 10.87 | 4.00 |
| 10 | bull put spread; short 0.25% OTM, wing 1.0%, enter 15:00, stop 2x credit, target none, range filter <1.0% | 5.14 | 86 | 7.37 | 3.29 |
| 11 | RSI14 reversion -> put/call spread; short 0.50% OTM, wing 1.0%, enter 14:00, stop none, target none, range filter none | 5.08 | 22 | -8.04 | -0.88 |
| 12 | EMA+VWAP trend -> put/call spread; short 0.75% OTM, wing 1.0%, enter 11:00, stop none, target 50%, range filter <1.0% | 5.07 | 69 | 0.78 | 0.69 |
| 13 | iron condor; short 0.25% OTM, wing 1.0%, enter 15:00, stop none, target none, range filter <1.0% | 5.04 | 74 | 15.86 | 4.12 |
| 14 | bear call spread; short 0.25% OTM, wing 1.0%, enter 14:00, stop none, target none, range filter <1.0% | 5.02 | 88 | 13.59 | 6.40 |
| 15 | RSI14 reversion -> put/call spread; short 0.25% OTM, wing 0.5%, enter 15:00, stop none, target none, range filter none | 5.01 | 40 | 13.00 | 2.89 |
| 16 | RSI14 reversion -> put/call spread; short 0.25% OTM, wing 0.5%, enter 15:00, stop none, target 50%, range filter none | 4.82 | 40 | 5.83 | 1.53 |
| 17 | iron condor; short 0.25% OTM, wing 0.5%, enter 15:00, stop 2x credit, target none, range filter <1.0% | 4.74 | 87 | 10.50 | 3.85 |
| 18 | RSI14 reversion -> put/call spread; short 0.75% OTM, wing 0.5%, enter 15:00, stop none, target none, range filter none | 4.70 | 11 | 9.79 | 4.38 |
| 19 | iron condor; short 0.25% OTM, wing 1.0%, enter 15:00, stop 2x credit, target none, range filter <1.0% | 4.69 | 74 | 15.34 | 3.97 |
| 20 | bull put spread; short 0.25% OTM, wing 0.5%, enter 15:00, stop none, target none, range filter <1.0% | 4.67 | 85 | 5.76 | 2.70 |
