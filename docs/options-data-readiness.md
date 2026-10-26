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

## Free alternative implemented (2026-10-26)

`python -m backtestceo.free_options --symbol SPY --date 2026-10-23` fetches the public `post-no-preference/options` DoltHub table without credentials. The source has actual bid/ask columns and Greeks, but only a date (no exact observation timestamp, no sizes, volume or open interest). Archive metadata explicitly forbids using these records as an intraday execution tape, conservatively makes snapshots available the following session, records chain limitations and a SHA-256, and preserves upstream README/license documents when provided. No-source dates remain missing, not completed header-only files. This is an additional dataset, not a replacement for the ongoing Alpaca download.

This is a viable free research input for selected daily strategies, subject to coverage and source-quality validation. It is not proof of historical NBBO or executable size. No quote should be fabricated or filled forward as a fresh market. Six SPY/QQQ date requests for October 21–23 are the initial validation batch, not a full-market backfill.

For intraday validation without a Theta subscription, Databento officially offers eligible new teams $125 in historical-data credits, expiring after six months. A verified cost estimate and credit balance must precede any request; do not assume all years/all contracts fit the credit or allow paid overages. No account was created and no Databento data was fetched in this session.
https://databento.com/docs/faqs/usage-pricing-and-data-credits

OptionsDX also advertises zero-cost variants and provides timestamp, bid/ask and size fields, but not every year/frequency is free. Its public sample download returned HTTP 406 in our direct request, so no OptionsDX data was imported. Its product catalogue must not be described as a verified unrestricted free intraday archive.
https://www.optionsdx.com/shop/
https://www.optionsdx.com/option-chain-field-definitions/

Alpaca's indicative quotes are modified derivatives, not actual OPRA quotes. Recording them going forward must retain that designation; it does not solve missing real historical NBBO.
https://docs.alpaca.markets/us/docs/historical-option-data
