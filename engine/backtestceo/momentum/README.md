# Small-cap momentum (Cameron-style, no float)

Our own version of Ross Cameron's (Warrior Trading) small-cap momentum day-trading method: a gap / relative-volume /
news scanner, three pullback entries on 1-minute bars, and his exit and risk habits written as fixed rules.
There's a backtest on 60 sessions of Alpaca 1-minute SIP bars and a loop for the Alpaca **paper** account.

**Result: no edge found, in two independent 60-session periods (see 3b).** Over 60 sessions (2026-08-11 to 2026-11-03) the default rules lost $1,945 on $100 risk
per trade: 124 trades, 28% winners, profit factor 0.69, −0.19R a trade. It still loses with zero slippage. Out of
32 tuned variants, 8 were positive on the held-out half, and the mean out-of-sample result was −$229. Do not trade
it with real money as it stands.

## 1. What the method is (research summary)

Sources: Warrior Trading's own blog posts, video summaries and TradingView ports of the rules. These secondhand
sources mostly agree with each other, but Cameron doesn't publish one exact rulebook. Where sources differ, the
choice is noted.

| Topic | Cameron | This version |
|---|---|---|
| **Stock selection ("5 pillars")** | Up ≥10% on the day, relative volume ≥5×, a fresh news catalyst, price $2–20 (some sources say $1–20), float <10–20M | Same except float, which is ignored as asked. RVOL uses a 20-day ADV and is time-of-day adjusted (below) |
| **Catalyst** | Breaking, stock-specific news: earnings, FDA, contracts, offerings ending, mergers | An Alpaca/Benzinga headline tagged with the symbol, from the previous day's 16:00 ET up to the bar. Sector roundups, mover lists, transcripts, market-wide pieces and headlines tagging >2 tickers are dropped |
| **Time of day** | Scanners from ~7:00 ET, best trading 9:30–10:30, usually done by late morning | Scanner from 07:00, entries 09:30–11:00, flatten 11:30. Premarket entries can be switched on (`entry_from=07:00`) |
| **Bull flag** | Strong surge (pole), 2–3+ candles pulling back on lighter volume, buy the first candle that makes a new high, stop at the pullback low | Pullback of 2–5 bars after a leg of ≥4% to a new high of day; retrace ≤50% of the leg; pullback average volume below the leg's; buy-stop at the last candle's high + 1¢, stop at the pullback low − 1¢ |
| **Micro pullback** | In a fast move, a single small dip (red candle or lower wick), then buy the break of that candle's high | 1-bar pullback, same leg/HOD/retrace rules, no volume condition |
| **First pullback** | The first pullback after the initial news squeeze is the highest-probability one | The pullback of the first leg high made after the symbol entered the scanner. This label takes precedence over the other two |
| **Confirmation** | MACD positive ("open"), above VWAP, above 9 EMA; avoid when MACD is negative | MACD(12,26,9) line > 0 and close > VWAP (VWAP from 04:00, premarket included) |
| **Exits** | Sell half into strength or at a 2:1 target, stop to breakeven, out on the first candle making a new low, topping tails / shooting stars, MACD crossing down, "breakout or bailout" | Sell 50% at 2R, stop to breakeven; then trail the prior candle's low, exit on a MACD bearish cross, exit at the close of a topping-tail candle at high of day (any time in profit); bailout if not above entry after 5 bars |
| **Risk** | Fixed max loss per trade, 2:1 profit:loss, daily max loss, size down when cold, stop after a few losers, avoid wide stops | $100 risk per trade, daily max loss $300 (3R), half size after a loser until a winner, stop after 3 losers in a row, max 10 trades a day, max 2 entries per symbol, one position at a time, skip stops wider than 5% |

Not modelled: float, Level 2 / time & sales, 10-second charts, halts (bars just stop), short-sale restrictions,
borrow, hot keys. Cameron leans on tape reading and sub-minute charts, and none of that can be reproduced from
1-minute bars.

**Relative volume.** RVOL = volume since 04:00 ÷ (20-day ADV × expected share of the day by now). The expected
share is `max(30, minutes since 09:30) / 390`, capped at 1. So at 09:30 a 5× stock has already traded about 38% of
its average day in premarket.

## 2. Code

`engine/backtestceo/momentum/`

| File | What |
|---|---|
| `config.py` | Every rule as a field of a frozen `Config`; override any field with `--set key=value` |
| `engine.py` | Shared by the backtest and the paper loop: EMA/VWAP/MACD, RVOL, scanner, setup detection, sizing, exits, fill simulation |
| `data.py` | Alpaca data (news, daily, 1-min, snapshots, movers) with a disk cache in `~/.cache/backtest-ceo/momentum` |
| `backtest.py` | Universe, minute-by-minute day simulation, stats, sweep variants |
| `walkforward.py` | Grid of 32 variants: tuned on the first 30 sessions, scored on the last 30 |
| `paper.py` | Alpaca paper trading loop + dry-run broker |
| `../../tests/test_momentum.py` | Unit tests for the engine and the paper flow |

### Backtest method

1. **Universe.** Pull every headline from the previous day's 16:00 ET to 11:30 ET for each session. The news
   symbols are the universe, since a catalyst is required anyway. Drop warrants, units and rights.
2. **Daily data.** Raw and split-adjusted daily bars give the previous close and ADV in day-D share units, so a
   reverse split doesn't show up as a fake gap.
3. **Download prefilter.** Day D's daily high must be ≥ previous close +10%, and the day must touch the $2–20
   band. These are necessary conditions, used only to avoid downloading 1-minute bars that couldn't qualify. All
   qualification happens minute by minute with no lookahead. This holds for regular-hours entries. For premarket
   entries it can miss a premarket-only runner.
4. **Scanner, every minute.** A symbol enters play the first minute it meets price, gap, RVOL and catalyst. It
   stays in play for the day, but each setup re-checks price band, gap, VWAP and MACD.
5. **Setups and entries.** Setups are computed at a bar's close and are good for the next bar only, as a buy
   stop-limit (limit = trigger + 0.5%). Fill price = max(open, trigger) + slippage, never above the limit.
6. **Fill assumptions.** Slippage is 0.2% per side (min 1¢). Stops fill at min(open, stop) − slippage. A stop on
   the entry bar wins over the target. A red bar that hits target then breakeven exits at breakeven. Bar-close
   exits fill at close − slippage.
7. **Size.** Size = $100 ÷ (trigger − stop), capped by $25k notional and by 10% of the average 1-minute volume
   of the last 5 bars.

```bash
cd engine
python3 -m backtestceo.momentum backtest --days 60                       # writes docs/momentum-backtest/
python3 -m backtestceo.momentum backtest --days 60 --set min_gap_pct=20 patterns=first_pullback
python3 -m backtestceo.momentum sweep --days 60                          # docs/momentum-backtest/sweep.md
python3 -m backtestceo.momentum.walkforward
python3 -m pytest -q tests/test_momentum.py
```

The first run downloads about 63k headlines, daily bars for ~8.9k symbols and ~1.3k symbol-days of 1-minute bars
(about 7 minutes). Later runs are cached.

## 3. Results (60 sessions, 2026-08-11 to 2026-11-03, SIP 1-minute bars)

Default config, `docs/momentum-backtest/` (`trades.csv`, `scanner_hits.csv`, `summary.json`):

| | |
|---|---|
| Trades / days traded / green days | 124 / 46 / 16 |
| Net P&L ($100 risk/trade, $25k account) | **−$1,945** (−7.8%) |
| Win rate · avg win · avg loss | 28.2% · $122 · −$70 |
| Profit factor · avg R · max drawdown | 0.69 · −0.19R · −$1,988 |
| Days halted by the risk rules | 12 |

| Pattern | Trades | P&L | Win rate | Avg R |
|---|---:|---:|---:|---:|
| first pullback | 57 | −$541 | 30% | −0.11 |
| micro pullback | 24 | −$232 | 33% | −0.06 |
| bull flag | 43 | −$1,172 | 23% | −0.36 |

| Entry time (ET) | Trades | P&L | Win rate |
|---|---:|---:|---:|
| 09:30–10:00 | 75 | −$1,389 | 25% |
| 10:00–10:30 | 31 | +$34 | 39% |
| 10:30–11:00 | 18 | −$591 | 22% |
| 07:00–09:30 (when premarket is on) | | see sweep: worse overall | |

By exit: hard stops (54) lost $4,738 and bailouts (35) lost $1,461. Topping-tail exits (15, +$1,795) and trailing
stops after the partial (20, +$2,459) made money. The winners behave the way the method intends, but at 1-minute
resolution there are too many full-size stop-outs.

**The catalyst filter matters.** Counting sector-roundup headlines as news gave 160 trades and −$3,393 (PF 0.57).
The stock-specific filter gave 124 trades and −$1,945 (PF 0.69).

**Sensitivity** (`sweep.md`, one change at a time from the default; every row loses):

| Variant | Trades | Net P&L | PF |
|---|---:|---:|---:|
| default | 124 | −1,945 | 0.69 |
| premarket entries from 07:00 | 162 | −3,423 | 0.60 |
| first pullback only | 62 | −744 | 0.75 |
| gap ≥ 20% | 92 | −797 | 0.82 |
| RVOL ≥ 10 | 102 | −1,007 | 0.79 |
| slippage 0% | 124 | −1,215 | 0.78 |
| slippage 0.5%/side | 119 | −4,237 | 0.43 |
| target 3R | 116 | −1,909 | 0.68 |
| no bailout exit | 114 | −1,914 | 0.72 |

**Walk-forward** (`walkforward.txt`): a 2×2×2×2×2 grid over gap, RVOL, patterns, bailout and entry cutoff. The
best variant on sessions 1–30 (gap ≥20%, first pullback only) made +$30 in-sample and +$160 out-of-sample, on
about 20 trades per half, which is noise. 8 of 32 variants were positive out of sample, and the mean was −$229.
Stricter selection (bigger gaps, higher RVOL, first pullback only) loses less, which matches Cameron's emphasis on
the strongest stock of the day. The sample is too small to call that an edge.

**Caveats.** Fills on 1-minute bars of thin small caps are approximate. Spreads can be wider than 0.2%. Halts
aren't modelled. Alpaca's news feed is Benzinga, which is not the same as the scanners and feeds Cameron uses.

## 3b. Round 2: fixes tried, then a true holdout

**Diagnosis of the default run.**
- 42% of trades never reached +0.5R before stopping out.
- 15% stopped out on the entry candle itself (false breakouts).
- The median stop is only 2% wide, so 0.4% round-trip slippage costs about 0.2R a trade.

**Changes added** (all are options; defaults unchanged):

| Option | What |
|---|---|
| `entry_confirm_close=true` | Buy at the next open only after a candle *closes* above the trigger, in the top half of its range |
| `bar_minutes=5` | Run setups and exits on 5-minute candles (backtest only) |
| `leader_only=true` | Only trade the stock that's up the most right now (Cameron trades the leading gainer) |
| `require_above_ema9=true` | Setup candle must close above the 9 EMA |
| (always on) | Halt / resume / circuit-breaker headlines are no longer counted as catalysts |

**Method.** All tuning used the 60 sessions 2026-08-11..11-03 (dev). Two candidates were then fixed in advance,
along with the plain fixes, and each was run once on the 60 sessions before that, 2026-05-14..08-10 (holdout).

| Config | Dev trades | Dev P&L | Dev PF | Holdout trades | Holdout P&L | Holdout PF |
|---|---:|---:|---:|---:|---:|---:|
| default (stop entry, 1m) | 123 | −1,891 | 0.69 | 147 | −1,755 | 0.73 |
| close-confirm, 1m | 75 | −801 | 0.74 | 96 | −1,590 | 0.56 |
| close-confirm, 5m | 31 | −93 | 0.92 | 55 | −871 | 0.63 |
| A: close-confirm 1m, gap ≥20%, RVOL ≥10 | 40 | −256 | 0.83 | 40 | −922 | 0.52 |
| B: close-confirm 5m, gap ≥20%, RVOL ≥10 | 13 | **+466** | **2.59** | 20 | **−796** | **0.27** |

Other dev-only variants (leader only, 9 EMA, no bailout, target 1.5R/3R, smaller partial, no topping-tail or MACD
exit, $2–10, time windows) also all came in between −$1,300 and +$80.

**Takeaway.** Candidate B looked like a winner on dev and lost on unseen data. That's the curve-fitting trap: with
13–40 trades, any "profitable" setting found by search is mostly luck. Close-confirmation and 5-minute candles cut
losses in both periods, but nothing tested is profitable out of sample. Long pullback entries on 1- and 5-minute
bars of news gappers, without Cameron's tape reading and sub-minute timing, show no edge in 120 sessions of 2026
data.

Reproduce:

```bash
python3 -m backtestceo.momentum backtest --days 60 --set entry_confirm_close=true bar_minutes=5 min_gap_pct=20 min_rvol=10
python3 -m backtestceo.momentum backtest --days 60 --end 2026-08-10 --set entry_confirm_close=true bar_minutes=5 min_gap_pct=20 min_rvol=10 --out /tmp/holdout
```

## 4. Alpaca paper trading

```bash
cd engine
python3 -m backtestceo.momentum scan                  # one scanner pass, read-only
python3 -m backtestceo.momentum paper                 # dry run: logs the orders it would send
python3 -m backtestceo.momentum paper --live          # orders to the Alpaca PAPER account
python3 -m backtestceo.momentum paper --live --set entry_until=10:30 risk_per_trade=50
```

Start it before 07:00 ET (or any time in the morning). It exits after `flatten_at` once flat. Keys and flags come
from the environment or the repo `.env` (read by name only, never logged):

```
ALPACA_PAPER_API_KEY=...          # or ALPACA_API_KEY / APCA_API_KEY_ID
ALPACA_PAPER_SECRET_KEY=...       # or ALPACA_SECRET_KEY / APCA_API_SECRET_KEY
ALPACA_PAPER_TRADING_ONLY=true    # required for --live
ALPACA_DATA_FEED=sip              # needs a real-time SIP subscription; otherwise iex (default)
```

Each minute, 3 s after the bar closes, the loop does this:

1. Pulls new headlines (catalyst-filtered).
2. Takes snapshots of the news symbols and keeps those in the band and up ≥10%.
3. Rebuilds today's 1-minute bars from 04:00 and replays them through the same `SymbolState` the backtest uses.
4. Cancels last minute's unfilled entry, then, if a setup is armed and the risk rules allow, sends a **buy
   stop-limit** (day TIF).

After a fill:

- A **sell stop** goes in at the pullback low.
- The 2R partial is taken by polling the latest trade every 3 s; the stop then moves to breakeven.
- The trail, topping-tail, MACD-cross, bailout and 11:30 flatten exits run at bar close. They cancel the stop and
  sell at market.
- Trades are logged to `~/.cache/backtest-ceo/momentum/paper/` (`paper.log`, `trades-YYYY-MM-DD.jsonl`).

Safety:

- The order host is hard-wired to `paper-api.alpaca.markets`, and the existing `backtestceo.paper.safety` checks
  run before every request.
- `--live` refuses to start without `ALPACA_PAPER_TRADING_ONLY=true` or if any Alpaca base-URL variable points
  elsewhere.
- The kill switch is `PAPER_TRADING_KILL_SWITCH=1` (re-read from `.env`) or a `KILL` file in the state dir.

Limitations:

- `bar_minutes` must be 1 (5-minute mode is backtest-only); `entry_confirm_close=true` works (limit buy after the confirming close).
- Entries are regular-hours only, because Alpaca rejects stop orders in extended hours. The premarket variant
  backtested worse anyway.
- On the free IEX feed, volume is a few percent of the tape, so RVOL is computed against IEX daily volume. That
  keeps the ratio consistent but noisier. For scanning that matches the backtest, use SIP.
- Live partials are market orders, which fill a little worse than the backtest's limit fills.
- State is in memory: restarting mid-trade leaves the broker's stop order in place, but the loop won't manage that
  position.
- Not tested against the paper API from the build container, because order hosts were blocked there. The dry-run
  broker and `tests/test_momentum.py::test_paper_trader_dry_run_flow` cover the order flow.
