# Exact 0DTE options replay

July 24–October 23, 2026. Same frozen strategy and portfolio rules as the exact 1DTE study; only expiry changed to the entry date, with no fallback. Recorded Databento OPRA CBBO-1s quotes, simulated marketable fills, no actual orders. All quote archives already existed, covered requested contracts, and passed SHA-256 checks. No downloads or new data charges.

| Direction | Eligible signals | Completed trades | Winners | Losers | Net P&L |
|---|---:|---:|---:|---:|---:|
| Calls | 187 | 86 | 23 | 63 | -$788.80 |
| Puts | 116 | 50 | 20 | 30 | +$300.00 |
| Total | 303 | 136 | 43 | 93 | -$488.80 |

Starting capital $10,000; ending equity $9,511.20; return -4.888%; win rate 31.62%; profit factor 0.8402. 136 round trips means 272 simulated fills. All filled expirations were verified to equal entry dates. No unresolved positions. Trade P&L reconciles to equity.

413 underlying signals: 110 had no same-day contract, leaving 303 eligible. 120 were blocked by the two-loss daily lock; 47 by premium/cash/size limits; 136 traded. 90 losing trades exited at the premium stop, three on opposite crossovers. Loss ledger is sorted worst first.

Stress execution (two-second latency and $0.03 slippage per side) yielded 127 trades, -$1,048.10, ending equity $8,951.90. Base assumptions retain one-second latency, buy ask+$0.01/sell bid-$0.01, $0.65 per contract per side, one-contract maximum, 2% equity premium budget, 25% premium stop, 50% target, opposite-cross/15:55 ET exits, and two total net losses per day across the portfolio. Entry signals use completed three-minute candles, EMA9/VWAP crossing with EMA21 confluence, prior-session ATR filter and the same session windows.

The 1DTE run returned -$77.60 on 42 trades. This full-universe comparison has different expiry availability and affordability; it does not isolate expiry performance on matched opportunities. The original nearest-expiry baseline was mixed 0–7DTE and must not be labeled this exact 0DTE test.

Limitations: same already-examined period, not out-of-sample; SPX excluded. One-second displayed quotes do not guarantee broker fills and omit routing, queue and subsecond effects. Observed drawdown $745.10 is incomplete because 43 open-position seconds lacked valid fresh marks. Settlement/PDT eligibility is not modeled. These results show a losing exploratory strategy, not a validated trading edge.

Reproduce: `cd engine && .venv/bin/python -m backtestceo.zero_dte` (cache only, no network fallback). Outputs: `data/backtests/options-vwap-ema-3m-0dte-20260724-20261023/quote-results.json`, `quote-trades.csv`, `losing-trades.csv`, `quote-stress-trades.csv`, `signals.json`. Engine tests: 55 passed, including strict 0DTE selection without later-expiry fallback.
