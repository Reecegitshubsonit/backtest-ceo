# Exact 1DTE options comparison

Period: July 24–October 23, 2026. Real Databento OPRA one-second NBBO; simulated marketable fills. The single strategy change is exact one-calendar-day expiry, with no fallback to 0DTE or a later date. All positions are still closed intraday. SPX remains excluded.

## Results

| Run | Completed trades | Winners | Losers | Net P&L | Return |
|---|---:|---:|---:|---:|---:|
| Original nearest expiry, all signals | 143 | 45 | 98 | $-645.90 | -6.46% |
| Original expiry, same 1DTE-eligible signals | 78 | 28 | 50 | $138.60 | 1.39% |
| Exact 1DTE | 42 | 13 | 29 | $-77.60 | -0.78% |

The 1DTE base run had 42 buys and 42 sells: 84 simulated fills, no live orders. Starting capital $10,000; ending equity $9,922.40; profit factor 0.922. Slower execution (2-second latency, $0.03 adverse slippage per side) produced 39 trades and $-429.70 net P&L (-4.30%).

## Availability and affordability

All 413 underlying entry signals were retained for expiry selection. Exact 1DTE existed for 200; 213 signals had no eligible contract. Of the 200, 144 were rejected by the premium/cash/size budget gate, 13 by the two-loss daily lock, and one because a position was already open. The remaining 42 filled. These counts reconcile to 413 without double-counting skipped opportunities.

The unchanged position limit is one contract and at most 2% of current equity in premium plus round-trip commissions. Consequently, the initial per-trade allowance is approximately $200. More expensive 1DTE contracts therefore change trade admission, not only price behavior. Exact calendar-day DTE also skips signals where the next day is not an expiration; Friday-to-Monday is three calendar days and was not relabeled 1DTE.

The matched comparison uses the same 200 eligible signal identities and all original opposite-cross exit events, replaying risk limits and cash from scratch with the original expiry choice. It controls expiry availability but does not force identical fills or quantities: affordability and the daily loss lock remain endogenous. The matched original rule returned +$138.60, versus −$77.60 for 1DTE. The smaller loss relative to the original full-universe run is not sufficient evidence of an expiry improvement.

## Losing trades

13 winners earned $914.10; 29 losers lost $991.70. Of the losers, 21 hit the premium stop, six exited on an opposite crossover, and two exited at session close. Calls: 21 trades, five wins, net −$259.30. Puts: 21 trades, eight wins, net +$181.70. These descriptive splits are small and were not used to optimize the strategy.

| Underlying | Completed trades | Net P&L |
|---|---:|---:|
| SPY | 3 | $9.10 |
| QQQ | 0 | $0.00 |
| IWM | 27 | $-181.10 |
| AAPL | 2 | $-37.60 |
| MSFT | 0 | $0.00 |
| NVDA | 6 | $164.20 |
| AMZN | 4 | $-32.20 |
| GOOGL | 0 | $0.00 |
| META | 0 | $0.00 |
| TSLA | 0 | $0.00 |

27 of 42 filled trades were IWM. This is not a broad filled-trade sample across the full requested universe. Symbols with zero trades were evaluated but did not obtain fills under these rules.

## Assumptions and limits

- Prior completed raw 3-minute signals; EMA9/VWAP cross aligned with EMA21; same-time 20-session ATR median filter
- Entry windows 09:45-11:30 and 14:00-15:30 ET; 1s signal-to-order latency; reject entry after 5s grace
- ATM standard contract, exactly one calendar day to expiration; skip if unavailable; option eligibility validated by subsequent observed quote, not future profitability
- At most one contract, 2% of equity maximum premium and round-trip fees, cash constrained; no borrowing
- Buy ask + $0.01; sell bid - $0.01; $0.65 commission per contract per side; sufficient displayed size required
- 25% premium stop, 50% target monitored at bid net slippage; next quote at least 1s later executes, so gaps can exceed stop
- Opposite cross or 15:55 ET submits exit; unpriced exits remain open and invalidate final equity
- Two total net losing trades per day across portfolio block new entries; open trades still managed
- NBBO snapshots sampled at 1s, timestamps based on ts_recv; reject crossed, nonpositive or size-zero quotes and sample gaps >2s
- Displayed liquidity is not a guaranteed fill; hidden queue, subsecond movement, broker routing, quote fade and auction behavior unmodeled
- SPX excluded: no validated SPX underlying/contract selection feed; SPY signal is not SPX option execution
- Exploratory defaults, same already-examined period; no claim of out-of-sample validation

All 42 contract expirations were checked against entry dates and equal exactly one calendar day. No unresolved positions remained. Trade and daily cash ledgers reconcile. Observed maximum drawdown: $408.40; 620 open-position seconds had missing/stale quote marks, so drawdown is not complete. This was an exploratory rerun on an already examined period, not a fresh out-of-sample test.

## Reproduce and inspect

Run `cd engine && .venv/bin/python -m backtestceo.one_dte`. The runner has a separate output directory and does not overwrite the original replay. Shared underlying caches are reused. Completed quote archives must cover the requested contracts and pass SHA-256 validation; another expiry’s same-date file cannot substitute.

Output directory: `data/backtests/options-vwap-ema-3m-1dte-20260724-20261023/`. Files: `quote-results.json`, `quote-trades.csv`, `quote-stress-trades.csv`, worst-first `losing-trades.csv`, `signals.json`, `coverage.json`, `matched-baseline-results.json`, `matched-baseline-trades.csv`, and quote manifests.

Additional historical quote estimate: $0.541222 across 39 sessions with eligible signals. This is a provider estimate, not a verified invoice or credit balance. No subscription was purchased. The new-download estimate cap was $5.

Validation: 54 engine tests pass, including strict calendar-DTE selection, no silent expiry fallback, quote cache coverage/integrity and matched-control exit-event preservation. Frontend code was unchanged.
