# Three-month options replay on actual historical NBBO

July 24–October 23, 2026. **Simulated execution on real Databento OPRA one-second bid/ask snapshots. This supersedes the underlying-only signal study.**

Raw Alpaca three-minute underlying prices generate signals. Databento quotes price long-option entries and exits; no trade-bar midpoint or invented spread is used in these results. This is marketable-order replay, not proof that a broker would have filled historical orders.

## Results

| Execution scenario | Trades | Wins | Net P&L | Return on $10,000 | Profit factor |
|---|---:|---:|---:|---:|---:|
| Base: 1s latency, $0.01 extra slippage/side | 143 | 31.5% | $-645.90 | -6.46% | 0.804 |
| Stress: 2s latency, $0.03 extra slippage/side | 133 | 25.6% | $-1,170.90 | -11.71% | 0.625 |

Base ending equity: $9,354.10. Observed maximum drawdown: $1,033.30. Unresolved positions: 0. Unpriced open-position seconds: 287. Drawdown complete at the replay's one-second sampling: False.

## By underlying (base execution)

| Underlying | Trades | Net P&L |
|---|---:|---:|
| SPY | 24 | $218.80 |
| QQQ | 16 | $-168.80 |
| IWM | 25 | $-126.50 |
| AAPL | 13 | $8.10 |
| MSFT | 7 | $-318.10 |
| NVDA | 22 | $260.40 |
| AMZN | 17 | $-297.10 |
| GOOGL | 12 | $-83.60 |
| META | 0 | $0.00 |
| TSLA | 7 | $-139.10 |

SPX is **not tested**. SPY signals are not substituted for SPX contract execution. SPX needs defensible contract selection/underlying coverage. Alphabet is GOOGL.

## Execution and strategy assumptions

- Prior completed raw 3-minute signals; EMA9/VWAP cross aligned with EMA21; same-time 20-session ATR median filter
- Entry windows 09:45-11:30 and 14:00-15:30 ET; 1s signal-to-order latency; reject entry after 5s grace
- ATM standard contract, nearest expiry within 7 days; option eligibility validated by subsequent observed quote, not future profitability
- At most one contract, 2% of equity maximum premium and round-trip fees, cash constrained; no borrowing
- Buy ask + $0.01; sell bid - $0.01; $0.65 commission per contract per side; sufficient displayed size required
- 25% premium stop, 50% target monitored at bid net slippage; next quote at least 1s later executes, so gaps can exceed stop
- Opposite cross or 15:55 ET submits exit; unpriced exits remain open and invalidate final equity
- Two total net losing trades per day across portfolio block new entries; open trades still managed
- NBBO snapshots sampled at 1s, timestamps based on ts_recv; reject crossed, nonpositive or size-zero quotes and sample gaps >2s
- Displayed liquidity is not a guaranteed fill; hidden queue, subsecond movement, broker routing, quote fade and auction behavior unmodeled
- SPX excluded: no validated SPX underlying/contract selection feed; SPY signal is not SPX option execution
- Exploratory defaults, same already-examined period; no claim of out-of-sample validation

These are exploratory defaults, not user-confirmed entry/exit tuning. Premium stop/target, expiration, sizing, latency and fees materially affect results. The earlier underlying study used opposite-cross/session exits without option premium stops/targets, so its metrics are not directly comparable.

## Data coverage and exclusions

Underlying coverage: 65 complete sessions for every tested symbol. Quotes were requested for 62 sessions with candidate entries. Invalid or non-executable quote records rejected: 31,288. Entries rejected: `{"already_open": 1, "premium_budget_cash_or_size": 131, "two_loss_daily_lock": 138}`.

NBBO is sampled once a second. Queues, quote fade, subsecond excursions, routing, exchange-specific fees and market impact are unmodeled. Orders must have sufficient displayed size; the strategy is capped at one contract. The engine uses a cash ledger but does not implement settled-funds/PDT eligibility, assignment/exercise or overnight settlement. It does not permit a fictitious closing fill: unresolved exposure invalidates final equity.

The data is retrospective and this period was already examined. This is not an untouched out-of-sample test, and no parameter search was performed to improve this result.

## Reproduction and audit

Commands:

```
cd ~/backtest-ceo/engine
.venv/bin/python -m backtestceo.options_backtest
.venv/bin/python -m backtestceo.databento_quotes
.venv/bin/python -m backtestceo.quote_backtest
```

Raw quote archives and SHA-256 manifests: `data/backtests/options-vwap-ema-3m-20260724-20261023/databento-quotes/`. Full metrics and assumptions: `quote-results.json`. Individual base/stress trades: `quote-trades.csv` and `quote-stress-trades.csv` in the same run directory. Archived trade-bar stress results remain separately in `results.json`; they are not the headline results above.

Initial selected-data estimate: $1.174873, plus any partially transferred data during the compression switch. Actual billed usage/credit balance was not independently retrieved. No subscription was created. Each downloader invocation rejects estimates above $5; the project budget is $100/month.

Validation: 51 engine tests, 50 frontend tests and TypeScript pass. Engine checks cover quote sides, latency, gaps beyond stops/targets, net-fee daily locking, cash/contract budgets, invalid/missing quotes, no future-price entry and unresolved-exposure handling.
