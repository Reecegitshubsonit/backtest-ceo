# Three-month VWAP / EMA signal study

**Exploratory underlying-only test. This is not an options P&L backtest.**

Period: July 24–October 23, 2026. Existing Alpaca consolidated minute bars, aggregated to three minutes. All ten symbols supplied 65 complete regular sessions. No billable Databento data requested. The existing Scalp City Databento key entry was tested via metadata and rejected with auth_invalid_username_in_basic_auth; no secret is included here.

Combined: 248 trades; 23.79% wins; 0.607 underlying profit factor; mean net directional underlying move -13.76 basis points per trade.

| Underlying | Trades | Wins | Mean net underlying move (bp) |
|---|---:|---:|---:|
| SPY | 24 | 20.8% | -9.48 |
| QQQ | 24 | 29.2% | -9.34 |
| IWM | 24 | 25.0% | -10.52 |
| AAPL | 22 | 18.2% | -22.89 |
| MSFT | 25 | 16.0% | -32.23 |
| NVDA | 27 | 18.5% | -25.46 |
| AMZN | 25 | 28.0% | -6.41 |
| GOOGL | 26 | 23.1% | -6.13 |
| META | 21 | 38.1% | 4.03 |
| TSLA | 30 | 23.3% | -15.89 |

## Frozen exploratory assumptions

- EMA9/21 continuous across RTH sessions; daily VWAP from minute vw*volume
- ATR14 Wilder includes overnight gap; above 20-prior-session median at same time of day
- Confirmed EMA9 crossing VWAP, aligned with EMA21; next-bar open entry
- Exits opposite cross at next open or 15:57 ET; no option premium stop or profit target
- Entries 09:45-11:30 and 14:00-15:30 ET; skip incomplete 130-bar sessions
- Portfolio two-loss lock based on underlying net move, not option P&L; deterministic symbol-order ties
- 2bp per side assumed underlying friction; no dollars, options returns, or capital equity curve
- SPX shares SPY signal only, no duplicate exposure or SPX option results
- GOOGL used for Alphabet; all choices are exploratory defaults, not user-confirmed optimized rules

## Interpretation and limits

The tested signal specification has negative average directional underlying movement after a fixed 4bp round-trip friction assumption. That assumption is an underlying sensitivity cost, not measured options spreads, fees or market impact. Profit factor aggregates directional underlying returns and is not a capital-weighted portfolio return. No dollar P&L, option profit, equity drawdown or Sharpe is claimed.

Exits, option selection, position sizing and premium stop/target rules were never confirmed by the user. This run uses opposite-cross/session-close exits, not the previously suggested 25% option stop or 50% option target. The two-loss stop uses underlying directional outcomes as a proxy, not actual option P&L. Simultaneous events use alphabetical symbol ordering; open positions can finish after the second loss. It is not a complete multi-asset options risk engine.

SPX has no native traded volume and was not given a fabricated VWAP. SPY supplies the prospective SPX signal; there are no duplicate SPX trades or SPX option results in these totals. Historical bars came from the collector with adjustment=all. Raw underlying prices and actual option quote evidence are still required for option strike matching and execution.

Reproduce: `cd engine && .venv/bin/python -m backtestceo.cross_backtest`. Machine-readable assumptions, results and the individual trade log are in `data/backtests/vwap-ema-3m-20260724-20261023/`.

Validation: 40 engine tests pass, including next-bar execution, two-total-loss stopping, incomplete-session exclusion and prefix-invariant indicators. Tests do not establish vendor data quality or option execution realism.
