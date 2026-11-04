# Strategy handoff for external review

Purpose: everything another reviewer (human or AI) needs to judge, reproduce, and improve the best strategies found
in this branch (`claude/options-indicator-backtest-60d`). Exact rules are taken from the code, not from chat.

## 1. Bottom line

| Rank | Strategy | Evidence strength | Holdout window result (trades / avg $ / Sharpe) |
|---:|---|---|---|
| 1 | Daily ETF mean reversion (5 variants, shares) | Strongest: passed 3-month and 6-month walk-forward tests | see section 3 |
| 2 | v2 0DTE iron condor 15:00 (SPY, QQQ) | Medium: passed 3m test; tuned on overlapping data | 125 / $16.31 / 4.43 |
| 3 | v2 RSI14-reversion 0DTE credit spread 15:00 | Medium: passed 6m test; tuned on overlapping data | 59 / $29.38 / 4.61 |
| 4 | v2 0DTE bull put 15:00 | Medium | 82 / $15.99 / 3.74 |
| 5 | v2 0DTE bear call 10:00 | Medium, low trade count | 35 / $20.24 / 3.87 |
| 6 | v2 EMA+VWAP trend 0DTE credit spread 11:00 | Medium, small edge per trade | 77 / $5.27 / 5.11 |
| 7 | Search leads: 30DTE credit spreads / condors on daily IBS and gap signals | Weak: failed multiple-testing correction | see section 5 |

"Holdout window" = 2026-04-16 .. 2026-11-02. Strategies 1-6 were tuned on data that overlaps this window, so their
numbers there are optimistic. Strategy 7 was selected without seeing it, but its edge could not be separated from luck.

Recommendation from this work: trade #1, paper-trade #2-#5, treat #7 as research leads only.

## 2. Data and cost model (applies to everything)

* Source: Alpaca market data API only.
  * Stocks: SIP bars (5-min and 30-min intraday; daily split/dividend adjusted with `adjustment=all`).
  * Options: trade bars only, available from 2024-02. Feed is "indicative" (OPRA agreement not signed).
* **Not available:** historical option bid/ask quotes (endpoint returns 404); Level 2 / depth history; signed option order flow.
  Stock L1 quote history exists but was not used.
* Option fills: trade-bar VWAP +- modelled half-spread. Buys at the modelled ask, sells at the modelled bid, never the midpoint.
  * Half-spread: index ETFs max($0.01, 1% of price); single stocks max($0.02, 2% of price).
  * v2 "pessimistic" mode (used for all v2 numbers here): 2x that half-spread and strict fills (fill must come from the
    entry bar itself, no looking up to 3 bars ahead).
* Option fees: $0.65 commission + $0.03 regulatory = $0.68 per contract per side.
* Share costs: 2 bps per side (`COST = 0.0002` of notional).
* Expiry settlement: intrinsic value at the underlying's last close. No early assignment, pin risk, or exercise
  modelling.
* OCC symbols were constructed (contract-list endpoint blocked), not fetched from a contract master.

**Biggest unknown:** real bid/ask on 0DTE options near the close. If true spreads are wider than 2x the model,
the 0DTE edges shrink fast (average edge is only $5-$30 per spread).

## 3. Daily ETF strategies (shares) - `engine/backtestceo/shares_daily.py`

Universe (18): SPY QQQ IWM DIA XLK XLF XLE XLV XLY XLP XLI XLU XLB SMH GLD TLT EEM EFA.

Execution: signal on today's close, enter at that close, exit at the close of the day the exit rule fires.
$5,000 per trade, at most 5 open positions, $25k account. When there are more candidates than free slots, lowest
RSI(2) first. Indicators: SMA/EMA on daily closes, RSI with Wilder smoothing, IBS = (close - low) / (high - low).
"h" = days held. Requires >200 bars of history.

| Strategy | Entry | Exit | k used | Holdout: trades / win% / avg $ / total $ / max DD $ / Sharpe |
|---|---|---|---:|---|
| RSI(2) + IBS | close > SMA200 AND RSI(2) < k AND IBS < 0.25 | close > SMA5 OR IBS > 0.8 OR h >= 5 | 10 | 61 / 73.8 / 56.63 / 3454 / -261 / 3.42 |
| EMA snap-back | close > EMA200 AND close < EMA5 x (1 - k%) | close > EMA5 OR h >= 10 | 1.0 | 89 / 71.9 / 34.66 / 3084 / -891 / 3.06 |
| Connors RSI(2) | close > SMA200 AND RSI(2) < k | close > SMA5 OR h >= 10 | 10 | 82 / 70.7 / 34.87 / 2859 / -922 / 2.75 |
| k down closes | close > EMA200 AND >= k consecutive down closes | close > SMA5 OR h >= 10 | 3 | 82 / 73.2 / 28.97 / 2376 / -804 / 2.55 |
| IBS | close > SMA200 AND IBS < k | IBS > 0.7 OR h >= 3 | 0.1 | 143 / 56.6 / 15.25 / 2181 / -1040 / 1.75 |

Known weaknesses: long-only, all in uptrend regime, highly correlated with each other (same dips); 2024-2026 was a bull
market. Untested in a sustained bear market. No overnight gap risk modelling beyond close-to-close.

## 4. v2 0DTE options strategies (SPY, QQQ) - `engine/backtestceo/options_v2.py`

All use 0DTE options (expire same day), 1 contract per leg, intraday 5-min bars.

Config tuple in code: `(kind, a, w, entry, stop, tgt, orf, gap, mincr)`.
* `a` = short-strike offset from spot as a fraction (0.0025 = 0.25%). Spot = close of the 5-min bar before entry.
  Strike = round(spot x (1 +- a)) to whole dollars.
* `w` = wing width as a fraction of spot (long strike = short strike +- w).
* `stop` = exit if loss >= stop x credit; `tgt` = exit if profit >= tgt x credit (None = hold to expiry).
* `orf` = skip the day if (session high - low so far) / open > orf (opening-range filter).
* `gap` = skip if |open / previous close - 1| > gap.
* `mincr` = minimum net credit in $ per share to take the trade.
* Stops/targets checked on 5-min marks; exit fills on the next bar.

| Strategy | Tuple | Plain rules |
|---|---|---|
| 0DTE iron condor | ("IC", 0.0025, 0.005, "15:00", None, None, 0.01, None, 0.10) | At 15:00 sell put 0.25% below and call 0.25% above spot, buy wings 0.5% further out. Skip if the day's range so far > 1%. Need >= $0.10 credit. Hold to close. |
| 0DTE bull put | ("PUT", 0.0025, 0.01, "15:00", None, None, 0.01, None, 0.10) | At 15:00 sell put 0.25% below spot, buy put 1% further below. Range filter 1%. Credit >= $0.10. Hold. |
| RSI14 reversion spread | ("DIR:RSI14 reversion", 0.0025, 0.01, "15:00", None, None, None, None, 0.10) | At 15:00, 5-min RSI(14) < 40 -> sell put spread; > 60 -> sell call spread; else no trade. Short 0.25% OTM, 1% wide. Hold. |
| 0DTE bear call | ("CALL", 0.0075, 0.005, "10:00", None, None, 0.006, None, 0.25) | At 10:00 sell call 0.75% above spot, buy 0.5% further up. Skip if range so far > 0.6%. Credit >= $0.25. Hold. |
| EMA+VWAP trend spread | ("DIR:EMA+VWAP trend", 0.0075, 0.01, "11:00", None, None, 0.006, None, 0.0) | At 11:00, 5-min close > VWAP AND EMA9 > EMA21 -> sell put spread; both below -> sell call spread. Short 0.75% OTM, 1% wide. Range filter 0.6%. Hold. |

Holdout-window results (pessimistic execution, 1 contract):

| Strategy | Trades | Win % | Avg $ | Total $ | Max DD $ | Sharpe |
|---|---:|---:|---:|---:|---:|---:|
| 0DTE iron condor 15:00 | 125 | 88.8 | 16.31 | 2039 | -232 | 4.43 |
| 0DTE bull put 15:00 | 82 | 93.9 | 15.99 | 1311 | -299 | 3.74 |
| EMA+VWAP trend 11:00 | 77 | 66.2 | 5.27 | 406 | -49 | 5.11 |
| RSI14 reversion 15:00 | 59 | 91.5 | 29.38 | 1734 | -194 | 4.61 |
| 0DTE bear call 10:00 | 35 | 91.4 | 20.24 | 708 | -143 | 3.87 |

Known weaknesses:
* Short-premium, negatively skewed: ~90% win rate, losses up to ~(width - credit) x 100 per spread. A few bad days can erase months.
* Only 2 underlyings; trade counts per strategy are 35-125 over 6+ months.
* Earlier 6-month run: only 22 of the top 50 configs stayed profitable out of sample, so the parameter choice is fragile.
* Fills near the 15:00-16:00 close are the least reliable part of the model.

## 5. 100,000-combination search - `engine/backtestceo/osearch/`

Method:
* Symbols SPY QQQ IWM NVDA TSLA AAPL. 30-min bars. Option history 2024-02-01 .. 2026-11-02.
* Time split by entry day: search 60% (2024-02-01..2025-09-25), validate 20% (2025-09-26..2026-04-15), holdout 20%
  (2026-04-16..2026-11-02).
* Search space: 38 entry signals (EMA, VWAP, RSI, breakout, candle patterns, gap, daily RSI2/IBS/SMA) x invert x
  trend filter x vol filter x 4 entry times x 4 DTE buckets x 32 structure families x profit target x stop = 3.7M combos;
  100,000 sampled.
* Selection: top 1000 by search Sharpe -> validation -> neighbour test (>= 2/3 of one-step neighbours profitable) ->
  top 10 run on the holdout once.
* Corrections: Deflated Sharpe Ratio; Bonferroni (p < 0.005) on the 10 holdout tests; identical search on shuffled signals
  as a luck benchmark.
* Strikes are picked by Black-Scholes delta from the last option print before entry. Entry fills at the worse of that
  print and the entry-bar VWAP, +- half-spread.

Luck benchmark:

| Run | Best search Sharpe | Passed validation | Best validation Sharpe |
|---|---:|---:|---:|
| Real signals | 3.29 | 110 | 9.22 |
| Shuffled signals | 2.94 | 47 | 9.49 |

Result: **0 of 10 survive.** Deflated Sharpe is about 0 for every finalist. Shuffled signals produced a holdout winner
with p = 0.002, so lucky hits of this size are expected.

Best leads anyway (holdout, 1 contract; 2x-spread stress in last column):

| Signal (underlying) | Structure | Holdout trades / avg $ / Sharpe / p | 2x spread avg $ / Sharpe |
|---|---|---|---|
| Daily IBS < 0.2, trend-aligned (above SMA200), high-vol regime | 30DTE bull put credit spread, short 0.15 delta, long 0.10 delta, enter 14:00, take profit at 50% of credit, no stop | 60 / 32.11 / 7.07 / 0.0003 | 19.94 / 5.98 |
| Gap > 0.3% in trend direction, high-vol | 30DTE iron condor, short 0.15 delta, long 0.05 delta, enter 12:00, take profit 50%, stop at 3x credit | 182 / 60.33 / 2.47 / 0.033 | 39.50 / 1.64 |
| Daily IBS < 0.3 (or > 0.7 for the call side), high-vol | 30DTE credit spread, short 0.15 delta, long 0.05 delta, enter 14:00, take profit 75% | 192 / 67.51 / 1.75 / 0.097 | 57.70 / 1.50 |
| VWAP: price 0.2% from VWAP, inverted (fade), trend-aligned, high-vol | 30DTE iron condor, 0.15 / 0.05 delta, enter 12:00, take profit 50%, stop at 3x credit | 164 / 48.13 / 1.99 / 0.070 | 26.72 / 1.11 |

"High-vol" = 20-day realised vol above its 1-year median. "Wing -0.10d" in the raw output means the long leg's delta
is 0.10 lower than the short leg's.

Pattern worth noting: everything that held up is short premium (credit spreads/condors at 0.15 delta), mostly gated by
daily mean-reversion signals (IBS, RSI2) in high-vol regimes. That matches the share strategies in section 3. Long
options and debit spreads never survived.

## 6. Bugs found and fixed (a reviewer should check for these)

1. **Look-ahead in strike selection.** The first search run picked strikes using the entry bar's own VWAP, so it could
   see the next 30 minutes; validation Sharpe was 12.8. Fixed before the holdout was touched. The v2 engine was checked
   and picks strikes from the prior bar's close, so it does not have this bug.
2. NVDA June 2024 10:1 split: positions spanning the split are skipped.
3. Snapshot-quote spread calibration was rejected: the indicative feed showed absurd spreads (e.g. a $0.53 half-spread on
   a $1.45 QQQ option, stamped 16:14 ET). See `options-search/spread_model.md`.

## 7. What a reviewer should do next

1. Get real historical option quotes (OPRA via Alpaca subscription, Polygon/Massive, CBOE DataShop, ThetaData) and
   re-run the v2 0DTE strategies with true bid/ask fills. This is the single biggest risk.
2. Test the daily share strategies over 2007-2023 (2008, 2020, 2022 drawdowns) before trusting them.
3. Paper-trade the 0DTE condor and the IBS put spread for 4-8 weeks and compare fills with the model.
4. Size short-premium trades by max loss (e.g. risk <= 2% of the account per spread) with a daily loss stop.
5. Do not re-optimise on the holdout window; it has been used.

## 8. Files

| Path | What |
|---|---|
| `engine/backtestceo/shares_daily.py` | Daily share strategies |
| `engine/backtestceo/options_v2.py`, `options_fix.py`, `options60.py` | v2 0DTE options engine and indicators |
| `engine/backtestceo/osearch/` | 100k search: `data.py` fetch, `outcomes.py` trade simulation, `signals.py`, `search.py`, `compare.py` |
| `docs/backtests/options60/` | First 60-day study |
| `docs/backtests/options-v2/`, `options-v2-6m/` | 3-month and 6-month v2 results |
| `docs/backtests/options-search/README.md` | Full search report |
| `docs/backtests/options-search/*.json` | Raw finalists, holdout, and 2x-spread stress results |

Reproduce (from `engine/`; data cache is gitignored, so re-fetch first, which takes about 105 minutes at the rate limit):

```
python3 -m backtestceo.osearch.data
python3 -m backtestceo.osearch.outcomes
python3 -m backtestceo.osearch.search search
python3 -m backtestceo.osearch.compare
```

The holdout command refuses to run twice; delete `data/osearch/search/*/holdout.json` only if you accept that the
holdout is no longer clean.
