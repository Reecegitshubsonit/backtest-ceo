# Strategy search results

Decision rows: 639,376. Parameter space: 34,214,400; combinations searched: 100,000.

| split | from | to | events |
|---|---|---|---|
| search | 2026-10-03 | 2026-10-21 | 29809 |
| validate | 2026-10-22 | 2026-10-28 | 14304 |
| holdout | 2026-10-29 | 2026-11-04 | 14384 |

| | real data | shuffled outcomes (luck) |
|---|---|---|
| combos with >= 30 events and positive mean (search) | 1,603 | 676 |
| best search t | 36.07 | 2.07 |
| combos with search t > 3 | 18 | 0 |
| top-200 that stayed profitable on validation | 72 | 33 |
| rejected by neighbour check | 0 | 2 |
| finalists sent to holdout | 10 | 10 |

## Finalists on the holdout (tested once)

| # | strategy | search t | validate t | holdout events | holdout mean/event | holdout t | DSR | tail check (all splits) |
|---|---|---|---|---|---|---|---|---|
| 1 | no 0.95-0.98, 6h, Economics, vol>=0, spread<=0.1, mom follow 0.02/6h, hold, size 50 | 36.07 | 29.28 | 12 | +3.4% | 14.88 | 1.00 | 0/105 lost vs 3.8% break-even, p=0.02 |
| 2 | no 0.95-0.98, 12h, Sports, vol>=0, spread<=0.05, mom follow 0.02/6h, hold, size 10 | 26.61 | 18.38 | 13 | +3.6% | 18.27 | 1.00 | 0/67 lost vs 3.6% break-even, p=0.08 |
| 3 | no 0.90-0.98, 1h, Economics, vol>=0, spread<=0.03, mom follow 0.05/6h, hold, size 10 | 18.62 | 13.27 | 14 | -2.5% | -0.33 | 1.00 | 1/64 lost vs 4.1% break-even, p=0.26 |
| 4 | yes 0.95-0.98, 12h, Sports, vol>=0, spread<=0.05, mom follow 0.05/24h, hold, size 1 | 18.26 | 11.04 | 16 | +2.9% | 15.07 | 1.00 | 0/64 lost vs 2.8% break-even, p=0.16 |
| 5 | no 0.90-0.98, 1h, Financials, vol>=0, spread<=0.1, mom follow 0.02/6h, tp 0.20 / sl 0.10, size 10 | 7.01 | 12.57 | 20 | -2.3% | -0.42 | 0.22 | n/a (early exit) |
| 6 | yes 0.10-0.90, 1h, Mentions, vol>=1000, spread<=0.03, mom none, hold, size 10 | 2.33 | 1.86 | 15 | +45.3% | 1.72 | 0.00 | 28/78 lost vs 44.9% break-even, p=0.07 |
| 7 | no 0.90-0.98, 12h, all, vol>=1000, spread<=0.03, mom follow 0.02/6h, hold, size 10 | 1.84 | 3.73 | 81 | +1.3% | 0.57 | 0.00 | 10/292 lost vs 5.2% break-even, p=0.10 |
| 8 | yes 0.50-0.80, 1h, Mentions, vol>=0, spread<=0.1, mom none, tp 0.20 / sl 0.10, size 50 | 1.87 | 1.81 | 22 | +4.4% | 0.33 | 0.00 | n/a (early exit) |
| 9 | no 0.10-0.95, 6h, Climate and Weather, vol>=1000, spread<=0.05, mom follow 0.05/6h, tp 0.05 / sl 0.05, size 10 | 1.71 | 4.19 | 8 | +39.1% | 1.21 | 0.00 | n/a (early exit) |
| 10 | no 0.35-0.95, 6h, Climate and Weather, vol>=1000, spread<=0.03, mom none, tp 0.20 / sl 0.10, size 10 | 2.13 | 1.69 | 11 | -10.8% | -0.91 | 0.00 | n/a (early exit) |

## Same pipeline on shuffled outcomes

| # | strategy | search t | validate t | holdout events | holdout mean/event | holdout t | DSR | tail check (all splits) |
|---|---|---|---|---|---|---|---|---|
| 1 | yes 0.05-0.50, 6h, Sports, vol>=10000, spread<=0.01, mom fade 0.05/24h, hold, size 50 | 0.95 | 1.16 | 16 | -29.3% | -1.41 | 0.24 | 37/81 lost vs 34.1% break-even, p=0.99 |
| 2 | yes 0.02-0.50, 6h, Sports, vol>=10000, spread<=0.02, mom fade 0.05/24h, hold, size 50 | 0.90 | 0.98 | 25 | -22.1% | -1.21 | 0.16 | 50/107 lost vs 33.7% break-even, p=1.00 |
| 3 | yes 0.20-0.80, 3h, all, vol>=10000, spread<=0.02, mom follow 0.10/24h, hold, size 10 | 1.21 | 0.81 | 25 | -16.5% | -0.72 | 0.23 | 53/117 lost vs 35.8% break-even, p=0.99 |
| 4 | no 0.02-0.80, 96h, Sports, vol>=100, spread<=0.1, mom follow 0.02/6h, hold, size 50 | 0.90 | 0.79 | 14 | -28.3% | -1.44 | 0.25 | 29/87 lost vs 24.9% break-even, p=0.97 |
| 5 | yes 0.10-0.35, 3h, Sports, vol>=10000, spread<=0.03, mom fade 0.05/6h, hold, size 50 | 0.78 | 0.78 | 25 | -8.4% | -0.36 | 0.11 | 62/107 lost vs 36.4% break-even, p=1.00 |
| 6 | no 0.05-0.90, 12h, Sports, vol>=100, spread<=0.03, mom follow 0.05/6h, hold, size 50 | 0.73 | 0.74 | 30 | -19.5% | -1.45 | 0.06 | 54/155 lost vs 22.0% break-even, p=1.00 |
| 7 | no 0.02-0.65, 3h, Financials, vol>=0, spread<=0.05, mom fade 0.02/6h, hold, size 1 | 0.65 | 0.86 | 21 | +10.6% | 0.54 | 0.06 | 48/147 lost vs 26.0% break-even, p=0.97 |
| 8 | yes 0.05-0.50, 6h, Sports, vol>=10000, spread<=0.03, mom fade 0.05/24h, hold, size 1 | 0.64 | 1.07 | 24 | -27.8% | -1.54 | 0.11 | 50/108 lost vs 33.6% break-even, p=1.00 |
| 9 | no 0.02-0.65, 1h, Politics, vol>=1000, spread<=0.05, mom none, tp 0.20 / sl 0.10, size 10 | 0.74 | 0.63 | 12 | -18.0% | -1.17 | 0.23 | n/a (early exit) |
| 10 | no 0.02-0.80, 3h, Financials, vol>=0, spread<=0.1, mom fade 0.05/6h, hold, size 10 | 0.61 | 0.87 | 31 | -15.3% | -1.03 | 0.04 | 73/197 lost vs 24.0% break-even, p=1.00 |

## Earlier strategies on the same holdout

| strategy | events | mean/event | t |
|---|---|---|---|
| favorite 80-95c, 24h, hold (kalshibot paper strategy, taker) | 636 | +3.7% | 3.28 |
| favorite 50-80c weather, 24h, hold (weather market-only idea) | 156 | -0.2% | -0.03 |
| longshots 2-10c, 24h, hold (typical retail) | 1137 | -68.3% | -10.30 |
| copy trading (Rivo picks) | not testable: Kalshi data has no trader identities | | |
| weather forecast models (GFS/ECMWF, NBM) | separate backtests: -15% to -24% ROI, model Brier worse than market | | |

## Verdict

3 finalist(s) passed holdout t >= 2 and DSR >= 0.95 but failed the tail check: they buy near-certain sides, have too few events for a loss to be expected, and their loss count is not significantly below break-even (needs p < 0.005: 0.05 Bonferroni-split over 10 finalists). Their t-stats come from the lack of losses so far, not from an edge.
Nothing survives.

## Notes

- Order book history: Kalshi has none (only the current book and live websocket/FIX deltas). Spread and fills come from hourly candlestick bid/ask; entries pay the ask plus the taker fee (rounded up per order).
- Data: the live window only (markets settled since the 2026-09-05 historical cutoff, ~2 months). Older markets sit in the archive endpoint at one request per market and were not downloaded, so the holdout is one week.
- The tail check was added after the holdout was seen, because finalists 1, 2 and 4 had zero losses. It does not change any holdout number; it only stops a no-loss streak on 96c favourites from counting as proof.
- Broad 95-98c favourites (all categories, spread <= 5c) lose 0.4-1.7% per trade after fees: their loss rate (4-5%) is at or above break-even (~4%).
- The old favourite 80-95c strategy is not stable: search -0.1% (t -0.1), validate -4.2% (t -2.5), holdout +3.7% (t 3.3).
- The bot stays read-only/paper for these strategies; nothing here places orders.
