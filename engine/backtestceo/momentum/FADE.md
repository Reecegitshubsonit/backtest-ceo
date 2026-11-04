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

## Premarket (where Cameron does much of his trading)

`premarket.py` builds its universe from premarket bars, so there's no regular-session lookahead. For each session
it pulls 04:00–09:29 bars for every symbol whose previous close is $1.50–25 with ADV ≥50k (about 2,200 a day).
Any stock that trades ≥10% above the previous close in premarket is kept, including runners that collapse before
the open. That gives 50–70 a day and 2,400–3,000 symbol-days per period.

**Premarket momentum doesn't carry.** Buy the first 07:00–09:15 bar that's up ≥ G% with premarket volume
≥0.2× ADV (Aug–Nov):

| Up in premarket | To 09:29, mean / median | Share higher at 09:29 | To 09:45, median |
|---|---|---|---|
| ≥10% | −3.1% / −2.3% | 37% | −4.4% |
| ≥20% | −4.6% / −4.0% | 33% | −7.4% |
| ≥40% | −7.9% / −8.6% | 28% | −10.7% |

**Premarket long setups lose.** The grid has 486 configs per period:

- **Entries:** break of the premarket high of day, 1–3 bar pullback above VWAP, or the first push.
- **Filters:** up ≥10/20/40%, premarket volume ≥0.05/0.2/0.5× ADV.
- **Stops:** recent 5-bar low or −5%.
- **Exits:** 2R target, trail after +1R, or time exit at 09:29 or 09:45.
- **Windows:** entries 07:00 or 08:00 to 09:15.
- **Costs:** 0.5% slippage per side.

| Period | Positive configs | Positive in both halves | Best config | At 0% slippage: positive / both halves |
|---|---:|---:|---:|---:|
| Feb–May | 1 / 486 | 0 | +$1,011 | 3 / 0 |
| May–Aug | 23 / 486 | 0 | +$731 | 72 / 5 |
| Aug–Nov | 0 / 486 | 0 | −$23 | 13 / 0 |

**Premarket fade.** The rule was fixed after seeing the Aug–Nov drift, then run unchanged on the other two periods:

- **Scan:** the first 07:00–09:15 bar that closes ≥30% above the previous close, $2–20, premarket volume
  ≥0.1× ADV.
- **Entry:** short the next bar's open, with 0.5% premarket slippage.
- **Stop and exit:** disaster stop +50%, cover at 15:55.
- **Size:** $1k each, max 5 a day.

| Period | Trades | Net | PF | Win rate | Green days | Max DD | Stops | Same period, 09:35 fade |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| Feb–May | 197 | +$9,689 | 1.56 | 66% | 38/57 | −$1,343 | 26 | +$5,724, PF 2.39, DD −$504 |
| May–Aug | 246 | +$4,118 | 1.13 | 60% | 31/59 | **−$6,038** | 56 | +$8,654, PF 1.46, DD −$1,610 |
| Aug–Nov | 205 | +$14,452 | 1.74 | 67% | 39/59 | −$2,644 | 31 | +$3,931, PF 1.37, DD −$1,679 |

- **Total:** the premarket fade made more over 180 sessions (+$28.3k vs +$18.3k) and all six half-periods are
  positive.
- **Rougher ride:** in May–Aug it had a −$6k drawdown and twice as many squeeze stops. Its gap ≥20% variant lost
  money there (−$2,155), while every 09:35 fade variant was positive in every period.
- **Same stocks:** the two fades mostly short the same names, so running both doubles the exposure.
- **Order limits:** in extended hours, Alpaca takes limit orders only. Stop orders aren't accepted outside
  regular hours, so the stop would have to be watched in software. Short selling in premarket also needs
  easy-to-borrow shares.

**Verdict.** The 09:35 fade is the main strategy: steadier, regular hours, and a real broker-side stop. The
premarket fade earns more but has deeper drawdowns. It isn't in the paper trader yet.

Data and trades: `docs/premarket-backtest/`.

```bash
python3 -m backtestceo.momentum.premarket prepare --end 2026-11-03   # ~10 min per period, cached
python3 -m backtestceo.momentum.premarket drift   --end 2026-11-03
python3 -m backtestceo.momentum.premarket search  --end 2026-11-03   # the 486 long configs
```

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
| `premarket.py` | Premarket-runner universe, premarket long grid, premarket fade |
| `../../tests/test_fade.py`, `../../tests/test_gappers.py` | Tests |
| `docs/fade-backtest/` | Trades per period, sensitivity table |
