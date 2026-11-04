# Gapper Fade

This strategy uses Cameron's scanner, simplified (gap %, relative volume, $2–20; no news, no float), but trades the
other side of it: **short the biggest gappers after the first five minutes and cover at the close.**

The momentum long strategy in [README.md](README.md) lost money in every version tested. While trying to fix it,
the reason showed up in the data: these stocks fade after the open. The fade is the edge, and buying breakouts
fights it.

## Rule

The rule was fixed before the out-of-sample test. Nothing below was tuned on Feb–May.

| | |
|---|---|
| Scan at 09:35 ET | Gap at the 09:30 open ≥ **30%** vs the previous close, open price **$2–20**, relative volume **≥2×** by 09:34 (20-day ADV, time-of-day adjusted) |
| Rank | Biggest gap first, at most **5** a day |
| Entry | **Short at the 09:35 open**, equal dollars: **$1,000** per position ($5,000 max gross short) |
| Stop | Buy-stop **+50%** above entry. This is a disaster stop for squeezes; the fill is the worse of the stop and the bar's open |
| Exit | **Cover at 15:55** |
| Costs | 0.2% slippage per side (min 1¢); sensitivity runs at 0.5% and 1% below |

## How it was found

1. **Long breakouts on gappers lose.** The pullback entries in [README.md](README.md) lost in every version. A
   wider no-news search (`gappers.py`) tried 1,440 long configs: opening-range breakouts on the first 5, 15 or 30
   minutes, premarket-high breakouts and high-of-day breakouts, crossed with gap, RVOL, stop, exit and time
   settings. It found **0 configs positive in all four half-periods** of Aug–Nov and May–Aug. Every family averaged
   −0.5R to −0.8R a trade in both periods.
2. **Why.** Gappers drift down after the open, and the bigger the gap, the bigger the drift. These numbers are from
   09:35 to the close, $2–20, RVOL ≥2:

   | Gap at open | Aug–Nov: mean / median, share closing lower | May–Aug |
   |---|---|---|
   | ≥10% | −2.4% / −2.0%, 61% | −1.8% / −1.5%, 57% |
   | ≥20% | −5.0% / −6.2%, 70% | −3.3% / −5.3%, 63% |
   | ≥40% | −9.7% / −11.5%, 80% | −8.1% / −11.7%, 72% |

3. **Tight stops don't work.** Shorts with stops 5–10% above entry, or just above the high of day, got squeezed
   out: only 48 of 528 short configs were positive. These stocks routinely swing 10–30% intraday before fading.
   Equal-dollar positions with a wide disaster stop capture the drift instead.
4. **The fixed rule was then run once on a fresh period**, Feb–May 2026, which was downloaded only after the
   rule was set.

## Results

`python -m backtestceo.momentum.fade backtest --end <date>`. Trades are in `docs/fade-backtest/`.

| Period (60 sessions each) | Trades | Net P&L | Win rate | Profit factor | Green days | Max drawdown | Worst day | Stops hit |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **Feb 18 – May 13 2026 (fresh, untouched)** | 90 | **+$5,724** | 62% | 2.39 | 35/48 | −$504 | −$504 | 4 |
| May 14 – Aug 10 2026 | 191 | +$8,654 | 66% | 1.46 | 39/59 | −$1,610 | −$1,018 | 32 |
| Aug 11 – Nov 3 2026 | 133 | +$3,931 | 64% | 1.37 | 35/54 | −$1,679 | −$1,008 | 15 |

- **Average trade** is +6.4%, +4.6% and +3.0% of the position across the three periods. The median trade is
  +5.7% to +8.9%.
- **All six half-periods are positive:** +$2,022 / +$3,702, +$4,299 / +$4,355, +$2,553 / +$1,378.
- **Total over 180 sessions** is +$18,309 on at most $5,000 short at a time.

**Sensitivity** (`docs/fade-backtest/sensitivity.md`): all 39 cells (13 variants × 3 periods) are positive.

| Variant | Feb–May | May–Aug | Aug–Nov |
|---|---|---|---|
| rule as fixed | $5,724, PF 2.39 | $8,654, PF 1.46 | $3,931, PF 1.37 |
| slippage 1%/side | $4,572, PF 1.99 | $6,078, PF 1.30 | $2,208, PF 1.19 |
| gap ≥20% | $5,699, PF 1.70 | $6,389, PF 1.28 | $3,803, PF 1.24 |
| gap ≥40% | $3,880, PF 2.52 | $9,723, PF 1.66 | $4,569, PF 1.65 |
| stop +25% | $4,734, PF 2.01 | $4,884, PF 1.28 | $2,663, PF 1.26 |
| entry 10:00 | $1,619, PF 1.28 | $9,140, PF 1.63 | $253, PF 1.03 |
| cover 12:00 | $6,481, PF 3.52 | $6,018, PF 1.40 | $5,008, PF 1.67 |

Entering later (10:00) is the weakest variant. Most of the fade happens in the first half hour.

## Risks the backtest can't capture

- **Borrow.** This is the big one. Alpaca only lets you short **easy-to-borrow** stocks, and many +30% small-cap
  gappers are hard to borrow. The backtest assumes every name could be shorted. The paper trader checks
  `shortable` and `easy_to_borrow` for each stock and skips the rest, so live results will differ, possibly a
  lot. Run it on paper for several weeks before trusting the numbers. Brokers with locates can short HTB names,
  but locate fees on these can be large.
- **Squeezes and halts.** A short can lose more than the 50% stop when a stock halts up and reopens far above it.
  The worst backtest trade was −67% of the position. Keep positions small: $1,000 on a $25k account.
- **Fills at 09:35.** Spreads on these names are wide at the open. Slippage of 1% per side still left every
  period positive.
- **One year, one regime.** All three periods are in 2026. Small-cap behaviour changes with market regimes.
- **Bars, not quotes.** Fills come from 1-minute bar opens and closes, not the order book.
- **Margin.** Shorting stocks under $5 carries higher margin requirements. Gross short tops out at $5,000.

## Alpaca paper trading

```bash
cd engine
python3 -m backtestceo.momentum.fade paper              # dry run: logs the shorts it would place
python3 -m backtestceo.momentum.fade paper --live       # Alpaca PAPER account only
python3 -m backtestceo.momentum.fade paper --live --set notional=500 max_positions=3
```

Start it before 09:35 ET and leave it running until after 15:55. The keys, `.env`, kill switch and paper-only
checks are the same as the momentum loop ([README.md](README.md), section 4); `--live` needs
`ALPACA_PAPER_TRADING_ONLY=true`.

At 09:35 it does this:

1. Scans Alpaca's top gainers and most-actives.
2. Takes snapshots and keeps stocks whose open gap is ≥30%, open is $2–20, and RVOL ≥2.
3. Ranks by gap and checks each stock's asset record. It skips anything that isn't shortable or easy to borrow.
4. Market-sells up to 5 positions at $1,000 each.
5. Puts a buy-stop 50% above each fill.

At 15:55 it cancels the stops and buys to cover at market.

The only live entry window is 09:35–09:40. If you start it after that, it won't enter that day.

**Live universe differs from the backtest.** Live candidates come from Alpaca's movers and most-actives lists (top
50 gainers, top 100 by volume). The backtest universe was every symbol in the news feed, so the two pick from
slightly different sets.

**Data feed.** On the free IEX feed the snapshot volume is a slice of the tape, so RVOL is noisier. Use
`ALPACA_DATA_FEED=sip` if your Alpaca account has a SIP subscription.

## Files

| File | What |
|---|---|
| `fade.py` | Rule, portfolio backtest, stats, paper trader |
| `gappers.py` | No-news gapper universe, full-day 1-min data cache, long/short search grids |
| `../../tests/test_fade.py`, `../../tests/test_gappers.py` | Tests |
| `docs/fade-backtest/` | Trades per period, sensitivity table |
