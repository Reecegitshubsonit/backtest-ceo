# Losing-trade dissection: frozen three-month options replay

Period: July 24–October 23, 2026. Base execution only: one-second latency, actual Databento NBBO, $0.01 adverse slippage per side and $0.65 commission per contract per side. All entries/exits are simulated; no live orders were placed.

## Exact counts

413 qualifying entry opportunities accounted for: 143 filled and 270 skipped (138 daily two-loss lock, 131 premium budget/cash/displayed-size gate, 1 position already open). 143 buys and 143 sells = 286 simulated fills. Each trade was one long option contract and was closed. There were 45 winners, 98 losers and zero flat trades. These counts exclude the separate stress run; adding it would double-count an alternative simulation.

Wins totaled +$2,648.50; losses totaled −$3,294.40; net −$645.90. Average winner +$58.86, average loser −$33.62. At those observed average payoffs, the arithmetic breakeven win rate is 36.35%, versus the actual 31.47%. That is a descriptive threshold, not a forecast.

## Loss exits

| Exit reason | Losing trades | Total loss |
|---|---:|---:|
| 25% premium stop | 93 | −$3,111.90 |
| Opposite crossover | 5 | −$182.50 |

All 44 premium-target exits were profitable, as was the one session-close exit. The median losing trade lasted 5.70 minutes; 30 losers closed within 3 minutes and 46 within 5 minutes. Stop fills had a median premium return of −25.83% before commission, with the worst at −32.24%; four were worse than −30%. Gaps, latency and quote movement mean the 25% trigger is not a guaranteed maximum loss.

## Direction

| Direction | Trades | Winners | Losers | Net P&L |
|---|---:|---:|---:|---:|
| Calls | 90 | 23 | 67 | −$1,041.00 |
| Puts | 53 | 22 | 31 | +$395.10 |

The call and put groups differ in dates, symbols, market conditions and admission through the shared risk lock. Their difference is descriptive; it does not prove that a puts-only strategy would reproduce these results.

## Underlying contributions

| Underlying | Trades | Losers | Net all trades | Gross losing trades |
|---|---:|---:|---:|---:|
| AAPL | 13 | 8 | $8.10 | $-226.40 |
| AMZN | 17 | 14 | $-297.10 | $-493.20 |
| GOOGL | 12 | 8 | $-83.60 | $-305.40 |
| IWM | 25 | 18 | $-126.50 | $-359.40 |
| MSFT | 7 | 7 | $-318.10 | $-318.10 |
| NVDA | 22 | 12 | $260.40 | $-425.60 |
| QQQ | 16 | 12 | $-168.80 | $-469.60 |
| SPY | 24 | 13 | $218.80 | $-475.90 |
| TSLA | 7 | 6 | $-139.10 | $-220.80 |

META had no filled trades. SPX was excluded from this run; SPY fills are not SPX fills.

## What happened before and after losing exits

Of the 98 losing trades, 67 had a positive net hypothetical liquidation value while open; 43 had been at least 10% net profitable on the premium invested, 24 at least 20%, and 16 at least 25%, before eventually losing. These are maximum observed one-second executable-bid marks after assumed exit slippage and round-trip fees, not midpoint highs.

Of the 93 stopped trades, 42 later reached hypothetical net breakeven within 30 minutes after exit; 11 reached the original 50% premium target in that interval. Across all 98 losers, 43 recovered to net breakeven. All 98 had some valid post-exit samples. Windows end at 15:55 ET when earlier; a post-exit maximum does not guarantee a fill. These are hindsight price paths, not a rerun with larger stops. They ignore the alternative path’s cash, risk locks, opposite-cross exits and larger potential losses. Missing/invalid samples are not filled in.

This motivates controlled exit/profit-protection experiments. It does not establish an optimal stop or prove that moving a stop to breakeven after +10% would improve total returns; that rule could also cut eventual winners.

## Session and expiry

| Entry session | Trades | Winners | Losers | Net P&L |
|---|---:|---:|---:|---:|
| afternoon | 21 | 4 | 17 | $-263.30 |
| morning | 122 | 41 | 81 | $-382.60 |

133 trades were same-day-expiry options and 10 expired the next day. The default nearest-expiry selection makes this chiefly a 0DTE study. Afternoon entries are conditional on not having hit the two-loss lock earlier; session differences are not independent policy comparisons. The small samples for individual symbols and session slices are not a sufficient basis for excluding them after seeing this result.

## Cost accounting on the identical executed trades

Hypothetical midpoint-to-midpoint movement: +$232.00. Crossing the observed entry/exit spreads: −$406.00. Additional adverse-slippage assumption: −$286.00. Commission assumption: −$185.90. Net: −$645.90. Midpoints are not assumed executable. This decomposition holds the executed trades and timestamps fixed; removing costs would also change stops, position admission and subsequent trades in a new simulation.

None of the 98 losing trades had positive midpoint-to-midpoint movement at its actual exit. Costs erased the aggregate paper edge, but they do not by themselves explain why these individual trades exited at a directional loss.

## Largest five losses

| ID | Symbol | Entry Eastern | Holding minutes | Net loss |
|---|---|---|---:|---:|
| T004 | MSFT | 2026-07-27T10:09:01-04:00 | 1.87 | $-57.30 |
| T028 | NVDA | 2026-08-12T10:00:01-04:00 | 4.95 | $-56.30 |
| T039 | TSLA | 2026-08-24T09:57:01-04:00 | 10.30 | $-54.30 |
| T019 | AMZN | 2026-08-03T10:12:01-04:00 | 1.33 | $-52.30 |
| T066 | AMZN | 2026-09-08T10:03:01-04:00 | 43.28 | $-52.30 |

## Audit and reuse

`engine/scripts/analyze_losses.py` reproduces this diagnostic from the frozen trade log and saved quote archives, without API access, data purchases or strategy changes. The script verifies quote file hashes, trade uniqueness, headline reconciliation and the cost identity. Enriched all-trade and loss-only CSVs include stable IDs, direction, DTE, duration, spreads, cost decomposition, observed maximum/minimum bids and post-exit recovery flags.

Source: `quote-results.json`, `quote-trades.csv` and the SHA-256-verified `databento-quotes/*.csv.gz` for this run. Output: `loss-analysis/summary.json`, `all-trades-enriched.csv` and `losing-trades.csv`. The parent report documents original assumptions and the 287 unpriced open-position seconds. This is exploratory post-analysis of an already examined period; candidate improvements require a separate untouched validation period.
