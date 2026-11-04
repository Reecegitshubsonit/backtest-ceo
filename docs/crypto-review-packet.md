# Crypto strategy review packet

For an independent reviewer. Self-contained: rules, data, costs, results, every test run, known problems and open questions.
Repo `reecegitshubsonit/backtest-ceo`, branch `claude/gracious-archimedes-aiuy3u`, commit `b066385` (2026-11-04).

## 1. What we want from the reviewer

1. Find look-ahead, survivorship or accounting errors in the rules and the simulator (Section 7).
2. Judge whether any strategy below is worth paper-trading, given how many configurations were tried (Section 5).
3. Say what we should test next, or stop doing.

## 2. Setup used everywhere

- **Assets:** BTC/USD, ETH/USD, SOL/USD spot. Long only (Alpaca spot cannot short) unless marked L/S.
- **Data:** Alpaca crypto bars (`data.alpaca.markets/v1beta3/crypto/us`), daily and 1h, 2021-01-01 → 2026-11-02. 4h bars are built from 1h, anchored at midnight UTC. Daily bars are UTC days.
- **Fills:** the signal is computed at a bar's close; the trade fills at the **next bar's open**. Full equity per position, no leverage.
- **Costs:** 0.60% round trip (0.25% Alpaca taker + 0.05% slippage per side), unless stated. Round 4 used 0.30% (maker 0.15% per side, fill risk not modelled).
- **Metrics:**
  - Expectancy: mean net return per trade.
  - Sharpe: daily returns × √365, flat days count as 0, risk-free 0 unless stated.
  - Max drawdown: on compounded equity.
- **Rule from the brief:** reject any strategy with fewer than 30 trades.

## 3. Best strategies (none statistically proven)

### A. TSMOM 28d — the most consistent result across all rounds

- **Rule:** at each daily close, long if close / close 28 days earlier − 1 > 0, else flat. Fill at the next daily open.
- **Source:** Liu & Tsyvinski (2021), *Risks and Returns of Cryptocurrency*, RFS.

**Full period 2021-01-01 → 2026-11-02, 0.60% round trip.**

| Coin | Trades | Win % | Exp %/trade | Max DD | Sharpe | CAGR | B&H Sharpe | B&H Max DD | B&H CAGR |
|---|---|---|---|---|---|---|---|---|---|
| BTC | 91 | 35.2 | +2.11 | −49.0% | 0.78 | 24.9% | 0.57 | −76.7% | 17.8% |
| ETH | 91 | 36.3 | +1.62 | −57.0% | 0.52 | 14.7% | 0.63 | −79.3% | 21.2% |
| SOL* | 65 | 36.9 | +11.26 | −64.2% | 1.31 | — | 0.91 | −96.9% | — |

\* SOL has a 417-day data hole (Section 6). Returns across the hole are excluded, which leaves about 4.7 years of SOL bars.

**Sub-periods.**

| Coin | Last 2y trades | Last 2y exp % | Last 2y Sharpe (B&H) | Notes |
|---|---|---|---|---|
| BTC | 35 | −0.38 | 0.44 (0.34) | |
| ETH | 29 | +2.13 | 0.67 (0.28) | < 30 trades |
| SOL | 28 | −1.28 | 0.10 (0.01) | < 30 trades. SOL from 2022 on: 52 trades, +0.55%, Sharpe 0.28 vs B&H −0.33 |

**Robustness checks.**
- **Fill timing (BTC / ETH / SOL Sharpe):**
  - Fill at the signal bar's own close: 0.776 / 0.513 / 1.309.
  - Next open: 0.777 / 0.524 / 1.308.
  - One full bar late: 0.622 / 0.593 / 1.107.
- **Idle cash at the T-bill rate:** +1.7 to +2.9 pp CAGR; no conclusion changes.
- **Paired block bootstrap, Sharpe(TSMOM) − Sharpe(B&H), 95% CI:** BTC +0.21 [−0.41, 0.80]; ETH −0.11 [−0.76, 0.56]; SOL +0.40 [−0.29, 1.10]. **All include 0.**
- **Round 3 holdout (2025-09-03 → 2026-11-02, a bear market), 0.60%:**
  - TSMOM: BTC −3.9% (Sharpe 0.00, DD −24%), ETH −24.8% (−0.58, −37%), SOL −30.9% (−0.65, −52%).
  - Buy & hold: −31%, −48%, −56%.
- **2023 → 2026-11 at 0.30% round trip (round 4 reference):**

| Coin | TSMOM return | TSMOM Sharpe | TSMOM max DD | B&H return | B&H Sharpe | B&H max DD |
|---|---|---|---|---|---|---|
| BTC | +296% | 1.21 | −36.4% | +364% | 1.09 | −53.1% |
| ETH | +104% | 0.65 | −46.3% | +88% | 0.57 | −67.6% |
| SOL | +33% | 0.46 | −50.3% | +26% | 0.42 | −76.2% |

**Reading:** a drawdown cutter with Sharpe at or slightly above buy & hold. The advantage is concentrated in big trend years (2021, 2023) and is not significant.

### B. TSMOM vote 10–90d

- **Rule:** lookbacks of 10, 20, 40, 60 and 90 days; long if at least 3 of the 5 trailing returns are positive, else flat. Daily, next open.
- **Selection:** the threshold was chosen from {3, 4, 5} on 2021-01 → 2024-06, then run once on the holdout 2024-07-01 → 2026-11-02 (0.60% round trip).

| Coin | Holdout trades (full) | Win % | Exp % | Max DD | Sharpe | B&H Sharpe | B&H Max DD | Deflated Sharpe |
|---|---|---|---|---|---|---|---|---|
| BTC | 25 (77) | 24.0 | +1.89 | −27.6% | 0.58 | 0.41 | −53.1% | 0.36 |
| ETH | 33 (81) | 33.3 | +1.47 | −51.0% | 0.42 | 0.07 | −67.6% | 0.27 |
| SOL | 31 (72) | 29.0 | +0.64 | −53.2% | 0.31 | 0.05 | −76.2% | 0.22 |

Bootstrap CIs on the Sharpe difference vs B&H all include 0 (BTC [−0.87, 1.08]).

### C. Dual-momentum rotation BTC / ETH / SOL, 28d, weekly

- **Rule:** at each Monday close, take the trailing 28-day return of each coin. Hold the best one if its return is > 0, otherwise cash. Fill at the next open. A coin with no bar that day is ineligible.
- **Selection:** the 28-day lookback was chosen from {14, 28, 56} on 2021-01 → 2024-06.
- **Holdout 2024-07 → 2026-11-02, 0.60%:**
  - 37 trades (81 over the full period), win 43.2%, +1.64% per trade, max DD −51.1%, Sharpe 0.48.
  - Equal-weight B&H: Sharpe 0.14, max DD −64.3%.
  - Bootstrap CI on the Sharpe difference [−0.60, 1.17]. Deflated Sharpe 0.30.
- The only strategy that clears 30 trades inside its holdout.

### D. BTC-trend gate (own design)

- **Rule:** hold the coin while BTC's daily close > BTC SMA100, else flat. Same rule for each coin.
- **Selection:** SMA length chosen from {50, 100, 200}.
- **Holdout 2024-07 → 2026-11-02 (holdout trades / full-period trades):**
  - BTC: 19 / 40 trades, win 15.8%, +1.81%, DD −27.8%, Sharpe 0.47 (B&H 0.41).
  - ETH: 19 / 40, +4.13%, DD −43.0%, Sharpe 0.39 (B&H 0.07).
  - SOL: 16 / 33, +1.74%, DD −41.7%, Sharpe 0.41 (B&H 0.05).
- Fails the 30-trade rule inside the holdout.

### E. SuperTrend confluence 4h, ETH (live paper leg, long only)

- **Rule:** on 4h bars, long when SuperTrend(ATR 10, ×3) points up AND close > EMA200 AND ADX(14) > 20. Exit when SuperTrend flips down. Fill at the next 4h open.
- **Selection:** parameters were set in earlier work on overlapping data, so this is **not a clean out-of-sample test**.

| Window | Trades | Win % | Exp % | Max DD | Sharpe | B&H Sharpe |
|---|---|---|---|---|---|---|
| ETH 2021-03 → 2026-11 | 96 | 39.6 | +1.79 | −38.9% | 0.67 | 0.46 |
| ETH last 2y | 32 | 37.5 | +1.69 | −37.1% | 0.63 | 0.28 |
| BTC 2021-03 → | 106 | 34.9 | +0.51 | −44.4% | 0.24 | 0.41 |
| BTC last 2y | 40 | 35.0 | −0.20 | −42.8% | −0.19 | 0.34 |
| SOL 2021-03 → | 74 | 36.5 | +1.69 | −88.1% | 0.23 | 0.49 |
| SOL last 2y | 32 | 40.6 | +0.65 | −44.3% | 0.30 | 0.01 |

## 4. What failed (needed to judge the survivors)

- **Round 1** (5 published strategies):
  - Donchian 20/10 had too few trades.
  - Abnormal-day momentum was destroyed by costs.
  - Intraday first→last half-hour momentum and 21–23 UTC seasonality made about 0% per trade before costs on 60 days of 30m bars.
- **Round 2** (13 daily families, 41 variants, tuned 2021-01 → 2024-06, holdout 2024-07 → 2026-11, plus 7 intraday strategies on 60 days):
  - Passed the brief's rules: B, C, D, TSMOM 28d and SMA cross 10/30.
  - Rejected: price > SMA, Donchian ensemble, low-vol regime, RSI(2), and three own designs.
  - All 7 intraday strategies failed. The EMA 9/21 1h live leg lost on all three coins, even before fees, and is now disabled.
- **Round 3** (100,000 random combinations from a 2.03M space):
  - Space: 1h / 4h / 1d; 30 entries including candle patterns and volume; trend, volatility, volume, time-of-day and day-of-week filters; holding period; ATR stop and target.
  - Split 60 / 20 / 20: 16 passed validation, 7 passed the neighbour check, and all 7 lost on BTC or ETH in the holdout or had < 30 trades. Deflated Sharpe 0.00.
  - The same pipeline on 10 shuffled datasets found as many "winners", which scored higher in validation.
  - Cost diagnosis: 36% of combos made money on both coins before costs, 2.9% after.
- **Round 4** (100,000 combinations, walk-forward 2023–2026; alpha information ratio vs buy & hold; at most 15 trades a year; 0.30% round trip):
  - Out-of-sample alpha IR: BTC −0.54, ETH −1.02 (CI entirely below 0), SOL −0.39.
  - No better than 5 shuffled runs.

## 5. Multiple-testing ledger (be suspicious)

About 200,000+ configurations were looked at in total: 5 + 48 + 100,000 (+ neighbours) + 100,000, plus fill, cost and period variants.

- Strategies B, C and D were chosen from small grids (3–4 values each) inside a 41-variant round.
- TSMOM 28d was fixed from the literature before any testing, the least selection of anything here, but it has been looked at in every round.
- Round 4's design was chosen after seeing round 3's holdout (Sep 2025 – Nov 2026).

**No untouched data remains. Forward paper trading is the only clean test.**

## 6. Known data problems

- **SOL hole:** Alpaca SOL/USD has no bars from 2023-06-29 to 2024-08-25 (417 days). The scripts split at holes > 2–5 days and never book returns across them. Earlier SOL numbers that ignored the hole were wrong and have been corrected.
- **Thin venue:** Alpaca's crypto venue has a median of a few hundred trades a day since 2023, versus about 50k a day in 2021–22, so the data source changed. Volume-based features are unreliable after 2022.
- **Outage jumps:** opens jump up to 6–10% versus the prior close on 2025-12-02 (all coins), likely an Alpaca outage.
- **No cross-venue check:** Coinbase and Binance were unreachable (network policy, or excluded by choice). One live spot check against Robinhood matched within 0.015%.
- **No Level 2:** Alpaca has no historical order-book data.
- **Unmodelled costs:** maker-order fill risk, funding (no shorts are traded), and taxes.

## 7. Simulator (daily strategies), verbatim

```python
def simulate(d, sig, side_cost, fill="next_open", rf=None):
    """Event simulation of a daily signal. sig[i] is computed from bar i (uses its close).
    fill: "next_open"  -> trade at the open of bar i+1 (default, realistic)
          "next_close" -> trade at the close of bar i+1 (one full bar of lag, stress test)
          "same_close" -> trade at the close of bar i (look-ahead-ish: the signal bar's own close)
    rf: optional daily cash return series (index = d.index) earned on idle equity when flat.
    Returns (trade returns, daily equity returns, held position per bar)."""
    o, c = d["o"].values, d["c"].values
    s = np.nan_to_num(np.asarray(sig, float))
    n = len(c)
    tgt = np.zeros(n)  # target applied at bar j's fill
    if fill == "same_close":
        tgt[:] = s
    else:
        tgt[1:] = s[:-1]
    at_open = fill == "next_open"
    r_cash = np.zeros(n) if rf is None else rf.reindex(d.index).ffill().fillna(0).values
    E, u, mark = 1.0, 0.0, c[0]
    eq, held, trades = np.empty(n), np.empty(n), []
    cur, entry = 0.0, None
    for j in range(n):
        if u == 0:
            E *= 1 + r_cash[j]
        px = o[j] if at_open else c[j]
        if tgt[j] != cur:
            E += u * (px - mark)
            mark = px
            if cur != 0:
                trades.append(cur * (px / entry - 1) - 2 * side_cost)
            new_u = tgt[j] * E / px
            E -= abs(new_u - u) * px * side_cost
            u, cur, entry = new_u, tgt[j], px
        E += u * (c[j] - mark)
        mark = c[j]
        eq[j], held[j] = E, cur
    if cur != 0:
        trades.append(cur * (c[-1] / entry - 1) - 2 * side_cost)
    daily = pd.Series(eq, d.index).pct_change().fillna(0)
    return trades, daily, pd.Series(held, d.index)
```

Notes for checking:
- `sig[i]` uses only data up to bar i's close.
- `tgt` is shifted by one bar, so position changes happen at bar i+1's open.
- The fee is charged on traded notional per side. The trade's own return also subtracts 2 × side cost.
- `segments()` splits at data holes; each segment is simulated separately and the first-day return of a later segment is zeroed.
- The round 3/4 numba kernel was checked against a plain-Python reimplementation of one combination (780 trades, identical expectancy).

## 8. Questions for the reviewer

1. Any look-ahead in TSMOM (`pct_change(28)` on the close, fill at the next open) or in the rotation (Monday close → Tuesday open)?
2. Is a Sharpe of 0.5–1.3 with drawdowns of 40–60% on a 2-trades-a-month rule worth trading, versus simply holding a smaller buy & hold position?
3. Given the ledger in Section 5, is there any defensible reason to prefer B, C or D over plain TSMOM 28d?
4. Is the 0.30% maker-cost assumption realistic for a daily rule on Alpaca? What fill rate should be assumed?
5. What non-price data (funding, basis, open interest, on-chain) is most likely to add real information, and from which non-Binance source?

## 9. Reproduce

All scripts are in `engine/scripts/`. Cached bars go to `engine/.cache/` (git-ignored). The data API needs Alpaca keys or an auth proxy.

```bash
python engine/scripts/crypto_edge_backtest.py --out docs/crypto-edge-results-tables.md   # round 1 (+ fills, B&H, bootstrap, T-bill)
python engine/scripts/crypto_edge_round2.py --out docs/crypto-edge-round2-tables.md      # round 2
python engine/scripts/live_legs_4h.py --end 2026-11-02 --out docs/live-legs-4h-tables.md # live 4h legs
python engine/scripts/crypto_search.py --end 2026-11-02 --out docs/crypto-search-tables.md  # round 3
python engine/scripts/crypto_search_wf.py --end 2026-11-02 --out docs/crypto-search-wf-tables.md  # round 4
```

Write-ups:
- `docs/crypto-edge-results.md`
- `docs/crypto-edge-round2.md`
- `docs/crypto-search-results.md`
- `docs/crypto-search-wf.md`
