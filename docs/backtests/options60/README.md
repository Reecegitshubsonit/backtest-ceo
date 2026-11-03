# Options vs shares, 2026-08-10 to 2026-11-02 (60 sessions), SPY, QQQ

| Strategy | Trades | Win % | Expectancy $/trade | Total $ | Max DD $ | Sharpe | Costs $ | Status |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| 0DTE iron condor (short +-0.5%, wings +-1.0%) | 119 | 80.7 | 12.38 | 1473 | -1147 | 2.19 | 808 | OK |
| 0DTE iron butterfly (short ATM, wings +-1.0%) | 119 | 64.7 | 33.53 | 3990 | -1874 | 2.95 | 953 | OK |
| 0DTE bull put spread (short -0.3%, long -0.8%) | 120 | 78.3 | 4.23 | 508 | -1380 | 0.66 | 419 | OK |
| 0DTE long straddle 09:45 -> 15:30 | 119 | 34.5 | -33.27 | -3959 | -6690 | -2.29 | 1233 | OK |
| Overnight 1DTE long straddle 15:50 -> 09:45 | 117 | 31.6 | -6.74 | -788 | -2455 | -0.54 | 1597 | OK |
| EMA 9/21 cross | options | 308 | 24.4 | -15.06 | -4639 | -6086 | -3.79 | 2110 | OK |
| EMA 9/21 cross | shares | 308 | 28.9 | -15.03 | -4630 | -5669 | -4.80 | 2289 | OK |
| VWAP cross | options | 816 | 22.5 | -10.17 | -8297 | -9868 | -5.13 | 5736 | OK |
| VWAP cross | shares | 819 | 22.7 | -10.64 | -8716 | -9864 | -6.50 | 6110 | OK |
| RSI(2) 10/90 reversion | options | 895 | 42.1 | -9.95 | -8902 | -8902 | -11.60 | 6320 | OK |
| RSI(2) 10/90 reversion | shares | 898 | 45.4 | -9.25 | -8309 | -8312 | -9.43 | 6698 | OK |
| EMA9 pullback w/ VWAP+EMA21 trend | options | 480 | 26.7 | -5.98 | -2869 | -5148 | -2.16 | 3317 | OK |
| EMA9 pullback w/ VWAP+EMA21 trend | shares | 481 | 29.5 | -6.00 | -2886 | -4584 | -2.70 | 3590 | OK |
| RSI(14) 50-cross w/ VWAP filter | options | 341 | 20.2 | -12.42 | -4234 | -5673 | -3.85 | 2339 | OK |
| RSI(14) 50-cross w/ VWAP filter | shares | 342 | 21.9 | -12.81 | -4380 | -5408 | -4.72 | 2552 | OK |

Method: Alpaca SIP 5-min bars (underlying) and Alpaca 5-min option trade bars, last 60 sessions. Fills at the
VWAP of the bar after the signal bar. Options: ATM contract, next-day expiry, 1 contract; shares: 50 shares
(delta-matched to one ATM contract). Indicator trades are intraday, flat by 15:50. Structural 0DTE credit
structures enter 10:00 and settle at intrinsic on the 16:00 close (no exit cost). Sharpe: daily P&L on a $10k
account, annualised. Strategies under 30 trades are rejected (none were).

Costs: options $0.68/contract/side (commission + regulatory) plus half-spread max($0.01, 1% of premium) per
leg per side; shares 1 bp per side.

Caveats: Alpaca has no historical option quotes, so fills come from trade bars plus a modelled spread
(optimistic for wide/illiquid wings). A missing option print within 10-15 minutes skips the trade. 60 sessions
is one regime; short-premium results carry tail risk that 120 trades may not show.

Reproduce: `cd engine && python3 -m backtestceo.options60` (cache in `data/options60/`, gitignored).
