# Prompt for an outside reviewer

Paste everything below the line into another AI.

---

You are reviewing a failed search for a profitable trading strategy on Kalshi (a US prediction-market exchange). Read what was tried and what came out, find the mistakes or blind spots, and propose strategies that have a real chance of being profitable after costs. If the answer needs new data or research, say exactly what to collect and how to test it. Be blunt. If you think a retail trader cannot win here, say so and explain why.

## Constraints

- Account: about $25 on Kalshi, trading through the official REST API (v2) from a Linux machine. Small size, so capacity is not a problem, but every cent of fees matters.
- Costs: the taker fee is ceil-to-the-cent(0.07 × contracts × P × (1−P)), charged per order. Some series use a maker fee of 0.0175 × C × P × (1−P); others charge makers nothing. Taking liquidity also pays the bid/ask spread.
- Data Kalshi provides:
  - Market metadata and settlement results for all markets.
  - Public trade prints with no trader identity.
  - Candlesticks (period 1 min / 1 h / 1 day) with bid, ask and trade OHLC plus volume.
  - The current order book, plus live order-book deltas over websocket.
  - Markets settled before 2026-09-05 sit in a "historical" archive endpoint that allows one candlestick request per market; newer markets can be batched.
- Kalshi has no historical order-book data. Depth or queue history only exists if you record it yourself from now on.
- Other data we have used: Open-Meteo (GFS, ECMWF, ensembles, previous model runs), NWS forecasts, NBM text bulletins via the Iowa Environmental Mesonet, and Rivo (rivo.markets), which streams named Kalshi traders' trades of $1,000 or more.
- Rules: no bypassing bot protection, no market manipulation, nothing against Kalshi's terms.

## What was tried and what happened

### 1. Favorite–longshot maker strategy (paper only)
Rest bids on favorites (about 80–95¢) and expect the longshot bias to pay. It was never traded live. In the backtest below, buying 80–95¢ favorites 24 hours before close as a taker returned:
- −0.1% per event on the search weeks (t −0.1)
- −4.2% on the validation week (t −2.5)
- +3.7% on the holdout week (t 3.3)

The sign flips from week to week, so we read this as noise, not an edge.

### 2. Copying top Kalshi traders (live with a few dollars)
We ranked leaderboard traders on Rivo data by out-of-sample returns after slippage and fees, and copied six of them on Rivo's push stream. Orders are immediate-or-cancel, with at most 3¢ slippage, at most 5 minutes after the leader's trade, and $2 per trade. Problems:
- Rivo only shows trades of $1,000 or more, so we only see part of each trader's activity.
- The first live orders failed because Kalshi splits cash across "exchange shards" (now fixed with automatic shard transfers).
- No confirmed fills yet, so no track record.
- It can't be backtested, because Kalshi's trade data has no trader IDs.

### 3. Weather temperature markets (KXHIGH*, 19 cities)
We built probability models for the daily high-temperature brackets and compared them with the market price about 1 day before the event, over roughly 58 days and 6,000+ brackets:
- GFS + ECMWF deterministic models plus ensembles, with per-station bias and spread fitted leave-one-out: Brier score 0.1286, against 0.1065 for the market price.
- NWS National Blend of Models (NBM): Brier score 0.1337 against 0.1051, with fitted station bias of about −1 to +1.6°F and a standard deviation of 1.9–3.5°F.

Trading the model's "edges" returned −14% to −24% ROI. On these metrics the market beat every forecast we built. A market-only rule (buy 50–80¢ weather favorites) came out at −0.2% on the holdout.

### 4. Systematic search over 100,000 parameter combinations
- **Data:** 164,326 settled markets (closing 2026-10-03 to 2026-11-04), sampled with at most 150 markets per series and at least 50 contracts of volume, all non-combo series. That gives 639,376 decision rows.
- **Decision points:** 1, 3, 6, 12, 24, 48, 96 or 168 hours before close, using the last hourly candle's bid/ask (quotes older than 3 hours dropped).
- **Fills:** at the ask, plus the taker fee per order.
- **Parameters searched:**
  - Side: YES, NO, favorite or longshot.
  - Price band: 55 bands between 2¢ and 98¢.
  - Hours before close.
  - Category: the top 8 categories, or all.
  - Minimum 24-hour volume: 0, 100, 1k or 10k contracts.
  - Maximum spread: 1–10¢.
  - Momentum filter: follow or fade a 2–10¢ move over 6 or 24 hours.
  - Exit: hold to settlement, or take-profit/stop-loss at 10/10, 20/10 or 5/5¢.
  - Size: 1, 10 or 50 contracts.
- **Splits by close date:** first 60% for search (Oct 3–21, 29,809 events), next 20% for validation (Oct 22–28, 14,304 events), last 20% as holdout (Oct 29–Nov 4, 14,384 events). Each market appears in exactly one split.
- **Evaluation unit:** returns are averaged per event, because markets within one event are correlated.
- **Pipeline:**
  - Keep combos with at least 30 events and a positive mean on the search split.
  - Take the top 200 by t-stat and require a positive validation result with at least 15 events.
  - Rank by the lower of the search and validation t-stats.
  - Require at least 70% of one-step parameter neighbours to be profitable.
  - Test the top 10 on the holdout, once.
  - Compute the Deflated Sharpe Ratio with N = 100,000.
  - Run the identical pipeline on shuffled outcomes as a luck benchmark.

**Real data vs. shuffled outcomes:**

| | Real data | Shuffled |
|---|---|---|
| Combos with ≥30 events and positive mean | 1,603 | 676 |
| Best search t | 36.1 | 2.1 |
| Combos with t > 3 | 18 | 0 |

**Holdout:**
- Three finalists passed holdout t ≥ 2 with DSR 1.00:
  - NO at 95–98¢, 6h before close, Economics: +3.4% per event
  - NO at 95–98¢, 12h before close, Sports: +3.6%
  - YES at 95–98¢, 12h before close, Sports: +2.9%
- All three had zero losses, which is why the t-stats look huge. Across all splits they went 0/105, 0/67 and 0/64 events lost, against a break-even loss rate of 2.8–3.8%.
- The binomial p-values are 0.02, 0.08 and 0.16, and none pass a Bonferroni correction across the 10 finalists. A loss costs about −97%, roughly 30 wins.
- The other seven finalists were flat or negative on the holdout.
- Without the filters, 95–98¢ favorites lose 4–5% of the time, at or above break-even (~4%), for −0.4% to −1.7% per trade.
- 2–10¢ longshots lost −68% per event.

**Verdict:** nothing survives.

## Known weaknesses of what we did

1. **Short history.** Only about 2 months, a one-week holdout, and one market regime. The archive before 2026-09-05 (years of markets) was not downloaded because it needs one request per market.
2. **Taker-only fills.** Every strategy paid the spread plus the taker fee. Maker strategies (resting limit orders, earning the spread, cheaper or zero maker fees) were not simulated because we have no book history to model queue position and fills.
3. **Hourly candles.** These miss intra-hour moves, so news-speed and stale-quote strategies couldn't be tested.
4. **Single markets only.** No cross-market structure was tested: bracket sets in one event whose prices should sum to $1, ladders like "above X" vs "above Y" that must be monotonic, Kalshi vs Polymarket or sportsbook prices, or Kalshi vs listed options (e.g. S&P, BTC or Fed-funds futures implied probabilities).
5. **No external information.** Apart from weather, no outside data was used: sports odds, economic consensus forecasts, polling, or exchange prices for financial brackets.
6. **The shuffled benchmark.** It permutes whole return rows, which breaks the link between price and payoff, so it may be a weak luck control.

## What I want from you

1. Point out flaws in the methodology above, or anything we got wrong about Kalshi's fees, data or mechanics.
2. Rank 3–5 strategy ideas by likely profit after costs for a tiny account. For each, give:
   - The edge mechanism: who is on the other side and why they lose.
   - The exact data needed and where to get it (with API endpoints where you can).
   - A precise test with the same discipline: time splits, one holdout test, multiple-testing correction, a luck benchmark, and costs.
   - What would kill the idea.
3. Say which is most promising for a maker approach (resting orders) given Kalshi's fee schedule, and how to record our own order-book data to test it honestly.
4. Name any series where Kalshi prices can be checked against a sharper outside price (e.g. sportsbook closing lines, CME FedWatch, options-implied distributions for index or crypto brackets), and how stale Kalshi quotes typically are against it.
5. If nothing is realistically profitable at this size, say so plainly and explain why.
