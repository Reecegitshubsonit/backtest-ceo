"""Regenerates the parity fixtures from the real backtest.py (needs its pandas venv):
    /workspace/backtests/.venv/bin/python engine/tests/fixtures/paper/make_fixtures.py [/workspace/backtests]
Writes sample bars (CSV) and the signals/trades backtest.py produces on exactly those bars."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
BT = sys.argv[1] if len(sys.argv) > 1 else '/workspace/backtests'
sys.path.insert(0, BT)
import pandas as pd
import backtest as B


def save(df, name):
    df[['open', 'high', 'low', 'close', 'volume']].to_csv(f'{HERE}/{name}.csv', index_label='ts')


def sigs(le, lx, se=None, sx=None):
    n = len(le)
    f = lambda s: [bool(x) for x in (s.values if s is not None else [False] * n)]
    return dict(le=f(le), lx=f(lx), se=f(se), sx=f(sx))


def trades(tr):
    return [{k: t[k] for k in ('entry_time', 'exit_time', 'side', 'entry', 'exit') + (('contracts',) if 'contracts' in t else ())} for t in tr]


out = {}
eth = pd.read_csv(f'{BT}/data/ETHUSD_1h.csv', parse_dates=['ts'], index_col='ts')
eth = eth[eth.index >= pd.Timestamp('2025-08-01', tz='UTC')]
save(eth, 'eth_1h')
eth4 = eth.resample('4h').agg({'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'}).dropna()
out['eth4h_bars'] = len(eth4)
# alphainsider signals, recomputed exactly as s_alphainsider does
e = B.ema(eth4.close, 200); pdi, mdi, adx = B.dmi(eth4, 14)
out['alphainsider'] = dict(signals=sigs((eth4.close > e) & (adx > 25) & (pdi > mdi), (eth4.close < e) | (mdi > pdi),
                                         (eth4.close < e) & (adx > 25) & (mdi > pdi), (eth4.close > e) | (pdi > mdi)),
                           trades=trades(B.s_alphainsider(eth4)[1]))
d = B.supertrend(eth4, 10, 3.0); e = B.ema(eth4.close, 200); _, _, adx = B.dmi(eth4, 14)
out['supertrend'] = dict(signals=sigs((d == 1) & (eth4.close > e) & (adx > 20), d == -1, (d == -1) & (eth4.close < e) & (adx > 20), d == 1),
                         trades=trades(B.s_supertrend(eth4)[1]))
btc = pd.read_csv(f'{BT}/data/BTCUSD_1h.csv', parse_dates=['ts'], index_col='ts')
btc = btc[btc.index >= pd.Timestamp('2026-06-01', tz='UTC')]
save(btc, 'btc_1h')
f, s = B.ema(btc.close, 9), B.ema(btc.close, 21)
out['emacross'] = dict(signals=sigs((f > s) & (f.shift() <= s.shift()), (f < s) & (f.shift() >= s.shift())),
                       trades=trades(B.s_emacross(btc)[1]))
qqq = B.load_yf('QQQ', '5m', 'America/New_York')
save(qqq, 'qqq_5m')
out['first5m_qqq'] = dict(trades=trades(B.s_first5m(qqq, pt=1.0, cost_side=0.01, max_lev=4)[1]))
json.dump(out, open(f'{HERE}/expected.json', 'w'), indent=0, default=str)
print({k: (len(v['trades']) if isinstance(v, dict) else v) for k, v in out.items()})
