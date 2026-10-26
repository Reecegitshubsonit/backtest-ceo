# Options execution data — 2026-10-26

Actual read-only Alpaca account checks: expired SPY contract lookup and historical trades succeeded for 2026-10-23; `/v1beta1/options/quotes` returned HTTP 404. No historical options bid/ask tape has been obtained. General historical-feed marketing wording is not evidence of an options quotes endpoint. Claude's collector was confirmed running and left undisturbed.

The existing daily options bars and indicative snapshots must not be presented as historical NBBO. The engine currently serves charts/data; a strategy execution simulator is still outstanding.

## Prepared quote download

`engine/backtestceo/theta.py` requests one session and one expiration from local Theta Terminal v3. It preserves original quote CSV in gzip and records provenance, sampling interval, row count and invalid market count in a JSON manifest. Empty/non-quote responses fail without substituting bars. Raw invalid records remain for audit and must be rejected downstream. Interrupted writes are atomic; completed archives are reused.

Requires Theta Terminal v3 running on port 25503 and authenticated with an entitled account. No purchase was made, and no live subscribed Theta download has been verified. Start with a confirmed listed contract, for example:

```
cd ~/backtest-ceo/engine
.venv/bin/python -m backtestceo.theta --symbol SPY --expiration 2026-10-23 --date 2026-10-23 --strike 670 --right call
```

The example strike is not a coverage guarantee. Default interval is tick; `--interval 1s` or `1m` records sampled data explicitly. Omit strike for an entire expiration only after validating a small sample. Default destination: `data/options/quotes/thetadata/`. No mass tick backfill should precede strategy-universe selection.

Official Theta v3 entitlement matrix lists Standard options tick data from 2016-01-01, quote/trade/trade-quote/open-interest/IV/first-order Greek endpoints; higher-order and trade Greeks need Pro. Underlying index data is separate. See:

- https://thetadata.net/docs/Articles/Getting-Started/Subscriptions.html
- https://thetadata.net/docs/operations/option_history_quote.html
- https://www.thetadata.net/faq

## Realism requirements

Still required: no-lookahead joins to raw underlying prices, stale/invalid quote rejection, conservative ask-buy/bid-sell baseline, size limits, contract multipliers, fees, latency/slippage, multi-leg assumptions, partial fills, corporate actions, assignment/exercise, settlement, margin and out-of-sample validation. NBBO does not guarantee a fill or establish queue position. Bar-based results remain exploratory; quote collection alone does not make the current app a validated backtester.
