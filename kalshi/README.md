# kalshibot: favorite-longshot maker bot (read-only + paper)

Rests post-only **bids on the favorite side** (80–95¢) of liquid Kalshi markets and holds to settlement.
That captures the documented favorite-longshot bias as a **maker** (lower or zero fee, earns the spread)
instead of a taker. **This code places no real orders**: the client implements only GET requests, and paper mode
simulates fills against Kalshi's public trade tape.

## Can you copy top Kalshi traders? No, not reliably.

- **The public trade tape is anonymous.** `GET /markets/trades` returns price, size, taker side and time.
  It has no user, account or handle field, so you can't attribute any print to a trader.
- **There's no official API for other users' positions.** Your own fills and positions (`/portfolio/*`) need your key.
  Nothing in the documented API returns another account's positions.
- **Profiles and the leaderboard are opt-in website features.** Third-party scrapers read them by nickname.
  That's undocumented, fragile and probably against the ToS, and you only see traders who chose to be visible.
- **The edge doesn't transfer.** Top P&L accounts are largely makers and fast or informed traders.
  If you copy them, you are a delayed taker paying the spread plus the 7% × P × (1−P) taker fee on stale prices.
  Bürgi, Deng & Whelan find takers lose about 32% on average and makers about 10%.

So the alternative is to do what the profitable side does structurally: **be a maker and lean against the
longshot bias.**

## Strategy research summary

| Approach | Edge source | Feasible for a retail API bot? |
|---|---|---|
| Copy top traders | their information | No (see above) |
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
