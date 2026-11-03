# Crypto edge search — round 2

Script: `engine/scripts/crypto_edge_round2.py` (34 s, Alpaca bars). Full tables: `docs/crypto-edge-round2-tables.md`.
Run 2026-11-03. Rules unchanged from the original brief: BTC/ETH/SOL, intraday strategies on 60 days of bars, daily strategies on 2+ years, fees included, reject < 30 trades, report win rate / expectancy / max DD / Sharpe / trade count.

## Bottom line

- **Five daily strategies pass the fixed rules. None is statistically proven.** Every bootstrap 95% CI on Sharpe(strategy) − Sharpe(buy & hold) in the holdout spans zero. Every deflated Sharpe (which adjusts for how many variants were tried) is ≤ 0.41; 0.95 would be convincing.
- **Pass:** Dual-momentum rotation, BTC-trend gate, TSMOM vote 10–90d, TSMOM 28d, SMA cross 10/30.
- **Stricter reading of "< 30 trades":** if the 30-trade minimum must hold *inside the holdout per coin* (not just over the full 2021+ period), only **Dual-momentum rotation** passes (37 holdout trades).
- **Why they "won":** buy & hold was poor in the holdout (ETH −4%/y, SOL −25%/y). Most of the edge is sitting in cash during a falling market, which is the same drawdown-cutting result as round 1.
- **Intraday: nothing survives.** Two of the paper runner's live legs can't be judged on 60 days: SuperTrend 4h and EMA200+ADX 4h make 3–12 trades. The live **EMA 9/21 BTC 1h leg loses on all three coins, even before fees** (gross −0.17% to −0.44% per trade). Turn it off.

## Research: what people use and what the evidence says

| Approach | Who uses it | Evidence | Tested here |
|---|---|---|---|
| Trend following (TSMOM, MA filters, breakouts) | CTAs, crypto funds, most TradingView/Freqtrade bots | Strongest. [Decade of trend following in crypto (arXiv 2009.12155)](https://arxiv.org/pdf/2009.12155): Sharpe ~0.5–1.5 at daily+ horizons, *no* profitable intraday trend on BTC spot. Liu & Tsyvinski 2021. [Zarattini et al. 2025](https://ideas.repec.org/p/chf/rpseri/rp2580.html) | TSMOM, vote ensemble, Donchian ensemble, SMA, SMA cross, + own variants |
| Cross-sectional / dual momentum rotation | Quant funds, rotation bots | [Liu, Tsyvinski & Wu 2022, JF](https://econpapers.repec.org/RePEc:bla:jfinan:v:77:y:2022:i:2:p:1133-1177) (gross, 2014–18); practitioner rotations warn that fees and correlated crashes hurt ([Quantpedia BTC/gold](https://quantpedia.com/dual-momentum-allocation-between-physical-gold-and-bitcoin-digital-gold/?a=6080)) | Rotation among BTC/ETH/SOL |
| Volatility management | Risk-parity / vol-target funds | Moreira & Muir 2017 (equities); crypto evidence is blog-grade ([Coinmonks](https://medium.com/coinmonks/whats-vol-got-to-do-with-it-886b57c2d762)) | Low-vol regime, TSMOM + low vol |
| Mean reversion (RSI(2), Bollinger) | Retail bots | Weak in crypto; a [49-strategy retail backtest](https://dev.to/maymay5692/i-backtested-49-crypto-trading-strategies-heres-every-single-result-4gg5) found all mean-reversion variants negative. No rigorous crypto RSI(2) study found | RSI(2) daily & 1h, Bollinger 1h, trend dip-buy |
| Grid bots | Retail exchanges' built-in bots | Work in ranges, bleed in trends; no rigorous study found | Single-slot 2% grid, 1h |
| DCA | Most retail | Not a trading strategy (no exits); not testable on these metrics | — |
| Funding-rate / basis carry | Market-neutral crypto funds | Strongest market-neutral evidence | **Dropped** — needs perp data; Binance excluded |

## Protocol (fixed before seeing holdout results)

- **Daily:** 13 families with 41 variants. Tuning window: 2021-01-01 → 2024-06-30. One variant per family is picked by its mean tuning-window Sharpe across the three coins, with the same parameters for every coin. That variant is run **once** on the holdout, 2024-07-01 → 2026-11-02.
- **Intraday:** 7 strategies with standard or live parameters (no tuning) on 1h bars, with 4h bars built from 1h exactly as the paper runner does. Window: 2026-09-04 → 2026-11-02. The live legs call `backtestceo.paper.strategies` directly.
- **Costs:** 0.25% Alpaca taker fee + 0.05% slippage per side. The grid bot uses resting limit orders, so 0.15% maker + 0.05%.
- **Fills:** next bar open. Long/flat unless marked L/S. Alpaca's 417-day SOL data hole is excluded.
- **Survival rules:**
  - ≥ 30 trades per coin over the full period.
  - Holdout Sharpe > 0 and expectancy > 0 on ≥ 2 of 3 coins.
  - Then either beats buy & hold holdout Sharpe ("edge") or cuts max drawdown by ≥ 15 points ("overlay").
  - Intraday: ≥ 30 trades and positive net expectancy on ≥ 2 of 3 coins.

## Survivors — holdout 2024-07-01 → 2026-11-02, net of fees

| Strategy (kind, chosen param) | Coin | Trades (holdout / full) | Win % | Exp %/trade | Max DD % | Sharpe | B&H Sharpe | B&H Max DD % |
|---|---|---|---|---|---|---|---|---|
| Dual-momentum rotation (practitioner, 28d, weekly) | BTC/ETH/SOL | 37 / 81 | 43.2 | +1.64 | −51.1 | 0.48 | 0.14 (equal-weight) | −64.3 |
| BTC-trend gate (own, BTC > SMA100) | BTC | 19 / 40 | 15.8 | +1.81 | −27.8 | 0.47 | 0.41 | −53.1 |
| | ETH | 19 / 40 | 15.8 | +4.13 | −43.0 | 0.39 | 0.07 | −67.6 |
| | SOL | 16 / 33 | 37.5 | +1.74 | −41.7 | 0.41 | 0.05 | −76.2 |
| TSMOM vote 10–90d, ≥ 3 of 5 (published) | BTC | 25 / 77 | 24.0 | +1.89 | −27.6 | 0.58 | 0.41 | −53.1 |
| | ETH | 33 / 81 | 33.3 | +1.47 | −51.0 | 0.42 | 0.07 | −67.6 |
| | SOL | 31 / 72 | 29.0 | +0.64 | −53.2 | 0.31 | 0.05 | −76.2 |
| TSMOM 28d (published) | BTC | 41 / 91 | 36.6 | +0.31 | −36.5 | 0.08 | 0.41 | −53.1 |
| | ETH | 37 / 91 | 32.4 | +0.58 | −41.9 | 0.21 | 0.07 | −67.6 |
| | SOL | 29 / 65 | 31.0 | +0.18 | −54.1 | 0.17 | 0.05 | −76.2 |
| SMA cross 10/30 (practitioner) | BTC | 19 / 45 | 26.3 | −0.57 | −39.8 | −0.23 | 0.41 | −53.1 |
| | ETH | 17 / 38 | 41.2 | +2.60 | −47.3 | 0.35 | 0.07 | −67.6 |
| | SOL | 14 / 34 | 42.9 | +2.08 | −50.7 | 0.29 | 0.05 | −76.2 |

Rejected daily strategies:
- **TSMOM + ATR trail, TSMOM + low vol, Trend dip-buy (own):** holdout positive on only 1 of 3 coins.
- **Weekly TSMOM:** SOL has only 28 trades.
- **Price > SMA200, Donchian ensemble, Low-vol regime, RSI(2):** fewer than 30 trades.

Full per-coin numbers and the whole tuning grid are in the tables file.

## Intraday (60 days, 1h / 4h) — all rejected

| Strategy | BTC trades / exp % | ETH trades / exp % | SOL trades / exp % | Verdict |
|---|---|---|---|---|
| SuperTrend + EMA200 + ADX 4h (live leg, L/S) | 5 / +0.13 | 5 / −0.47 | 3 / +6.14 | < 30 trades |
| EMA200 + ADX25 4h (live leg, L/S) | 12 / −1.30 | 11 / −0.98 | 8 / −0.35 | < 30 trades |
| EMA 9/21 1h + 2% stop (live leg) | 34 / −0.77 | 42 / −0.80 | 35 / −1.04 | loses on 3/3 |
| RSI(2) 1h, EMA200 filter | 22 / −0.65 | 24 / −0.72 | 24 / −0.72 | < 30 trades |
| Bollinger 20/2 1h reversion | 25 / −0.60 | 27 / −0.44 | 27 / −0.62 | < 30 trades |
| Donchian 20/10 4h breakout | 5 / −1.78 | 5 / −2.90 | 3 / −0.58 | < 30 trades |
| Grid bot, single slot 2% | 5 / −0.84 | 6 / −1.65 | 8 / −1.73 | < 30 trades |

Before fees, only 2 of 21 strategy–coin cells clear the 0.60% round trip: SuperTrend 4h on BTC (5 trades) and on SOL (3 trades). This matches the arXiv finding of no intraday trend edge on BTC spot.

## Caveats

- The holdout is 2.3 years of mostly falling alt prices. The survivors may be measuring "was in cash" rather than skill.
- After the 2023-06 → 2024-08 data hole, SOL signals restart cold: SMA/lookback warm-up eats months of the SOL holdout.
- 41 daily variants were tried. The deflated Sharpe accounts for that and says no survivor is distinguishable from the best of 41 lucky draws.
- Alpaca data quality issues from round 1 still apply: thin venue since 2023, outage jumps on 2025-12-02.
