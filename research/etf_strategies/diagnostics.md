# Diagnostics: where the candidates make and lose money

Daily section: 2017-01-03 .. latest, same engine/costs as the backtests. Intraday section: 0.5 bp/side main case.

## N1 vol target 15% (SPY/SSO, ≤2x)

**Thesis (when it should make money vs SPY):** Volatility clusters, and high-vol periods have worse return per unit of risk. Cutting exposure as vol rises should lose less in slow-building selloffs. Levering up in calm markets should earn more than SPY. It should LOSE vs SPY in V-shaped crashes: it de-levers after the drop and misses the rebound.

| SPY drawdown episode | SPY fall | Strategy in fall | SPY recovery leg | Strategy in recovery | Net vs SPY over episode |
|---|---:|---:|---:|---:|---:|
| 2018-01-26 → 2018-02-08 → 2018-08-07 | -10.0% | -14.5% | +11.2% | +11.5% | -4.7% |
| 2018-09-20 → 2018-12-24 → 2019-04-12 | -19.3% | -19.4% | +24.3% | +19.0% | -4.4% |
| 2020-02-19 → 2020-03-23 → 2020-08-10 | -33.8% | -18.6% | +51.4% | +19.2% | -3.1% |
| 2022-01-03 → 2022-10-12 → 2023-12-13 | -24.5% | -19.0% | +34.0% | +26.0% | +0.9% |
| 2025-02-19 → 2025-04-08 → 2025-06-26 | -18.8% | -17.2% | +23.6% | +12.3% | -7.5% |

| Exposure | Days | SPY ann. return those days | SPY ann. vol those days | SPY Sharpe-like | Strategy P&L contribution |
|---|---:|---:|---:|---:|---:|
| 0-0.6 | 221 | +25.8% | 38.0% | 0.68 | +4.7% |
| 0.6-0.9 | 496 | +19.8% | 20.8% | 0.95 | +27.5% |
| 0.9-1.1 | 315 | +11.6% | 15.2% | 0.76 | +16.5% |
| 1.1-1.5 | 653 | +21.9% | 12.4% | 1.77 | +72.1% |
| 1.5-2 | 788 | +5.9% | 10.0% | 0.59 | +24.9% |

**Exposure-cut events (exposure falls below 0.6): next 21 sessions**

| Date | Exposure | SPY next 21d | N1 next 21d | Missed |
|---|---:|---:|---:|---:|
| 2018-12-27 | 0.50 | +7.3% | +3.6% | -3.7% |
| 2020-03-03 | 0.51 | -16.2% | -7.6% | +8.6% |
| 2020-06-12 | 0.52 | +5.2% | +3.3% | -1.8% |
| 2022-03-17 | 0.57 | +0.8% | -0.1% | -0.9% |
| 2022-05-05 | 0.55 | -4.3% | -3.0% | +1.3% |
| 2022-10-24 | 0.51 | +5.4% | +2.9% | -2.5% |
| 2025-04-04 | 0.59 | +5.0% | +0.3% | -4.6% |

## 1. SPY 200d SMA / T-bills

**Thesis (when it should make money vs SPY):** Bear markets are slow enough for a 200-day filter to exit before most of the fall and re-enter after the low. It should beat SPY in long declines (2022) and LOSE in fast V-shapes (2018 Q4, 2020, 2025) and in chop around the average (whipsaw).

| SPY drawdown episode | SPY fall | Strategy in fall | SPY recovery leg | Strategy in recovery | Net vs SPY over episode |
|---|---:|---:|---:|---:|---:|
| 2018-01-26 → 2018-02-08 → 2018-08-07 | -10.0% | -10.0% | +11.2% | +11.2% | +0.0% |
| 2018-09-20 → 2018-12-24 → 2019-04-12 | -19.3% | -14.2% | +24.3% | +4.7% | -10.5% |
| 2020-02-19 → 2020-03-23 → 2020-08-10 | -33.8% | -18.9% | +51.4% | +11.5% | -9.8% |
| 2022-01-03 → 2022-10-12 → 2023-12-13 | -24.5% | -9.4% | +34.0% | +7.6% | -3.8% |
| 2025-02-19 → 2025-04-08 → 2025-06-26 | -18.8% | -9.8% | +23.6% | +5.5% | -5.3% |

| Exposure | Days | SPY ann. return those days | SPY ann. vol those days | SPY Sharpe-like | Strategy P&L contribution |
|---|---:|---:|---:|---:|---:|
| 0 (cash) | 404 | +24.4% | 32.6% | 0.75 | -4.9% |
| 0.9-1.1 | 2069 | +13.7% | 13.1% | 1.04 | +112.4% |

**Out-of-market spells:** 25. SPY gains missed while out (sum): +41.1%; SPY losses avoided (sum): -7.7%.
Spells that cost money (SPY rose while out): 20 of 25. Largest five:

| Out from | Back in | SPY while out |
|---|---|---:|
| 2026-03-23 | 2026-04-09 | +4.8% |
| 2022-08-18 | 2022-12-01 | -4.1% |
| 2022-01-26 | 2022-01-31 | +3.6% |
| 2025-03-27 | 2025-05-13 | +3.2% |
| 2023-10-26 | 2023-11-02 | +3.2% |
| 2025-03-11 | 2025-03-25 | +3.0% |
| 2019-06-03 | 2019-06-05 | +2.7% |
| 2022-04-12 | 2022-08-17 | -2.6% |

## I1b noise boundary SPY (≤4x)

**Thesis:** Intraday momentum. When price leaves the noise band, the day is more likely to keep trending. Most profit should come from large open→close days with the trade on the right side. Quiet days should cost only small stop-outs.

**By side (1 long, -1 short)**

| side (1 long, -1 short) | Trades 16-23 | Sum P&L 16-23 | Avg bp 16-23 | Trades 24+ | Sum P&L 24+ | Avg bp 24+ |
|---|---:|---:|---:|---:|---:|---:|
| -1 | 807 | +42.4% | +5.3 | 294 | +0.1% | +0.0 |
| 1 | 910 | +65.8% | +7.2 | 338 | +1.8% | +0.5 |

**By exit**

| exit | Trades 16-23 | Sum P&L 16-23 | Avg bp 16-23 | Trades 24+ | Sum P&L 24+ | Avg bp 24+ |
|---|---:|---:|---:|---:|---:|---:|
| close | 605 | +543.1% | +89.8 | 212 | +164.9% | +77.8 |
| stop | 1112 | -435.0% | -39.1 | 420 | -163.0% | -38.8 |

**By entry hour**

| entry hour | Trades 16-23 | Sum P&L 16-23 | Avg bp 16-23 | Trades 24+ | Sum P&L 24+ | Avg bp 24+ |
|---|---:|---:|---:|---:|---:|---:|
| 10:00 | 705 | +62.9% | +8.9 | 252 | +6.1% | +2.4 |
| 11:00 | 284 | +17.4% | +6.1 | 102 | -2.3% | -2.3 |
| 12:00 | 211 | +0.6% | +0.3 | 82 | +3.4% | +4.2 |
| 13:00 | 165 | -0.0% | -0.0 | 72 | -7.3% | -10.1 |
| 14:00 | 178 | +10.3% | +5.8 | 73 | +7.8% | +10.7 |
| 15:00 | 174 | +17.0% | +9.8 | 51 | -5.8% | -11.4 |

**By day's |open→close| quintile**

| day's |open→close| quintile | Trades 16-23 | Sum P&L 16-23 | Avg bp 16-23 | Trades 24+ | Sum P&L 24+ | Avg bp 24+ |
|---|---:|---:|---:|---:|---:|---:|
| Q1 quiet | 362 | -155.6% | -43.0 | 109 | -56.8% | -52.1 |
| Q2 | 325 | -101.7% | -31.3 | 145 | -48.3% | -33.3 |
| Q3 | 308 | +3.8% | +1.2 | 160 | -6.8% | -4.3 |
| Q4 | 339 | +74.1% | +21.8 | 131 | +27.1% | +20.7 |
| Q5 trend | 383 | +287.6% | +75.1 | 87 | +86.8% | +99.7 |

**By trade side matches day's open→close direction**

| trade side matches day's open→close direction | Trades 16-23 | Sum P&L 16-23 | Avg bp 16-23 | Trades 24+ | Sum P&L 24+ | Avg bp 24+ |
|---|---:|---:|---:|---:|---:|---:|
| False | 299 | -179.4% | -60.0 | 87 | -45.3% | -52.1 |
| True | 1418 | +287.6% | +20.3 | 545 | +47.2% | +8.7 |

Trend days (top quintile |open→close|) share of trades: 20%; their P&L 2016-23 +287.6%, 2024+ +86.8%; all other days 2016-23 -179.4%, 2024+ -84.8%.

## I2b ORB 5-min QQQ (1% risk, ≤4x)

**Thesis:** The first 5-min candle's direction persists on trend days. Small losses (stop at the candle's other end) and rare large wins (10R target or a strong close) should give positive skew. Profit should be concentrated in big trend-aligned days.

**By side (1 long, -1 short)**

| side (1 long, -1 short) | Trades 16-23 | Sum P&L 16-23 | Avg bp 16-23 | Trades 24+ | Sum P&L 24+ | Avg bp 24+ |
|---|---:|---:|---:|---:|---:|---:|
| -1 | 961 | +77.4% | +8.1 | 364 | +21.8% | +6.0 |
| 1 | 1025 | +86.0% | +8.4 | 345 | -5.6% | -1.6 |

**By exit**

| exit | Trades 16-23 | Sum P&L 16-23 | Avg bp 16-23 | Trades 24+ | Sum P&L 24+ | Avg bp 24+ |
|---|---:|---:|---:|---:|---:|---:|
| close | 446 | +1052.5% | +236.0 | 172 | +361.2% | +210.0 |
| stop | 1494 | -1145.5% | -76.7 | 522 | -413.5% | -79.2 |
| target | 46 | +256.5% | +557.6 | 15 | +68.5% | +456.9 |

**By day's |open→close| quintile**

| day's |open→close| quintile | Trades 16-23 | Sum P&L 16-23 | Avg bp 16-23 | Trades 24+ | Sum P&L 24+ | Avg bp 24+ |
|---|---:|---:|---:|---:|---:|---:|
| Q1 quiet | 406 | -256.4% | -63.1 | 133 | -92.2% | -69.3 |
| Q2 | 396 | -154.0% | -38.9 | 143 | -83.3% | -58.2 |
| Q3 | 371 | -84.3% | -22.7 | 168 | -18.6% | -11.1 |
| Q4 | 383 | +126.4% | +33.0 | 156 | +59.4% | +38.1 |
| Q5 trend | 430 | +531.7% | +123.7 | 109 | +150.9% | +138.5 |

**By trade side matches day's open→close direction**

| trade side matches day's open→close direction | Trades 16-23 | Sum P&L 16-23 | Avg bp 16-23 | Trades 24+ | Sum P&L 24+ | Avg bp 24+ |
|---|---:|---:|---:|---:|---:|---:|
| False | 834 | -640.7% | -76.8 | 267 | -209.8% | -78.6 |
| True | 1152 | +804.1% | +69.8 | 442 | +226.0% | +51.1 |

Trend days (top quintile |open→close|) share of trades: 20%; their P&L 2016-23 +531.7%, 2024+ +150.9%; all other days 2016-23 -368.2%, 2024+ -134.7%.
