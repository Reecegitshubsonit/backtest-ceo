# ETF strategy research: 5 strategies vs buy-and-hold SPY

Run: `python3 research/etf_strategies/backtest.py` (daily; add `--intraday` for the SPY 5-min test). Writes `results.md` and `results.csv`.

## Data and method (v2)
- **Source: Alpaca SIP, split and dividend adjusted.** Yahoo was requested but this environment's network policy blocks it (403).
  Alpaca history starts 2016-01-04: 2016 is indicator warm-up, scoring starts 2017-01-03. 12-1 month TSMOM has no signal until
  its first month end with 252 days of history (2017-01-31), so it sits in T-bills for January 2017.
- **Engine:** holdings drift with prices between rebalances. Signal at the close, trade at the next open. The 3 bp/side cost is
  taken from traded notional. v1 held constant weights every day, which amounted to free daily rebalancing. v2 fixes that.
- **Cash = T-bills:** any unallocated weight earns BIL's daily total return (net of its 0.14% fee) and costs nothing to move.
  BIL returned 2.4%/yr from 2017 to 2026 and 4.0%/yr over the last 2 years. Trend and rotation "off" states, and RSI(2) idle days, all sit in this cash.
- **Sharpe:** daily returns minus BIL, ×√252.
- **Trade counts:** *round trips* = a symbol goes flat→held→flat (positions still open at the end are listed separately).
  *Position changes* = entries + exits. Monthly resizes of a position that stays held are neither, but they are
  still charged costs and still appear in *fills*.
- **Longest DD:** calendar days from a peak to the day it is regained (or to the last date if never regained).
- **Vol-matched SPY:** SPY's excess return scaled by k = vol(strategy)/vol(SPY), rest in T-bills, rebalanced daily
  with no costs. Return = rf + k·(SPY − rf). This favours SPY a little because it trades for free.
- **Bootstrap:** 5000 circular-block resamples (21-day blocks) of the paired daily excess returns of strategy and SPY,
  95% percentile CI on Sharpe(strategy) − Sharpe(SPY).

## Strategies
1. **Trend, SPY 200d SMA:** 100% SPY while above its 200-day SMA, else cash. Checked daily.
2. **Trend, TSMOM:** equal 1/N slots. A slot is held if the 12-1 month return > 0 and price > 200d SMA, else cash. Monthly.
3. **Rotation, sectors:** SPDR sectors, top 3 by average 1/3/6-month return. A pick must beat BIL over 6 months, else its slot goes to cash. Monthly.
4. **Rotation, dual momentum:** best 6-month performer of SPY/QQQ/EFA/TLT/GLD if it beats BIL, else cash. Monthly.
5. **Mean reversion:** 5a SPY RSI(2) < 10 above its 200d SMA, exit when close > 5d SMA or after 10 days. 5b, the intraday
   VWAP reversion, was not rerun; it lost money net of costs over 42 sessions (see v1 commit).

## How the 10 TSMOM ETFs were chosen, and hindsight
I picked `SPY QQQ IWM EFA EEM TLT IEF GLD DBC VNQ` in 2026, aiming for one liquid ETF per major asset class.
No screen was run on returns. It is still not hindsight-free:
- Its core comes from the published GTAA-5 set (Faber 2007: US stocks, foreign stocks, bonds, REITs, commodities). That set
  is out-of-sample for 2017–2026.
- I **added QQQ, IWM, EEM, TLT and GLD by judgment, knowing their 2017–2026 history.** QQQ and GLD are the period's two big
  winners, and TLT's 2022 crash is one a trend filter sidesteps. That is the kind of choice hindsight biases.
- Survivorship: none of the 10 died, and all existed before 2016. The risk is in which ETFs I chose, not in delisted ETFs being dropped.

Robustness rerun of the best risk-adjusted strategy (TSMOM) on two lists chosen by rule:
- **Sector SPDRs listed before 2017-01-01** (XLB XLE XLF XLI XLK XLP XLU XLV XLY XLRE; XLC launched in 2018 and is excluded).
- **Faber 2007 GTAA-5** (SPY EFA IEF VNQ DBC), the list published ten years before the test window.

On rule-chosen lists the TSMOM Sharpe falls from 0.71 to 0.55 (2017–2026). Part of the original list's result was the list itself.

## Results, 2017-01-03 .. 2026-11-03
| Strategy | CAGR | Vol | Sharpe | Max DD | Longest DD (d) | Round trips | Pos. changes |
|---|---:|---:|---:|---:|---:|---:|---:|
| SPY buy & hold | 14.8% | 17.8% | 0.73 | -33.8% | 709 | 0 (+1 open) | 1 |
| 1. SPY 200d SMA / cash | 10.7% | 12.1% | 0.71 | -19.3% | 746 | 25 (+1) | 51 |
| 2. TSMOM, original 10 | 7.1% | 6.7% | 0.71 | -8.4% | 583 | 75 (+6) | 156 |
| 2r. TSMOM, sectors listed pre-2017 | 6.8% | 8.4% | 0.55 | -12.4% | 814 | 103 (+7) | 213 |
| 2r. TSMOM, GTAA-5 | 5.7% | 6.1% | 0.55 | -8.0% | 497 | 40 (+4) | 84 |
| 3. Top-3 sectors | 10.3% | 17.1% | 0.52 | -32.6% | 839 | 124 (+3) | 251 |
| 4. Dual momentum | 10.6% | 19.6% | 0.49 | -36.5% | 1968 | 33 (+1) | 67 |
| 5a. RSI(2) SPY | 4.7% | 6.2% | 0.39 | -12.1% | 1006 | 86 (+1) | 173 |

| vs SPY | Vol-matched SPY CAGR | Vol-matched SPY max DD | ΔSharpe | 95% CI |
|---|---:|---:|---:|---:|
| 1. SPY 200d SMA | 11.0% (strat 10.7%) | -23.9% (strat -19.3%) | -0.02 | [-0.44, +0.37] |
| 2. TSMOM, original 10 | 7.3% (7.1%) | -13.8% (-8.4%) | -0.02 | [-0.53, +0.44] |
| 2r. TSMOM, sectors pre-2017 | 8.5% (6.8%) | -17.0% (-12.4%) | -0.18 | [-0.62, +0.23] |
| 2r. TSMOM, GTAA-5 | 6.9% (5.7%) | -12.6% (-8.0%) | -0.18 | [-0.73, +0.32] |
| 3. Top-3 sectors | 14.3% (10.3%) | -32.6% (-32.6%) | -0.21 | [-0.58, +0.16] |
| 4. Dual momentum | 16.0% (10.6%) | -36.8% (-36.5%) | -0.24 | [-0.81, +0.28] |
| 5a. RSI(2) | 6.9% (4.7%) | -12.6% (-12.1%) | -0.34 | [-0.97, +0.28] |

## Results, last 2 years (2024-11-04 .. 2026-11-03)
| Strategy | CAGR | Vol | Sharpe | Max DD | Longest DD (d) | Round trips | Pos. changes |
|---|---:|---:|---:|---:|---:|---:|---:|
| SPY buy & hold | 16.3% | 16.5% | 0.76 | -18.8% | 127 | 0 (+1 open) | 1 |
| 1. SPY 200d SMA / cash | 11.8% | 11.7% | 0.68 | -10.2% | 175 | 3 (+1) | 7 |
| 2. TSMOM, original 10 | 11.1% | 8.8% | 0.80 | -6.9% | 112 | 18 (+6) | 42 |
| 2r. TSMOM, sectors pre-2017 | 8.0% | 8.0% | 0.51 | -8.9% | 290 | 23 (+7) | 53 |
| 2r. TSMOM, GTAA-5 | 9.4% | 7.2% | 0.75 | -8.0% | 129 | 9 (+4) | 22 |
| 3. Top-3 sectors | 12.1% | 13.8% | 0.62 | -14.8% | 208 | 24 (+3) | 51 |
| 4. Dual momentum | 18.0% | 23.6% | 0.66 | -25.8% | 278 | 6 (+1) | 13 |
| 5a. RSI(2) SPY | 10.4% | 5.4% | 1.14 | -4.1% | 182 | 22 (+1) | 45 |

| vs SPY | Vol-matched SPY CAGR | Vol-matched SPY max DD | ΔSharpe | 95% CI |
|---|---:|---:|---:|---:|
| 1. SPY 200d SMA | 12.8% (strat 11.8%) | -13.4% (strat -10.2%) | -0.08 | [-0.87, +0.61] |
| 2. TSMOM, original 10 | 10.7% (11.1%) | -10.1% (-6.9%) | +0.04 | [-0.93, +0.87] |
| 2r. TSMOM, sectors pre-2017 | 10.1% (8.0%) | -9.2% (-8.9%) | -0.25 | [-1.44, +0.77] |
| 2r. TSMOM, GTAA-5 | 9.5% (9.4%) | -8.2% (-8.0%) | -0.01 | [-0.99, +1.03] |
| 3. Top-3 sectors | 14.4% (12.1%) | -15.8% (-14.8%) | -0.14 | [-1.10, +0.80] |
| 4. Dual momentum | 21.0% (18.0%) | -26.1% (-25.8%) | -0.10 | [-1.86, +1.48] |
| 5a. RSI(2) | 8.1% (10.4%) | -6.1% (-4.1%) | +0.38 | [-1.07, +1.57] |

## Verdict
- **No strategy's edge over SPY can be told apart from noise.** Every 95% CI on ΔSharpe includes 0, in both windows.
  Over 2017–2026 most point estimates are negative. With seven strategy/universe tests, a single marginal result would
  also need a multiple-testing correction. None comes close to needing one.
- At equal volatility, SPY scaled down with T-bills matched or beat every strategy on CAGR over 2017–2026. The trend strategies
  (1 and 2) did keep a real **drawdown** advantage: -19% vs -24% and -8% vs -14% at matched vol. Their value is drawdown
  shape, not return. Two caveats: that is one sample with one big crash (2020) and one bear market (2022), and the
  advantage is roughly half as large on the rule-chosen lists.
- Rotation (3 and 4) and RSI(2) underperform vol-matched SPY over the full period. The last-2-years RSI(2) Sharpe of 1.14 rests on 22 round trips,
  and its CI is [-1.07, +1.57].
- v1 vs v2: v1 used a 0% risk-free rate, which inflated cash-heavy Sharpes (TSMOM 1.06 → 0.71). v1 also rebalanced daily for free.
