# Copy picks: 2026-11-03

Command: `python -m kalshibot leaders --refresh --top 10 --write copy_config.json`.
Data: rivo.markets Kalshi leaderboard (201 traders) plus each trader's page, stats as of Nov 1–2, 2026.
kalshi.com blocks automated access (bot checkpoint) and the Kalshi API has no leaderboard endpoint.

Method: Rivo's 90-day "copy at $100 per bet" simulation, minus the taker fee (7% × (1−p) per $ staked) and
2¢ of slippage per contract. Traders are ranked by t-stat. Filters drop:
- market makers
- traders idle more than 14 days
- parlays over 15% of trades
- one win over 40% of profit
- under 40 simulated trades
- average entry outside 15–93¢
- simulated return over 100% (driven by longshots)
- under 60% of months green
- one month over 70% of profit

| Trader | 90d sim trades | Avg entry | Sim return | Net of fee+slip | t | Profit factor | Lifetime (Rivo) | Main category | Weight |
|---|---|---|---|---|---|---|---|---|---|
| whodis1 | 1171 | 34¢ | +33.7% | +23.2% | 5.70 | 1.53 | +$96.6K | NFL, MMA, boxing | 1.0 |
| old.cardinal6907 | 1121 | 31¢ | +26.5% | +15.2% | 3.42 | 1.41 | +$80.2K | NFL, MMA | 1.0 |
| hughman | 261 | 44¢ | +26.2% | +17.7% | 2.54 | 1.52 | +$46.4K | Cricket, soccer | 1.0 |
| silicon | 1064 | 50¢ | +14.4% | +6.9% | 2.24 | 1.30 | +$29.3K | Bitcoin | 1.0 |
| dontsleeponthedub | 96 | 55¢ | +26.6% | +19.8% | 2.14 | 1.73 | +$33.0K | WNBA, NBA | 1.0 |
| manimal2017 | 873 | 59¢ | +10.7% | +4.4% | 1.57 | 1.27 | +$45.2K | Bitcoin | 0.5 |
| breukinksepulveda3105 | 238 | 43¢ | +17.8% | +9.2% | 1.23 | 1.36 | +$27.0K | Tennis | 0.5 |

Big names that failed:

| Trader | Why |
|---|---|
| BWmarkets (#1, +$1.1M) | net copy return −2.1%; 3 of 9 months green |
| lost.buck | market maker; one win is 42% of profit |
| call.road | net +0.5%, t = 0.09 (noise) |
| hudson1234 | no recent trades to simulate; one month is 97% of profit |
| Wiseandstrong | net −5.1% |
| thebigdon | parlay-heavy; 99% of profit in October; average entry 91¢ |
| Unitdor (KalshiSpy #2) | net −3.8%; one win is 90% of tracked profit |

Lifetime profit doesn't predict copy profit.

Caveats:
- Only about 2–4 months of tracked history.
- Rivo's simulation has no fees or delay, so the 2¢ slippage is a guess. In-play sports (MMA, NFL) and
  short-dated Bitcoin markets can move more than 2¢ in the minutes a notification takes.
- These are past results, and survivorship applies.
- Paper-copy first; after 2–4 weeks, drop anyone whose copied P&L in `data/copy_journal.jsonl` is negative.
