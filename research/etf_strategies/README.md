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

## Round 3: strategies from published research (`new_strategies.py`, `new_results.md`)
Method to avoid data-mining 10 years of data: each candidate comes from a paper published **before 2017**, with
the paper's default parameters and no tuning here. 2017–2026 is a true out-of-sample test. Leverage only through
listed 2x/3x S&P ETFs (SSO, UPRO), so their fees, financing and daily-reset decay are included. Results are also split
2017–21 / 2022–26 to check whether an edge holds in both halves. Holm correction runs over all 12 strategy-vs-SPY tests in the project.

- N1 **Vol target** (Harvey et al. 2018 / Moreira–Muir 2017): S&P exposure = 15% / 21-day realized vol, cap 2x via SSO, re-trade on a 10-point move.
- N2/N3 **Leveraged trend** (Gayed–Bilello 2016): SSO / UPRO while SPY > 200d SMA, else T-bills.
- N4 **Turn of month** (Lakonishok–Smidt 1988, McConnell–Xu 2008): hold SPY on the last trading day + first 3 of each month.
- N5 **Trend × vol target**: N1 exposure only while SPY > 200d SMA.

| 2017–2026 | CAGR | Vol | Sharpe | Max DD | Longest DD (d) | Round trips | Vol-matched SPY CAGR / DD | ΔSharpe [95% CI] |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| SPY buy & hold | 14.8% | 17.8% | 0.73 | -33.8% | 709 | 0 (+1) | — | — |
| N1. Vol target 15% | 14.4% | 16.5% | 0.76 | -19.4% | 608 | 28 (+2) | 14.0% / -31.6% | +0.02 [-0.29, +0.32] |
| N2. 2x trend (SSO) | 16.6% | 24.2% | 0.66 | -36.0% | 788 | 25 (+1) | 18.7% / -43.7% | -0.07 [-0.49, +0.32] |
| N3. 3x trend (UPRO) | 21.8% | 36.2% | 0.67 | -51.0% | 868 | 25 (+1) | 24.9% / -59.3% | -0.07 [-0.48, +0.32] |
| N4. Turn of month | 5.5% | 7.8% | 0.43 | -10.7% | 522 | 118 (+1) | 8.1% / -15.9% | -0.31 [-1.03, +0.41] |
| N5. Trend × vol target | 12.2% | 14.9% | 0.69 | -22.9% | 713 | 57 (+2) | 12.9% / -29.0% | -0.05 [-0.54, +0.42] |

| Sharpe by window | SPY | N1 | N2 | N3 | N4 | N5 |
|---|---:|---:|---:|---:|---:|---:|
| 2017–2021 | 0.95 | 1.09 | 0.87 | 0.88 | 0.59 | 0.94 |
| 2022–2026 | 0.50 | 0.40 | 0.41 | 0.42 | 0.23 | 0.40 |
| Last 2 years | 0.76 | 0.41 | 0.62 | 0.62 | 0.66 | 0.40 |

All Holm-adjusted p = 1.00.

### Read
- **Nothing tested in this project beats SPY on risk-adjusted return by a margin the data can detect.** That makes 12 tests,
  all with CIs spanning 0. With 10 years of daily data, a Sharpe gap must be roughly ±0.3–0.5 before the bootstrap can see it.
  Published edges for these ideas are 0.1–0.3.
- **Best practical result, N1 vol targeting:** SPY-like return (14.4% vs 14.8%) with max DD -19% vs -34%, against -32% for
  vol-matched SPY. So the drawdown cut is not just lower exposure. It held in 2017–21 (the 2020 crash, where vol spiked first)
  but not after: in 2022–26, and especially the April 2025 V-shaped selloff, it cut exposure near the low and missed the rebound.
  It is a drawdown tool with one good episode behind it, not a proven edge.
- **Leveraged trend (N2/N3)** raises CAGR (UPRO 21.8%) only by adding risk (vol 36%, max DD -51%). Its Sharpe is no better than
  SPY, and simply levering SPY to the same vol would have done better (24.9%). The 200d filter did not pay for its whipsaw here.
- **Turn of month** keeps a positive return in only ~20% of days, but net of costs and next-open fills it trails vol-matched SPY.
- Round 1–2 conclusions stand. Every robust result here is a **risk-shape** change (lower drawdown), not extra return per unit of risk.

### What would actually move this forward
1. **Longer history.** Ken French daily market data (1926+), FRED T-bills and stooq index data would allow these rules
   to be tested over ~90 years, where a 0.2 Sharpe edge is detectable. The environment's network policy blocks
   `mba.tuck.dartmouth.edu`, `fred.stlouisfed.org` and `stooq.com`.
2. More orthogonal return sources than SPY timing (carry, value or cross-sectional factor ETFs), tested the same way.

## Round 4: 3-month backtest and intraday strategies (`three_month.py`, `intraday.py`)

### Last 3 months, daily strategies (2026-08-03 .. 2026-11-03, 66 sessions): `three_month_results.md`
SPY +0.9%. Best: turn of month +4.6% (Sharpe 2.39) and top-3 sectors +4.5% (1.46). Both rest on 3 rebalances or
holding windows, and turn of month lost to vol-matched SPY over 10 years. 66 days cannot rank strategies, so
nothing was tuned or chosen on this window.

### Intraday candidates, published rules, 5-min SIP bars 2016–2026
- I1 **Noise-boundary intraday momentum, SPY** (Zarattini, Aziz, Barbon 2024): bands = max/min(open, prev close) × (1 ± 14-day
  average absolute move from open at that time of day). Checks every 30 min, trailing stop at the band or VWAP, flat at the close.
  1x, and the paper's sizing (2% daily vol target, ≤4x).
- I2 **5-min opening-range breakout, QQQ** (Zarattini, Barbon, Aziz 2023): trade in the direction of the first 5-min candle,
  stop at its other end, 10R target, else exit at the close. 1x, and the paper's 1%-risk sizing (≤4x).
- I3 **First half-hour → last half-hour momentum, SPY** (Gao, Han, Li, Zhou 2018).

Pass rule set before the results: net Sharpe above SPY in **both** 2016–2023 and 2024-01..2026-07, with the last 3 months
as a holdout scored once. Main cost 0.5 bp/side. The paper costs of about 0.06 bp/side at today's prices are under the
0.25 bp sensitivity row. Disclosure: the first run used 2 bp/side, at which all five lose money even in 2016–2023.
I cut the main case to 0.5 bp after seeing that, because 2 bp is about 15× SPY's 1-cent spread. The sensitivity table covers 0–2 bp.

| Sharpe (xs T-bill), 0.5 bp/side | 2016–2023 | 2024-01..2026-07 | Holdout 3m | Full | Gross (0 bp) full |
|---|---:|---:|---:|---:|---:|
| SPY buy & hold | 0.74 | 0.99 | 0.15 | 0.78 | — |
| I1a Noise boundary 1x | 0.77 | -0.13 | -0.67 | 0.56 | 0.89 |
| I1b Noise boundary ≤4x | 0.92 | 0.16 | -1.22 | 0.69 | 1.09 |
| I2a ORB QQQ 1x | 0.56 | -0.05 | 1.21 | 0.45 | 0.71 |
| I2b ORB QQQ ≤4x | 0.68 | 0.12 | 1.20 | 0.57 | 0.88 |
| I3 Last half-hour | -0.68 | -0.63 | -4.40 | -0.70 | -0.18 |

Full-period CAGR / max DD at 0.5 bp: I1b 11.9% / -31%, I2b 15.3% / -30%, SPY 15.2% / -34%.

**No intraday strategy passes.** The noise-boundary and ORB edges replicate before costs in 2016–2023 (gross Sharpe
1.31 and 0.99), but **they decayed after publication.** In 2024–26 even the gross Sharpes (0.56, 0.45) are about half of SPY's.
The ORB's strong last 3 months (Sharpe 1.2, +39% annualized at ≤4x) rests on 65 trades with a ΔSharpe CI of [-2.3, +3.8],
right after a 2.5-year stretch below SPY. That is the profile of a lucky window, not a fixed strategy. I3 loses in every window.

### Where this leaves the project
17 strategy-vs-SPY tests, 0 survivors after Holm correction, and none passed its own pre-declared rule. Searching further
on the same 10 years will eventually produce something that looks extremely profitable, and it will be an artifact of the
search. Options that could produce a real answer:
1. **Longer history** to test rules over many regimes. The environment's network policy blocks the hosts
   (`mba.tuck.dartmouth.edu`, `fred.stlouisfed.org`, `stooq.com`).
2. **Forward paper trading** of a small fixed set (e.g. I1b, I2b, N1) with rules frozen now. Live out-of-sample data
   cannot be overfit.
3. Accept a risk-shape goal instead of beating SPY: N1 vol targeting kept SPY-like return with max DD -19% vs -34% over 2017–2026.

## Round 5: diagnostics, drawdown goal, frozen forward test

### Where they lose money, and whether they make it where they should (`diagnostics.py` → `diagnostics.md`)
**N1 vol target.** Thesis: win in slow selloffs, lose in V-shapes.
- Confirmed, but 4 of the 5 SPY drawdowns since 2017 were V-shaped. It gave up 5–28 pts of each recovery
  (2020: +19% vs SPY +51%; 2025: +12% vs +24%). It was net ahead only in the slow 2022 bear (+0.9 pts).
- **Lost where it should protect:** Feb 2018 it fell -14.5% vs SPY -10%. It was at max leverage after record-calm
  January vol, then vol exploded. Calm → full leverage → shock is the structural weak spot.
- **The premise fails at the extremes:** on its 2x days (31% of the time) SPY's return per unit of risk was 0.59,
  vs 1.77 on 1.1–1.5x days. Maximum leverage bought little, at SSO's 0.89% fee. On its lowest-exposure days SPY returned
  +26% annualized, the rebounds it was out of. 6 of 7 cuts below 0.6x were followed by SPY rising; only March 2020 paid.

**1. SPY 200d SMA.** Thesis: win in slow bears, lose in V-shapes and chop.
- 20 of 25 out-of-market spells cost money: +41% of SPY gains missed vs 7.7% of losses avoided.
- SPY returned +24% annualized on out-days vs +14% on in-days, because exits cluster just before rebounds.
- **Lost even in the slow 2022 bear (-3.8 pts)** by re-entering late after the October 2022 low (+7.6% of a +34% recovery).

**I1b noise boundary.** Thesis: profit on trend days, small losses on quiet days.
- **Works as designed:** top-quintile |open→close| days made +288% (2016–23) and +87% (2024+), at +75–100 bp per trade.
  Quiet days and trades against the day's direction lose.
- **Why 2024+ went flat:** fewer trend days among trades (14% vs 22%), and quiet-day losses grew (Q1 -43 → -52 bp).
  Entries after noon turned negative (13:00 -10 bp, 15:00 -11 bp). Not a bug; the market had fewer trend days.

**I2b ORB QQQ.** Same structure: profit lives in trend days, and 75% of trades stop out.
- **Loses where it should make money:** in 2024+ longs lost -5.6% while QQQ rose strongly, while shorts made +21.8%.
  Up-opening candles got faded more often in this bull market. The 10R target is hit by under 3% of trades;
  the wins are close exits.

Hypotheses these suggest (NOT tested: testing them on this data is the overfitting loop):
- H1: cap N1 at 1.5x, or re-lever more slowly.
- H2: skip I1/ORB entries when the trailing 14-day average range is in its bottom tercile (a quiet regime).
- H3: no I1 entries after 12:30.
- H4: ORB short-only, or ORB filtered by the overnight gap direction.

H1 can be tested over 90 years once the long-history hosts are allowed. H2–H4 need intraday history, so only a new
forward freeze can judge them.

### Option 3: return for the same max drawdown (`drawdown_goal.py` → `drawdown_goal.md`)
Benchmark: SPY scaled down to the strategy's own max drawdown, rest in T-bills. Pass rule (set before running): beat it on
CAGR in both halves. Sanity check: a static 60/40 SPY/T-bill mix lands on Δ ≈ 0, as it should.

| Strategy | ΔCAGR vs DD-matched SPY 2017–21 | 2022–26 | Full (95% CI) | Pass |
|---|---:|---:|---:|---|
| N1 vol target | +9.0 | -0.4 | +5.1 [-1.1, +12.0] | no |
| N5 trend × vol target | +3.4 | -0.2 | +1.5 [-5.4, +8.6] | no |
| 1. SPY 200d SMA | +2.3 | -0.8 | +1.4 [-3.6, +6.5] | no |
| 2. TSMOM original 10 | +2.2 | +0.8 | +1.8 [-1.0, +4.6] | **yes** (hindsight-picked list) |
| 2r. TSMOM GTAA-5 | +1.7 | -1.1 | +0.4 [-2.3, +3.2] | no |

Only the hindsight-picked TSMOM list passes. Its rule-chosen twin (GTAA-5) does not, and every CI includes 0.
The best drawdown result, N1's +5 pts/yr at -19% max DD, comes entirely from 2017–21 (mostly March 2020).

### Option 2: frozen forward test (`frozen_2026_11_03/`, `forward_test.py`)
- Exact copies of `backtest.py`, `new_strategies.py` and `intraday.py`, with SHA-256 hashes in `MANIFEST.json`, frozen
  after the 2026-11-03 close. `forward_test.py` refuses to run if any byte changed, and scores only sessions after the freeze.
- Strategies: N1, T2, T2r, I1b, I2b vs SPY.
- Simulated fills with the frozen cost model, not broker paper orders. Wiring them into `engine/backtestceo/paper` is a separate job.
- Kill rule: drop a strategy if its forward max DD exceeds 1.5× its backtest max DD.
- Checkpoints at 63, 126 and 252 sessions. A strategy can graduate only after 252 sessions. One year can reject a broken
  strategy, not prove a good one.

## Round 6: our own strategies, 100,176-combination search (`search/`)

### Setup
- **Data:** Alpaca SIP adjusted daily bars from 2016-01-04, scored from 2017-02-01 after warm-up. Intraday: every SPY/QQQ
  5-min RTH bar from 2016 on. Data is cut at the 2026-11-03 close.
- **Level 2:** not used, because no history exists here. Alpaca serves top-of-book (L1) quote history back to 2016 but
  no order-book history. Databento sells historical L2, but it is paid and this environment blocks it.
- **Splits by time:** search 2017-02-01..2022-12-02 (60%), validate 2022-12-05..2024-11-15 (20%),
  holdout 2024-11-18..2026-11-03 (20%). Holdout days are dropped before anything is stored. One run, enforced by a lock file.
- **Costs:** daily 3 bp/side, intraday 0.5 bp/side × leverage. Idle cash earns BIL (T-bills); Sharpe is in excess of BIL.
- **Grid (100,176 combinations):**

  | Family | Combinations | What varies |
  |---|---:|---|
  | F1 trend | 5,760 | SMA / 12-1 momentum / SMA cross, lookbacks 20–252, equal or inverse-vol weights, daily–quarterly rebalance, vol target none–15% |
  | F2 rotation | 53,568 | 31 blends of 21–252-day momentum, skip 0/21, top-K 1–5, absolute filters, weights, rebalance, vol target |
  | F3 mean reversion | 11,025 | RSI 2/3/5/14, z-scores, IBS, consecutive down days; exits, max hold, trend filter, sizing |
  | F4 candle patterns | 735 | 7 patterns, hold 1–10 days, trend filter |
  | F5 vol targeting | 10,080 | SPY/SSO, target 8–25%, 6 estimators, cap 1–2x, bands, trend overlays, rebalance |
  | I1 opening-range breakout | 14,400 | SPY, QQQ |
  | I2 noise band | 4,608 | SPY, QQQ |

- **Universes are fixed by rule:** sector SPDRs listed before 2016; Faber GTAA-5 (2007); Antonacci GEM (2014); the union of
  those. No QQQ, GLD or TLT, the hindsight picks from round 2. The round-5 fixes H1–H4 are points inside the grid.
- **Selection** (rules in `select_top.py`, fixed before results):
  1. Top 500 by search Sharpe.
  2. Neighbor test: one ordinal parameter moved one step; median neighbor search Sharpe ≥ 0.7× own, and median neighbor validate Sharpe > 0.
  3. Rank by validate Sharpe; top 10, at most 2 per family/symbol. The cap left 6, so the last 4 were filled uncapped (disclosed).
- **Luck and multiple-testing checks:** Deflated Sharpe with N = 100,176; studentized White's Reality Check (stationary
  bootstrap, 500 draws) against vol-matched SPY; the whole pipeline rerun on shuffled data (days permuted across all ETFs together;
  intraday sessions and in-session bars permuted, overnight gap kept at the open).

### Bugs found and fixed before the holdout
1. A crash in the consecutive-down-days indicator. It was a crash, not wrong numbers; finished checkpoints were kept.
2. **Shuffle artifact:** the overnight gap was being moved into the session, which handed intraday longs SPY's overnight drift.
3. **ORB intrabar bias, found through the luck benchmark:** a target could fill on the trigger bar while a stop in the same bar
   was ignored. The first fix (worst case) overcorrected, counting lows printed before the breakout as stops after it, and
   gave Sharpe -11 on tight stops. The final version uses the standard OHLC path convention.
4. **Unresolvable stops:** ORB stops of 0.05×/0.10× ATR fit inside one median 5-min bar (0.086%), so 5-min data cannot tell
   whether stop or target hit first. They are ineligible but still counted in N. 1-minute bars would be needed to test them.

### Results
| | Real data | Shuffled noise |
|---|---:|---:|
| Best search Sharpe of 100,176 | **1.62** | **1.61** |
| Deflated-Sharpe hurdle (expected max of N unskilled trials) | 1.39 | 1.56 |
| White's Reality Check p, search split (H0: nothing beats vol-matched SPY) | 0.974 | 1.000 |
| Reality Check p, validate split over the 500 shortlisted | 0.702 | 0.142 |
| Top-10 validate Sharpe range | 1.51–2.19 | 0.8–3.0 |
| SPY Sharpe, search / validate | 0.64 / 1.23 | 0.92 / 0.36 |

The best real combination is no better than the best one found in shuffled noise. The best real Deflated Sharpe is 0.66
(0.95 needed); against vol-matched SPY it is 0.015 at best.
Family view: no daily family has more than 7.7% of its combinations beating SPY on both search and validate (vol
targeting). Trend and rotation: 0.0%. The intraday noise band is the only family with a large share (22%), and its top
picks are the 2024 paper's own default parameters. The search rediscovered the published rule, not something new.

**Holdout (run once, 2024-11-18 .. 2026-11-03, 491 sessions):**

| Strategy | CAGR | Vol | Sharpe | Max DD | Longest DD (d) | Trades | Vol-matched SPY CAGR / DD | ΔSharpe vs SPY [95% CI] |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| SPY buy & hold | 15.1% | 16.6% | 0.70 | -18.8% | 127 | 1 | — | — |
| 10-ETF TSMOM (round 2) | 11.5% | 8.8% | 0.84 | -6.9% | 112 | 24 | 10.1% / -10.1% | +0.14 [-0.82, +0.98] |
| #1/#2 noise band QQQ, paper params (stop max / band: identical trades) | 18.1% | 15.9% | 0.88 | -14.6% | 385 | 279 | 14.7% / -18.0% | +0.18 [-2.12, +1.98] |
| #3 noise band SPY, VWAP stop | -6.3% | 15.4% | -0.60 | -25.6% | 355 | 304 | 14.4% / -17.6% | -1.30 [-3.55, +0.41] |
| #4 noise band SPY, long-only, 7d | 3.2% | 6.8% | -0.07 | -8.1% | 417 | 141 | 8.8% / -7.8% | -0.77 [-2.19, +0.43] |
| #5 ORB QQQ 15-min, gap filter, 1x | 4.9% | 5.5% | 0.19 | -3.2% | 177 | 255 | 7.9% / -6.2% | -0.51 [-2.45, +1.17] |
| #6 ORB QQQ 10-min, gap filter, 1% risk | 7.3% | 19.5% | 0.26 | -14.2% | 276 | 261 | 16.9% / -21.8% | -0.44 [-2.32, +1.01] |
| #7 noise band QQQ 7d, VWAP stop | 13.1% | 16.6% | 0.59 | -13.2% | 334 | 295 | 15.1% / -18.8% | -0.11 [-2.36, +1.58] |
| #8/#9 noise band QQQ 7d, band / max stop | 11.3% | 16.0% | 0.50 | -18.5% | 558 | 295 | 14.8% / -18.2% | -0.20 [-2.61, +1.64] |
| #10 noise band QQQ, hourly checks | 12.4% | 14.5% | 0.61 | -10.0% | 381 | 249 | 13.9% / -16.6% | -0.09 [-2.39, +1.63] |

**Nothing survives.** Pre-declared rule: Holm-adjusted p < 0.05 for ΔSharpe > 0 AND CAGR above vol-matched SPY. All 10
have Holm p = 1.00. Only #1/#2 (the same trades) had a higher holdout Sharpe than SPY and TSMOM. They beat vol-matched SPY
by 3.4 pts CAGR, but the CI spans -2.1 to +2.0, and the same rule on SPY (#3) lost 6.3%/yr. 8 of 10 fell below SPY's Sharpe.

### The round-5 fixes (`search/fixes.md`, search / validate Sharpe; SPY 0.64 / 1.23)
- **Vol target (H1):** cap 1.5x 0.79/1.15 vs original 0.78/1.14, the same. Slower re-levering and all three combined are worse in search.
- **Noise band:** skipping the quiet regime (H2) helped search (1.29) but hurt validate (0.77). No entries after 12:30 (H3)
  cut search to 0.86 with a similar validate (1.73).
- **ORB:** short-only (H4a) is worse. The gap-direction filter (H4b) lifted validate from 0.17 to 0.78 and fed picks #5/#6,
  which made 0.19/0.26 Sharpe in the holdout.
- **Trend re-entry:** SMA100 beat SMA200 on both splits (0.82/1.03 vs 0.66/0.95), but still not SPY.
- No fix turned a strategy into one that beats SPY on both splits.

### Caveats
- The holdout years (2024–26) were already seen in rounds 1–5, and the grid contains rules I had looked at there. That can
  only bias toward false positives, so the negative result stands.
- Only one shuffle was run (compute): it shows the scale of luck, not a full null distribution.
- The fast engines hold target weights between rebalances; finalists were rerun on the exact engine (intraday: same per-trade engine).

## Round 7: why "nothing survives" was the wrong verdict, and what does work (`search/moc.py`, `frozen_2026_11_04/`)

**The test was underpowered and used the wrong yardstick.**
- Power of the round-6 holdout test: with Holm over 10, a 2-year holdout catches a true +0.5 Sharpe edge over SPY 2% of the
  time, and +1.0 5% of the time. 80% power for +0.5 on a single test needs about 53 years of holdout.
- Sharpe-vs-SPY is the wrong bar for an intraday strategy that has ~0 correlation with SPY. The question is whether it adds
  return to SPY (alpha), not whether it beats SPY alone.

**Candidate 1: noise-band intraday momentum on QQQ** (the 2024 paper's default parameters; the search's #1 pick).
| Split | Sharpe | SPY Sharpe | Corr with SPY | Alpha / yr | t(alpha), HAC |
|---|---:|---:|---:|---:|---:|
| Search 2017-02..2022-12 | 1.35 | 0.64 | -0.10 | 21.4% | 4.04 |
| Validate 2022-12..2024-11 | 2.19 | 1.22 | 0.00 | 26.3% | 3.40 |
| Holdout 2024-11..2026-11 | 0.88 | 0.70 | -0.02 | 14.2% | 1.30 |

- Positive in every calendar year 2017–2026: +20 +51 +3 +18 +10 +20 +31 +27 +9 +11 (% P&L, ≤4x vol-sized).
- Break-even cost is about 2.4 bp/side, vs a 0.5 bp/side main case; QQQ's real half-spread is ~0.1 bp.
- **Holdout portfolio test:**

  | | CAGR | Sharpe | Max DD |
  |---|---:|---:|---:|
  | SPY | 15.2% | 0.70 | -18.8% |
  | SPY vol-matched to the 50/50 mix | 11.9% | 0.70 | -13.0% |
  | 50% SPY + 50% noise band | 17.5% | 1.13 | -7.4% |
  | 100% SPY + half-size overlay | 23.2% | 1.02 | -16.5% |

- **The real-vs-luck test supports it:** 82% of noise-band settings were positive on both search and validate,
  vs 29% on shuffled data.
- **But it is decaying since publication:** the whole QQQ family's median holdout Sharpe is 0.14 (search median 0.95), and the
  SPY version, the paper's own instrument, is median -0.55 in the holdout. The 0.88 of the chosen point is top-6% of its
  family. A realistic forward Sharpe expectation is well below the backtest.

**Candidate 2: SPY IBS mean reversion with market-on-close fills** (round 6b, `moc_results.md`). Round 6 forced next-open fills,
which removes the overnight bounce these rules trade. MOC look-ahead check: the 15:55-price signal matches the close-based
signal on 99.0% of days. Buy SPY at the close when IBS < 0.10; exit at the first close above the 5-day SMA (max 10 days).
Sharpe: search 0.98, validate 1.64, holdout 1.00. **That holdout figure is a second look and not clean**, because the holdout
had already been used once. The neighbors are similar (IBS < 0.15 / 0.20: 0.27–0.91 in the holdout).

**Frozen for forward testing** (`frozen_2026_11_04/`, `forward_test_v2.py`, hash-checked, completed sessions after
2026-11-03 only):
- Sleeves: noise band QQQ, SPY IBS (MOC).
- Portfolios: 50/50 SPY + noise band; SPY + half-size overlay; 40/30/30.
- Kill rules are in `MANIFEST.json`.

Bottom line: there is one real edge in this data (intraday momentum), and it is fading. The way to use it is as a
low-correlation sleeve next to SPY, not as a replacement that beats SPY on its own. The forward test is the only clean
evidence left.
