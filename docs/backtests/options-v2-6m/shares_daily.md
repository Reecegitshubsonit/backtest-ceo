## Daily ETF signals on shares (6-month test)

Universe 18 ETFs. Train 2016-01-04..2026-05-04; test 2026-05-05..2026-11-02 (126 sessions). $5k per trade, max 5 open, $25k account, 2 bp/side cost, market-on-close fills.

| Strategy | Train trades | Train win % | Train exp $ | Train Sharpe | Test trades | Test win % | Test exp $ | Test total $ | Test max DD $ | Test Sharpe | Verdict |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| RSI(2) pullback in uptrend (Connors) (k=10) | 936 | 69.1% | 13.56 | 0.97 | 76 | 68.4% | 30.46 | 2315 | -922 | 2.41 | PASS |
| EMA200 trend + close below EMA5 by k% (EMA snap-back) (k=1.0) | 839 | 68.8% | 12.63 | 0.68 | 84 | 71.4% | 34.55 | 2902 | -891 | 3.04 | PASS |
| IBS < k in uptrend, 1-3 day hold (k=0.1) | 1845 | 62.1% | 7.62 | 0.85 | 130 | 56.2% | 13.03 | 1693 | -1040 | 1.45 | PASS |
| k down closes above EMA200 (k=3) | 1069 | 70.1% | 14.14 | 1.12 | 75 | 72.0% | 25.29 | 1897 | -804 | 2.17 | PASS |
| RSI(2) < k AND IBS < 0.25 in uptrend (k=10) | 760 | 68.0% | 14.11 | 0.91 | 59 | 72.9% | 55.54 | 3277 | -261 | 3.42 | PASS |
| RSI(14) < k above EMA50 (trend pullback) (k=45) | 192 | 63.0% | 12.10 | 0.29 | 9 | 77.8% | 75.37 | 678 | -191 | 2.31 | FAIL |
