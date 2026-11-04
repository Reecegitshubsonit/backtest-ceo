# Strategy spec for independent review

Prepared 2026-11-04 from the `backtest-ceo` research (branch `claude/funny-einstein-9h4tvb`, folder `research/etf_strategies/`).
Read-only research; nothing here places orders. A reviewer should treat every number below as a claim to verify, not a fact.

## 1. Summary

Two strategies survived seven rounds of testing (about 112,000 parameter combinations, plus about 30 hand-built rules). Neither
was invented by the search: both are published ideas, run with default or near-default parameters.

| Name | What it is | Role | Main risk |
|---|---|---|---|
| **NBQ**: noise-band intraday momentum on QQQ | Zarattini, Aziz & Barbon (2024), "Beat the Market", paper defaults, applied to QQQ instead of SPY | Return stream uncorrelated with SPY (ρ ≈ -0.07) | Edge is decaying since publication |
| **IBS**: SPY internal-bar-strength dip buy, market-on-close | Classic IBS mean reversion (IBS < 0.10, exit above the 5-day SMA) | Low-exposure (19% of days) dip buyer | Holdout evidence is a second look, not clean |

Recommended use: as **sleeves next to SPY**, not as SPY replacements. 50% SPY + 50% NBQ had Sharpe 1.13 vs SPY 0.70 in the
holdout. On its own, no strategy's edge over SPY is statistically significant in a 2-year holdout (see §5 for why that test is
nearly powerless).

## 2. Data and conventions (apply to everything below)
- **Data:** Alpaca market data, SIP feed, split- and dividend-adjusted (`adjustment=all`). Daily bars from 2016-01-04; 5-minute
  bars from 2016-01-04, regular trading hours only (09:30–16:00 ET; bars are labelled by their start time). Data cut at the
  2026-11-03 close.
- **Cash:** idle cash earns BIL's daily total return (T-bill proxy, net of its 0.14% fee). Sharpe ratios are annualized
  (×√252) from daily returns in excess of BIL.
- **Time splits:** search 2017-02-01..2022-12-02 (60%), validate 2022-12-05..2024-11-15 (20%), holdout 2024-11-18..2026-11-03 (20%).
  2016 is indicator warm-up.
- **Not available:** Level 2 / order-book history (Alpaca has only top-of-book quotes; Databento is blocked here). Data before
  2016 (Ken French, FRED, stooq and Yahoo are blocked by this environment's network policy).

## 3. Strategy NBQ: noise-band intraday momentum, QQQ

### Rules (exact)
Notation for session *d* and 5-minute bar *k* (k = 0 is 09:30–09:35):
1. **Noise band.** For each bar time *k*: σ(d,k) = mean over the **previous 14 sessions** of |close(d′,k) / open(d′) − 1|,
   where open(d′) is that session's 09:30 open. Same time of day only; today is excluded.
2. **Bands.** UB(d,k) = max(open(d), prevclose(d)) × (1 + σ(d,k)); LB(d,k) = min(open(d), prevclose(d)) × (1 − σ(d,k)).
   prevclose = prior session's 16:00 close (this handles the overnight gap).
3. **VWAP.** Session VWAP from 09:30, typical price (H+L+C)/3 × volume, cumulative.
4. **Decision times.** Closes of the bars ending at 10:00, 10:30, …, 15:30 (every 30 minutes; 12 decisions). Decide on the
   bar close, fill at the **next 5-min bar's open**.
5. **Exits first.** A long exits if close < max(UB, VWAP). A short exits if close > min(LB, VWAP).
6. **Entries (when flat, including right after an exit at the same decision).** Long if close > UB; short if close < LB.
   Entries allowed at decisions up to and including 15:30.
7. **Flat by the close.** Any open position is closed at the 16:00 close. Never held overnight.
8. **Sizing.** Leverage = min(4, 0.02 / σ_daily), where σ_daily = standard deviation of QQQ's daily close-to-close returns over
   the **previous 14 sessions** (targets 2% daily vol). Median 1.88x, 90th percentile 3.61x, at the 4x cap 6% of days.
   Requires margin and US pattern-day-trader status (≥ $25k).
9. **Costs.** 0.5 bp per side × leverage. QQQ's quoted spread is ~1 cent on ~$600 (≈0.17 bp; half-spread ≈0.08 bp).
   The paper assumed $0.0035/share commission + $0.001/share slippage. **Break-even: about 2.4 bp per side.**

Code: `research/etf_strategies/search/families_intraday.py` → `NoiseBand.pnl` with
`look=14, mult=1.0, freq=6, stop="max", last=71, quiet=False, size="vol2", side="both", sym="QQQ"`.

### Results
| Split | CAGR | Vol | Sharpe | Max DD | SPY Sharpe | Alpha / yr vs SPY | t(alpha), Newey-West |
|---|---:|---:|---:|---:|---:|---:|---:|
| Search 2017-02..2022-12 | 22.5% | 15.2% | 1.35 | -10.6% | 0.64 | 21.4% | 4.04 |
| Validate 2022-12..2024-11 | 35.7% | 12.0% | 2.19 | -5.9% | 1.22 | 26.3% | 3.40 |
| Holdout 2024-11..2026-11 | 18.2% | 15.9% | 0.88 | -14.6% | 0.70 | 14.2% | 1.30 |
| Full 2017-02..2026-11 | 24.1% | 14.8% | 1.38 | -14.6% | 0.73 | | |

Correlation with SPY: -0.07. Active on 59% of days; 45% of active days are winners; average active day +13.8 bp. Profit
comes from large trend days, while quiet days produce small stop-outs (positive skew).

Cost sensitivity (Sharpe search / validate / holdout): 0 bp 1.64/2.52/1.13; 0.5 bp 1.35/2.19/0.88; 1 bp 1.06/1.86/0.63;
2 bp 0.48/1.19/0.14.

### Evidence it is real, and evidence it is fading
- **For:** profitable every calendar year 2017–2026 (table §6). Across all 4,608 noise-band settings, 82% were positive on both
  search and validate on real data, vs 29% on shuffled data, where intraday time structure was destroyed. The parameters are
  the paper's defaults, not tuned here. Neighboring parameters perform similarly (median neighbor Sharpe 1.28 search /
  1.94 validate).
- **Against:** the paper was published in 2024, and in the holdout the whole QQQ family's median Sharpe dropped to 0.14
  (from 0.95 in search). The chosen point's 0.88 is in the top 6% of its family, which is partly luck. The **SPY** version,
  the paper's own instrument, has a family median of -0.55 in the holdout and lost money in 2025–26. Expect forward
  performance well below the backtest.

## 4. Strategy IBS: SPY internal-bar-strength dip buy, market-on-close

### Rules (exact, tradable version)
1. **Signal at 15:55 ET** from regular-hours data: IBS = (P − Low) / (High − Low), where P = SPY price at 15:55 and High/Low = the
   session's regular-hours high and low up to 15:55.
2. **Entry:** if flat and IBS < 0.10 → buy SPY with 100% of the sleeve via a **market-on-close** order (filled at the 16:00 close).
3. **Exit:** at 15:55, if P > the 5-day SMA (using the previous 4 closes plus P) → sell market-on-close. Also exit after 10
   sessions in the trade. The entry day does not count as an exit check.
4. **No trend filter.** Long only. When flat, the sleeve sits in T-bills.
5. **Costs:** 3 bp per side (conservative; MOC fills at the auction price, with no spread).

Variant actually searched (and reported in round 6b): the same rules using the daily bar's own high/low/close at the close.
Daily-bar high/low include out-of-hours prints on about 5% of days, and the 15:55 signal fires on different days in about 37% of
cases. The tradable version above performs similarly: Sharpe 1.27 / 1.91 / 0.79 vs 0.98 / 1.64 / 1.00 as searched.

Code: `families_daily.py` → `MeanRev` with `ind=27 (IBS<0.10), exit="sma5", maxhold=10, trend="none", sizing="slot", univ="SPY"`,
executed with `moc.run_moc` (searched variant). The 15:55 tradable variant is in the review notes (§8).

### Results (searched variant; tradable variant Sharpe in brackets)
| Split | CAGR | Vol | Sharpe | Max DD |
|---|---:|---:|---:|---:|
| Search | 11.7% | 10.9% | 0.98 [1.27] | -11.7% |
| Validate | 16.8% | 6.6% | 1.64 [1.91] | -6.1% |
| Holdout (second look) | 14.6% | 10.2% | 1.00 [0.79] | -7.5% |
| Full | 13.3% | 10.1% | 1.06 | -11.7% |

About 18 trades a year, in the market 19% of days. Correlation with SPY +0.56 (it is long SPY when in); with NBQ +0.04.
**The holdout is not clean for IBS:** it was found in a follow-up search (MOC fills) after the holdout had been used once.

## 5. Statistical caveats (read before trusting anything)
- **Multiple testing:** about 112,000 combinations were tried. On the search split, the best real combination (Sharpe 1.62) was no
  better than the best on shuffled data (1.61). White's Reality Check vs vol-matched SPY gave p = 0.97. The two strategies
  here are defensible because they are published rules with default parameters, and because their family-level evidence holds,
  not because they won the search.
- **The holdout test has almost no power:** a 2-year window detects a true +0.5 Sharpe advantage over SPY only ~12% of the
  time on a single test (~2% after a 10-way Holm correction). About 53 years would be needed for 80% power. The right test for an
  uncorrelated intraday stream is alpha vs SPY, or the portfolio effect.
- **Researcher contamination:** the 2024–26 period was seen during earlier rounds, before the formal holdout.
- **Short history:** 2016 onward only. One crash (2020), one bear market (2022).
- **Intraday resolution:** 5-minute bars. NBQ only acts on 30-minute closes, so bar resolution is not an issue for it.
  Breakout variants with stops tighter than one bar were excluded as untestable.

## 6. Year-by-year returns
| Year | SPY | NBQ | IBS | 50% SPY + 50% NBQ | 40% SPY / 30% NBQ / 30% IBS |
|---|---:|---:|---:|---:|---:|
| 2017 | +19.6% | +21.3% | +5.0% | +20.9% | +15.9% |
| 2018 | -5.0% | +65.9% | -5.3% | +26.7% | +13.1% |
| 2019 | +31.1% | +4.4% | +12.0% | +17.4% | +17.2% |
| 2020 | +18.5% | +18.5% | +29.5% | +20.6% | +23.6% |
| 2021 | +28.6% | +8.8% | +15.7% | +18.9% | +19.0% |
| 2022 | -18.2% | +22.5% | +18.2% | +1.1% | +4.0% |
| 2023 | +26.2% | +41.8% | +10.6% | +34.2% | +26.0% |
| 2024 | +24.9% | +36.5% | +21.3% | +31.2% | +27.7% |
| 2025 | +17.7% | +12.3% | +17.4% | +15.9% | +16.7% |
| 2026 (to Nov 3) | +11.5% | +13.9% | +8.3% | +13.1% | +11.6% |

## 7. Portfolios (CAGR / vol / Sharpe / max DD)
| Split | SPY | 50% SPY + 50% NBQ | 40/30/30 SPY/NBQ/IBS |
|---|---|---|---|
| Search | 12.3% / 19.6% / 0.64 / -33.8% | 18.3% / 11.8% / 1.40 / -16.3% | 15.9% / 10.7% / 1.35 / -15.4% |
| Validate | 22.4% / 13.2% / 1.22 / -10.0% | 29.4% / 8.9% / 2.38 / -4.4% | 24.9% / 7.5% / 2.35 / -4.7% |
| Holdout | 15.2% / 16.6% / 0.70 / -18.8% | 17.5% / 11.4% / 1.13 / -7.4% | 16.5% / 10.3% / 1.16 / -8.1% |
| Full | 14.8% / 17.9% / 0.73 / -33.8% | 20.3% / 11.2% / 1.49 / -16.3% | 17.8% / 10.0% / 1.45 / -15.4% |

On the holdout, SPY scaled down to the 50/50 mix's vol returned 11.9% / max DD -13.0%. The mixes rebalance daily and assume
no extra cost for that (NBQ is flat every night, so the 50/50 split is reset each day anyway).

## 8. What the reviewer should check
1. **Look-ahead in NBQ:** σ(d,k) and σ_daily must use only previous sessions. The decision uses the bar *ending* at :00/:30, and
   the fill is the next bar's open. VWAP must include only bars up to the decision bar.
2. **Fill realism:** QQQ market orders at 10:00:00, 10:30:00, … filled at the next 5-min bar's open. Check against 1-minute
   data or quotes if available. Check slippage at 2–4x leverage for the intended account size.
3. **Costs:** is 0.5 bp/side realistic, including commissions and SEC/FINRA fees on sells? The break-even is ~2.4 bp.
4. **Decay:** rerun NBQ on data after 2026-11-03 (the frozen forward test does this: `forward_test_v2.py`). The kill rule is a
   negative Sharpe after 252 sessions, or a drawdown beyond 1.5× the backtest max DD.
5. **IBS:** the tradable 15:55 version above is the one to verify. Confirm MOC order cutoffs (NYSE Arca: 15:50 ET for SPY;
   check your broker's).
6. **Independent data:** reproduce with a second vendor (Polygon, Databento, IQFeed) and with pre-2016 data if available.
7. **Out-of-sample on other instruments**, as a robustness check only, not for selection: NBQ on IWM, DIA and sector ETFs; IBS on QQQ and IWM.

## 9. Reproduce
From `research/etf_strategies/search/` (needs Alpaca data access; first run fetches about 1M 5-min bars):

    python3 check_engines.py                       # engine fidelity
    python3 search.py real && python3 search.py shuffled
    python3 select_top.py real && python3 select_top.py shuffled
    python3 moc.py                                 # IBS / mean reversion with MOC fills
    python3 ../forward_test_v2.py                  # frozen forward test, sessions after 2026-11-03 only

Full history of what was tried and rejected: `research/etf_strategies/README.md` (rounds 1–7).
