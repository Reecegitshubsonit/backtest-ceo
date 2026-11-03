# ETF strategy research: 5 strategies vs buy-and-hold SPY

Run: `python3 research/etf_strategies/backtest.py` (needs Alpaca keys in env or the agent proxy). Writes `results.md`, `results.csv`.

## Data and assumptions
- **Source: Alpaca SIP, split+dividend adjusted.** Yahoo was asked for but is blocked by this environment's network
  policy (403 on query1/query2.finance.yahoo.com). Alpaca adjusted bars are equivalent to Yahoo "Adj Close" series.
- Daily: 2016-01-04 .. 2026-11-03; 2016 is warm-up, scored 2017-01-03 onward, plus a last-2-years window.
- Intraday: last 60 calendar days of SPY 5-min RTH bars (Yahoo's 5-min limit), 42 sessions. Intraday strategy only.
- Signal on close, fill at **next bar open**. No lookahead.
- Costs: daily 3 bp/side (fees + spread/slippage), intraday 2 bp/side, on every weight change (turnover-based).
- Sharpe: daily returns, rf = 0, ×√252. Idle cash earns 0; trend/rotation "off" state buys BIL explicitly.
- Trades = number of fills (each symbol weight change; monthly trims count).

## Strategies
1. **Trend – SPY 200d SMA**: SPY above 200d SMA else BIL, checked daily.
2. **Trend – 10-ETF TSMOM**: SPY QQQ IWM EFA EEM TLT IEF GLD DBC VNQ, 10% slots, held if 12-1m return > 0 and > 200d SMA, else BIL. Monthly.
3. **Rotation – sectors**: 11 SPDR sectors, top 3 by avg 1/3/6-month return; a pick must beat BIL over 6m else its slot → BIL. Monthly.
4. **Rotation – dual momentum**: best 6-month of SPY/QQQ/EFA/TLT/GLD if it beats BIL, else BIL. Monthly.
5. **Mean reversion**
   - 5a daily: SPY RSI(2) < 10 while > 200d SMA; exit close > 5d SMA or 10 days.
   - 5b intraday: SPY 5-min z of (price − session VWAP), long z < −2 / short z > +2, exit at VWAP or 15:50; flat overnight.

## Results
See `results.md` (copied below at time of commit).

### Full: 2017-01-03 .. 2026-11-03 (3 bp/side)
| Strategy | CAGR | Max DD | Sharpe | Trades |
|---|---:|---:|---:|---:|
| SPY buy & hold | 14.7% | -33.9% | 0.86 | 1 |
| 1. SPY 200d SMA / BIL | 10.5% | -19.6% | 0.89 | 101 |
| 2. 10-ETF TSMOM | 7.2% | -8.2% | **1.06** | 239 |
| 3. Top-3 sectors | 10.4% | -32.7% | 0.66 | 273 |
| 4. Dual momentum | 10.4% | -37.0% | 0.60 | 71 |
| 5a. RSI(2) SPY | 2.6% | -15.0% | 0.45 | 171 |

### Last 2 years: 2024-11-04 .. 2026-11-03
| Strategy | CAGR | Max DD | Sharpe | Trades |
|---|---:|---:|---:|---:|
| SPY buy & hold | 14.6% | -18.6% | 0.91 | 1 |
| 1. SPY 200d SMA / BIL | 10.1% | -10.3% | 0.89 | 13 |
| 2. 10-ETF TSMOM | 10.7% | -7.0% | **1.20** | 59 |
| 3. Top-3 sectors | 10.9% | -15.0% | 0.82 | 56 |
| 4. Dual momentum | 19.6% | -26.0% | 0.88 | 13 |
| 5a. RSI(2) SPY | 5.1% | -4.8% | 1.01 | 43 |

### Intraday: 2026-09-04 .. 2026-11-03, 42 sessions (2 bp/side)
| Strategy | CAGR | Max DD | Sharpe | Trades |
|---|---:|---:|---:|---:|
| SPY buy & hold | -11.8% | -3.5% | -1.10 | 1 |
| 5b. VWAP z±2 reversion | -16.6% | -3.7% | -3.41 | 170 |

## Read
- Nothing beat SPY on CAGR over the full window. SPY's bull run is the hurdle.
- Best risk-adjusted: **10-ETF TSMOM** (Sharpe 1.06/1.20, max DD -8%), at half SPY's CAGR. Lever-up candidate.
- SPY 200d SMA: same Sharpe as SPY, DD cut ~40%, gives up ~4 pts CAGR (whipsaw: 101 fills).
- Rotations: no edge over SPY full period; dual momentum's 2-year win is one concentrated run, DD worse than SPY.
- RSI(2) with next-open fills: edge mostly gone (in market ~15% of days). Enter-at-close variant would score better but needs MOC orders.
- Intraday VWAP reversion: loses after costs; 60 days / 42 sessions is too short to conclude anything — CAGR annualized from 2 months is noise.
- Caveats: one parameter set per strategy (no tuning, no out-of-sample split), ETF survivorship (XLRE/XLC join late), no taxes, BIL yield only when explicitly held.
