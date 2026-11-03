## Daily ETF signals on shares (replacement for the dead intraday share signals)

Universe 18 ETFs. Train 2016-01-04..2026-08-04; test 2026-08-05..2026-11-02 (63 sessions). $5k per trade, max 5 open, $25k account, 2 bp/side cost, market-on-close fills.

| Strategy | Train trades | Train win % | Train exp $ | Train Sharpe | Test trades | Test win % | Test exp $ | Test total $ | Test max DD $ | Test Sharpe | Verdict |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| RSI(2) pullback in uptrend (Connors) (k=10) | 974 | 69.7% | 15.88 | 1.13 | 38 | 57.9% | -3.26 | -124 | -922 | -0.28 | FAIL |
| EMA200 trend + close below EMA5 by k% (EMA snap-back) (k=1.0) | 891 | 69.5% | 15.31 | 0.85 | 33 | 57.6% | 1.18 | 39 | -891 | 0.09 | FAIL |
| IBS < k in uptrend, 1-3 day hold (k=0.1) | 1916 | 62.0% | 7.91 | 0.87 | 58 | 55.2% | 17.16 | 995 | -559 | 3.07 | PASS |
| k down closes above EMA200 (k=3) | 1109 | 70.5% | 15.81 | 1.25 | 35 | 62.9% | -7.19 | -252 | -804 | -0.62 | FAIL |
| RSI(2) < k AND IBS < 0.25 in uptrend (k=10) | 786 | 68.4% | 16.77 | 1.04 | 33 | 69.7% | 27.37 | 903 | -261 | 3.05 | PASS |
| RSI(14) < k above EMA50 (trend pullback) (k=45) | 196 | 63.8% | 15.16 | 0.36 | 5 | 60.0% | 6.10 | 31 | -191 | 0.24 | FAIL |
