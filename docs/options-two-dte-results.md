# Exact 2DTE options replay

July 24–October 23, 2026. Only expiry changed from the prior studies: exactly two calendar days after entry, skipping unavailable expirations. All positions remain intraday. Same completed three-minute EMA9/VWAP crossover, EMA21 confluence, ATR/session filters, stops, target, cash and portfolio two-loss lock. Real Databento OPRA CBBO-1s quotes; simulated fills, not actual orders.

| Direction | Eligible signals | Trades | Winners | Losers | Net P&L |
|---|---:|---:|---:|---:|---:|
| Calls | 108 | 6 | 0 | 6 | -$186.80 |
| Puts | 68 | 7 | 3 | 4 | +$120.90 |
| Total | 176 | 13 | 3 | 10 | -$65.90 |

Starting $10,000; ending $9,934.10; return -0.659%; win rate 23.08%; profit factor 0.7901. 13 round trips / 26 simulated fills. Of 413 signals, 237 lacked an exact 2DTE contract. Among 176 eligible signals: 156 premium/cash/size rejections, six daily-loss-lock rejections, one missing valid entry quote within the grace period, and 13 trades. All filled expirations were verified; P&L and admission counts reconcile; no unresolved positions.

Ten losers: five premium stops, three opposite crosses, two session exits. Slower execution (two-second latency, $0.03 adverse slippage per side) yielded 12 trades and -$182.60. Base execution uses one-second latency, ask+$0.01 entry/bid-$0.01 exit, $0.65 commission per contract per side. Unchanged one-contract maximum and 2% equity premium-plus-fees budget (~$200 initially) make most selected 2DTE contracts unaffordable. No cheaper-strike substitution was introduced.

Provider estimate for additional data: $0.482610, not a verified invoice. Download estimate capped at $5; hashes and requested contract coverage validated. 55 engine tests passed.

Observed drawdown $210.50 is incomplete: 24 open-position seconds lacked valid fresh marks. SPX excluded. Displayed one-second quotes do not guarantee fills; routing, partial executions, subsecond quote movement, settlement/PDT eligibility and market impact are unmodeled. Same examined period, not out-of-sample. Thirteen trades is a small sample. Comparing total P&L to 0DTE (-$488.80/136 trades) or 1DTE (-$77.60/42 trades) does not establish an expiry advantage: availability, affordability and loss-lock paths differ.

Reproduce: `cd engine && .venv/bin/python -m backtestceo.two_dte`. Separate outputs under `data/backtests/options-vwap-ema-3m-2dte-20260724-20261023/`: quote-results.json, quote-trades.csv, losing-trades.csv (worst first), quote-stress-trades.csv, signals.json and source quote archives/manifests.
