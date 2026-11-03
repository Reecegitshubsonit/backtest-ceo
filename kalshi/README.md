# kalshibot: favorite-longshot maker bot (read-only + paper)

Rests post-only **bids on the favorite side** (80–95¢) of liquid Kalshi markets and holds to settlement.
That captures the documented favorite-longshot bias as a **maker** (lower or zero fee, earns the spread)
instead of a taker. It also has a copy-trading mode (below). **This code places no real orders**: the client implements only GET requests, and paper mode
simulates fills against Kalshi's public trade tape.

## Copy trading (paper): `kalshibot copy`

Kalshi has a leaderboard and public, opt-in trader profiles, and you can follow traders and get notified
when they trade. The API itself gives no way to see who traded: `GET /markets/trades` has no user field,
and there is no documented endpoint for other users' positions. So the copy bot takes its signals from
outside the API, through any of these routes:

| Route | How |
|---|---|
| HTTP | `POST http://host:8787/signal`, header `X-Token`, body JSON or the notification text |
| Inbox file | append one signal per line to `data/signals.jsonl` (for an email or notification forwarder) |
| One-off | `kalshibot copy signal 'alice bought 120 Yes on Will the Fed cut rates in December? at 62¢'` |

JSON signal: `{"trader","ticker" or "market","side","action":"buy|sell","price","contracts","ts"}`.
A market title (from a notification) is fuzzy-matched to an open ticker.

Guards on each copy:
- The trader must be in your allowlist (`traders`, with a size multiplier).
- The signal must be no older than 5 minutes.
- Our ask must be within 3¢ of the leader's price.
- The price must be between 10¢ and 95¢. Longshots are skipped because of the bias below.
- Caps of $10 per trade, $30 per market, $150 per trader and $300 total, and the fill is limited to the
  size offered at the best ask.
- When the leader sells, we close at the best bid. Otherwise positions settle on the result.

Fills are taker fills with the 7% fee. Every copy logs the leader's price, our fill, the slippage and the delay
to `data/copy_journal.jsonl`. **That log is what tells you whether copying works.**

```bash
cp copy_config.example.json copy_config.json   # put leaderboard nicknames in "traders"
```

```bash
COPY_TOKEN=change-me .venv/bin/python -m kalshibot copy serve --host 0.0.0.0
```

```bash
.venv/bin/python -m kalshibot copy status
```

Why copies can underperform the leader:
- Many top-P&L accounts are makers. Their fills come from resting orders, while you arrive late as a taker
  and pay the spread plus the fee.
- Bürgi, Deng & Whelan find takers lose about 32% on average and makers about 10%.
- Leaderboard rank is in-sample: past P&L, survivorship and size you can't match.

### Choosing traders: `kalshibot leaders`

`kalshibot leaders --refresh --write copy_config.json` downloads Rivo's Kalshi leaderboard and every listed
trader's page (kalshi.com blocks bots, and the API has no leaderboard). It then:
- takes Rivo's 90-day "$100 per bet" copy simulation;
- charges the taker fee and 2¢ of slippage;
- drops market makers, idle accounts, parlay-heavy accounts, one-win and one-month wonders, closers
  (95¢+ entries) and longshot-driven results;
- ranks the rest by t-stat and writes the top names into the copy config.

Current picks and why the biggest lifetime earners fail: [LEADERS.md](LEADERS.md).

Paper-copy for a few weeks, then keep only the traders whose *copied* P&L (not their own P&L) is positive.

**FOMO:** it's a social crypto trading app with feeds of followed traders, leaderboards and copy signals.
As of this writing I found no Kalshi or prediction-market integration. If you mean another FOMO product,
it can feed the same `/signal` endpoint.

## Strategy research summary

| Approach | Edge source | Feasible for a retail API bot? |
|---|---|---|
| Copy leaderboard traders (`copy`) | their information/skill | Yes via notifications/profiles; edge decays with delay and taker fees, so measure it |
| **Favorite-side maker (this bot)** | longshot bias + spread + maker fee advantage | **Yes**: slow, rules-based, low infra |
| Pure two-sided market making | spread capture | Partly: adverse selection on news; needs WebSocket, inventory control; Kalshi MM program terms are negotiated |
| News speed | react before the book | Hard: competing with low-latency bots on scheduled data (CPI, jobs, weather station feeds); co-location matters |
| Kalshi ↔ Polymarket arb | price gap on "same" event | Marginal: resolution-rule mismatch is the #1 risk (the two venues can grade the same event differently), capital locked on two venues, fees eat 2–3¢ gaps, US access to Polymarket is limited, profits concentrate in sub-second bots |
| Internal arb (YES+NO < $1, mutually exclusive ranges summing ≠ $1) | mispricing | Rare after fees, and fast bots take it first. Worth a scanner later |

Evidence for the bias (Bürgi, Deng & Whelan, *Makers and Takers: The Economics of the Kalshi Prediction Market*,
UCD WP2025_19 / CEPR DP20631):
- Contracts under 10¢ lose more than 60% for buyers.
- A 95¢ contract wins about 98% of the time.
- The average contract returns about −20% before fees.

**The risk is negative skew.** A 90¢ favorite that loses costs about 9 wins. The edge is a few cents per contract,
so position caps, per-event caps and fractional Kelly are not optional.

## How the bot works

1. `GET /markets?status=open` returns markets that close in 3h–10d. It drops multivariate parlays (`KXMVE*`) and
   markets with 24h volume under 200. It keeps markets whose mid puts one side in the 80–95¢ band.
2. `GET /markets/{t}/orderbook` gives the best bid and ask for the favorite side. Kalshi books are bids only:
   a YES ask is 1 − the best NO bid. The bot bids **one tick above the best bid** if the spread allows,
   otherwise it joins the bid. It never crosses.
3. **Model probability** = 1 − q × ratio(q), where q is the longshot price. `ratio` defaults to a haircut
   of the paper's numbers, and `calibrate` replaces it with your own measurement.
   `edge = p_model − bid − maker fee`. The bot quotes only if edge ≥ `min_edge` (1.5¢).
4. Size is 0.15 × Kelly, capped at $25 per market, $40 per event and $300 total, including resting bids.
5. **Paper fills** (conservative):
   - A print below our bid fills us.
   - A print at our bid by a taker selling our side first consumes the queue that was resting ahead of us
     when we posted, and only then fills us.
6. Each cycle requotes when the book moves (which resets the queue), cancels bids within 3h of close,
   and settles positions on `result` (any result other than yes/no refunds the cost).
   Everything is journaled to `data/paper_journal.jsonl`.

## Use

```bash
cd kalshi
```

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

```bash
cp config.example.json config.json
```

Read-only: print the bids it would place now (no key needed):

```bash
.venv/bin/python -m kalshibot scan
```

Measure the bias yourself before trusting the default table (60 days, price 24h before close):

```bash
.venv/bin/python -m kalshibot calibrate --days 60 --hours-before 24
```

Then set `"calibration_path": "data/calibration.json"` in `config.json`.

Paper trade (loop every 60s; `--once` runs a single cycle):

```bash
.venv/bin/python -m kalshibot paper
```

```bash
.venv/bin/python -m kalshibot status
```

Check your keys (authenticated, still read-only):

```bash
export KALSHI_API_KEY_ID=...
```

```bash
export KALSHI_PRIVATE_KEY_PATH=~/.kalshi/key.pem
```

```bash
.venv/bin/python -m kalshibot account
```

`KALSHI_ENV=demo` points at `demo-api.kalshi.co`. Run the tests with `.venv/bin/python -m pytest -q`.

## Before going live (not implemented on purpose)

1. Run `calibrate`. If the 80–95¢ buckets don't show positive `fav_edge_maker` after fees, stop.
2. Paper trade for 2–4 weeks and well over 100 settled positions. Compare realized win rate to `p_model` by bucket.
3. Check whether maker fees apply to the series you trade (`maker_fee_rate`; the 0.0175 default is conservative).
4. Live trading would need: `POST /portfolio/orders` with `post_only`, cancel and amend, a WebSocket order
   book instead of polling, reconciliation against `/portfolio/fills`, a kill switch and a daily loss limit.

## Known limits

- **Not tested live.** The cloud session that wrote this had no network route to Kalshi.
  Field names follow the current docs (`*_dollars`, `*_fp`, `orderbook_fp`) with legacy-cents fallbacks.
  Run `scan` first and check the output looks sane.
- Paper fills ignore cancel latency and hidden or iceberg size. The tape can't tell you queue position exactly.
- Positions are marked at cost until settlement, so there is no intraday mark-to-market.
- Calibration samples the most-traded market per event, which still leaves correlated events (for example,
  many games on one night). Treat small buckets with suspicion.
