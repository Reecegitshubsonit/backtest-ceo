# Momentum parameter search: 124,416 combinations, 2016–2026

**Result: nothing survived.** All 10 finalists lost money on the holdout. White's Reality Check is not
significant, every finalist's deflated Sharpe is about 0, and the earlier Cameron version also loses on the same
holdout.

## Data

| Item | What was used |
|---|---|
| History | All Alpaca SIP 1-minute bars: 2,725 sessions from 2016-01-04 to 2026-11-03 |
| Universe | 33,043 symbols: headline symbols on every 5th session (19,713) plus every corporate-action symbol (31,435: splits, name changes, mergers, worthless removals) |
| Delisted symbols | **Included.** Alpaca serves their bars (checked on SIVB, BBBY, TWTR, FRC) |
| Survivorship gap | Alpaca's asset list (which includes delisted names) is blocked from this container. Measured on 2026, this universe contains **97.9%** of the gappers found with the full daily-news universe. Roughly 2% of names may be missing |
| Candidates | Each day: previous close $0.5–25 and 20-day ADV ≥50k (about 3,200 stocks). Kept if the regular-session high was ≥+10% (daily bar), **or** the premarket high was ≥+10% (hourly bars, scanned separately because Alpaca's daily bar is regular-session only). The premarket scan keeps runners that faded before the open, so premarket entries carry no survivorship bias |
| Bars | 1-minute bars, 04:00–12:00, for all candidates |
| News | Symbol-filtered headlines, previous day 16:00 to 12:00. "Stock-specific" excludes roundups, transcripts, halt notices and headlines tagging more than 2 tickers |
| Level 2 | **Not used. Alpaca has no Level 2 or order-book history**, only NBBO top-of-book quotes |
| Spreads | 1,313 random NBBO samples from candidate stock-minutes give the median spread by price × bar dollar volume × session. Typical values: 0.4–1.4% in regular hours, 0.5–2.1% in premarket |
| Cost per side | Half spread + 0.05% impact. Limit-order target exits pay no spread |

## Search

One event is a setup candle closing between 07:00 and 11:30, with the stock ≥+10% and $1–20 at that moment.
There are 222,545 events. Setup structure matches the round-1 engine:

- **Leg:** ≥4% to the high of day within 15 bars.
- **Pullback:** 1–5 bars, retracing at most 50% of the leg.
- **Patterns:** micro pullback (1 bar), bull flag (2–5 bars on lighter volume), or first pullback (the day's first
  qualifying leg).
- **Rules for every combination:** the first qualifying setup per symbol per day, at most 5 trades a day, a
  30-minute maximum hold, results in R.

The 124,416 combinations are every mix of:

| Parameter | Values |
|---|---|
| Gap | ≥10 / 20 / 40% |
| Relative volume (time-of-day adjusted) | ≥2 / 5 / 10 |
| Price | $1–10 / $2–20 / $5–20 |
| Catalyst | none / any headline / stock-specific |
| Pattern | micro / bull flag / first pullback / any |
| Candle confirmation | off (buy-stop at high +1¢) / on (buy the open after a strong close above the trigger) |
| Filters | VWAP on/off, close above 9 EMA on/off |
| Entry window | 07:00–09:30, 09:30–10:00, 09:30–10:30, 09:30–11:30 |
| Stop | pullback low (capped at 8%) / 2% / 4% |
| Target | 1R / 2R / 3R / trail the prior bar's low after +1R |

**Time split:**

| Split | Sessions | Dates |
|---|---:|---|
| Search (60%) | 1,635 | 2016-01-04 .. 2022-06-30 |
| Validate (20%) | 545 | .. 2024-08-30 |
| Holdout (20%) | 545 | .. 2026-11-03 |

The holdout was run once, on the top 10. Code: `hist.py` (data, resumable), `events.py` (numba precompute),
`search.py` (search, validation, statistics). Checkpoints are under `~/.cache/backtest-ceo/momentum/hist/`.

## Results

| | Real data | Shuffled #1 | Shuffled #2 |
|---|---:|---:|---:|
| Combinations with ≥200 search trades | 91,152 | 91,152 | 91,152 |
| Search Sharpe > 0 | **95 (0.10%)** | 6 | 11 |
| Best search Sharpe (annualized, R) | 0.31 | 0.21 | 0.10 |
| Median search Sharpe | −2.37 | −2.76 | −2.69 |
| Top 1,000 with validation Sharpe > 0 | 325 | 0 | 1 |
| White's Reality Check p (top 1,000, validation) | **0.43** | 1.00 | 1.00 |
| Survivors (validation > 0, neighbours pass) | 89 | 0 | 0 |

The shuffled benchmark moves trade outcomes randomly among the events of each day. The real data beats it: there
is less loss and some structure. But no strategy clears zero once the number of tries is accounted for.

**Holdout, top 10 survivors (run once):**

| # | Setup | Search SR | Validate SR | **Holdout SR** | Holdout trades | Holdout mean R |
|---|---|---:|---:|---:|---:|---:|
| 1 | confirm, bull flag, 09:30–11:30, $2–20, stock-specific, VWAP, EMA9, gap ≥40, RVOL ≥5, 4% stop, trail | −0.39 | 0.57 | **−1.64** | 131 | −0.25 |
| 2 | confirm, micro, 09:30–10:30, $5–20, any news, VWAP, gap ≥20, RVOL ≥2, 4% stop, trail | −0.33 | 0.57 | **−1.62** | 204 | −0.19 |
| 3 | same as 2 without VWAP | −0.33 | 0.57 | **−1.62** | 204 | −0.19 |
| 4 | confirm, bull flag, 09:30–10:30, $1–10, any news, gap ≥40, RVOL ≥5, 4% stop, trail | −0.28 | 0.57 | **−3.01** | 128 | −0.46 |
| 5 | same as 4, RVOL ≥2 | −0.31 | 0.57 | **−3.09** | 130 | −0.46 |
| 6 | confirm, micro, 09:30–11:30, $5–20, no catalyst, VWAP, EMA9, gap ≥40, RVOL ≥2, 4% stop, trail | −0.14 | 0.56 | **−2.24** | 134 | −0.35 |
| 7 | same as 6 without VWAP | −0.14 | 0.56 | **−2.24** | 134 | −0.35 |
| 8 | confirm, micro, 09:30–10:30, $5–20, any news, VWAP, EMA9, gap ≥20, RVOL ≥2, 4% stop, trail | −0.28 | 0.56 | **−1.75** | 199 | −0.20 |
| 9 | same as 8 without VWAP | −0.28 | 0.56 | **−1.75** | 199 | −0.20 |
| 10 | confirm, bull flag, 09:30–11:30, $2–20, stock-specific, VWAP, EMA9, gap ≥40, RVOL ≥2, 4% stop, trail | −0.31 | 0.55 | **−1.52** | 138 | −0.23 |

**Deflated Sharpe ratio** (search split, N = 124,416): **0.00** for all 10. The search-period Sharpe needed to
beat chance at that many tries is far above anything found.

**Earlier Cameron version** (round-1 engine and default rules, same holdout, same candidates):

| Slippage | Trades | Net ($100 risk) | PF | Win rate | Mean R | Daily Sharpe (R) |
|---|---:|---:|---:|---:|---:|---:|
| 0.2% per side (as built) | 1,464 | −$24,410 | 0.65 | 27% | −0.20 | −4.8 |
| 0.5% per side (closer to the spread model) | 1,393 | −$53,041 | 0.40 | 21% | −0.41 | −10.4 |

The searched variants lose less per day than the Cameron version (Sharpe −1.5 to −3 vs −4.8) because they trade
less. They lose about the same per trade (−0.2R to −0.46R). Neither has an edge.

## Protocol note (stated plainly)

- **Gate gap:** the survivor rule required validation Sharpe > 0 and the neighbour test, but not a positive
  search Sharpe. Because only 95 combinations were positive in search, the top-1,000 list was mostly negative in
  search, and the 10 finalists all were. A stricter gate (search > 0 and validation > 0) would have picked other
  finalists. Those can't be put on the holdout now without breaking the run-once rule. White's Reality Check
  (p = 0.43) and the deflated Sharpe (0 for all) say no choice from this search clears chance either way.
- **Duplicate rows:** several finalists are identical except for the VWAP flag. In those subsets almost every
  setup is already above VWAP.

## Conclusion

- **Long momentum:** over ten years of 1-minute data, with realistic spreads, no pullback-entry variant of the
  long small-cap momentum style has an edge that survives out of sample.
- **Consistent with earlier tests:** this matches every earlier test in this repo. The only thing that has held up
  is the short side (Gapper Fade, [FADE.md](FADE.md)), and that hasn't been run through this 10-year pipeline yet.
- **Paper trading:** unchanged.
