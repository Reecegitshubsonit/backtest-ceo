## Round-5 fixes inside the search (search + validate splits only)

SPY Sharpe: search 0.64, validate 1.23. Percentile = rank of search Sharpe within its family.

| Variant | Search Sharpe | Validate Sharpe | Family percentile (search) | Beats SPY on both |
|---|---:|---:|---:|---|
| N1 vol target (original) | 0.78 | 1.14 | 92 | no |
| H1a N1 cap 1.5x | 0.79 | 1.15 | 95 | no |
| H1b N1 slower re-lever (63d vol) | 0.69 | 1.12 | 79 | no |
| H1c N1 wider band (20 pts) | 0.82 | 1.10 | 98 | no |
| H1 all three | 0.59 | 1.22 | 47 | no |
| I1b noise band (original) | 1.16 | 1.85 | 87 | yes |
| H2 skip quiet regime | 1.29 | 0.77 | 94 | no |
| H3 no entries after 12:30 | 0.86 | 1.73 | 52 | yes |
| H2+H3 | 0.99 | 1.08 | 70 | no |
| I2b ORB QQQ (original) | 0.68 | 0.17 | 86 | no |
| H4a ORB short-only | 0.46 | 0.44 | 72 | no |
| H4b ORB with gap direction | 0.67 | 0.78 | 85 | no |
| H2 ORB skip quiet regime | 0.51 | 0.08 | 76 | no |
| SMA200 (original) | 0.66 | 0.95 | 87 | no |
| Trend: faster re-entry, 50/200 cross | 0.49 | 1.35 | 61 | no |
| Trend: SMA100 | 0.82 | 1.03 | 99 | no |
