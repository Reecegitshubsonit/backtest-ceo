"""Stock-strategy fixtures + per-symbol reference stats from the real backtest_alpaca.py (needs its pandas venv and alpaca_data/):
    /workspace/backtests/.venv/bin/python engine/tests/fixtures/paper/make_stock_fixtures.py [/workspace/backtests]
Writes <sym>_1d.csv / <sym>_5m.csv samples, stocks_expected.json (what backtest_alpaca produces on exactly those bars) and
adds alpaca_<strategy>_<SYM> runs to backtestceo/paper/reference_results.json (full-history stats, not the sample)."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
BT = sys.argv[1] if len(sys.argv) > 1 else '/workspace/backtests'
sys.path.insert(0, BT)
import numpy as np, pandas as pd
import backtest_alpaca as B

REF = os.path.join(HERE, '..', '..', '..', 'backtestceo', 'paper', 'reference_results.json')
SETS = dict(sip=['PLTR', 'TSLA', 'ARKK'], rsi2=['SMH', 'AMD'], overnight=['NVDA', 'MSTR', 'LLY'])
NAMES = dict(sip='Stocks-in-Play 5-min ORB', rsi2='RSI(2) Pullback', overnight='Overnight Hold')
D_FROM, D_TO = pd.Timestamp('2023-01-01'), pd.Timestamp('2026-09-05')
M_TO = pd.Timestamp('2026-09-05', tz=B.NY)
M_FROM = dict(sip=pd.Timestamp('2026-08-03', tz=B.NY), rsi2=pd.Timestamp('2026-08-31', tz=B.NY), overnight=pd.Timestamp('2026-08-31', tz=B.NY))
alpaca = json.load(open(f'{BT}/results_alpaca.json'))
fam = {s['id']: s for s in alpaca['strategies']}


def save(df, name, daily):
    o = df[['open', 'high', 'low', 'close', 'volume']].copy()
    o.index = (o.index.tz_localize(B.NY) if daily else o.index).map(lambda t: t.isoformat())
    o.to_csv(f'{HERE}/{name}.csv', index_label='ts')


exp, runs = {}, []
END = pd.Timestamp('2100-01-01')
for kind, syms in SETS.items():
    for sym in syms:
        dd = B.load_daily(sym); x5 = B.load_intraday(sym)
        # ---- sample fixtures + what backtest_alpaca does on them
        dfx = dd[(dd.index >= D_FROM) & (dd.index < D_TO)]
        save(dfx, f'{sym.lower()}_1d', True)
        m5 = x5[(x5.index >= M_FROM[kind]) & (x5.index < M_TO)]
        save(m5, f'{sym.lower()}_5m', False)
        if kind == 'rsi2':
            _, t = B.run_rsi2(sym, dfx)
            exp[f'rsi2_{sym}'] = [str(d.date()) for d in t.index]
        elif kind == 'sip':
            # include 14 sessions of first-bar history + the daily context exactly as run_intraday sees it
            t = B.run_intraday(sym, m5, dfx, 'sip')
            exp[f'sip_{sym}'] = [] if t is None else [dict(date=str(d.date()), ret=float(r.ret), side=int(r.side)) for d, r in t.iterrows()]
        # ---- full-history reference stats for the wall screen / Backtester agent
        if kind == 'rsi2': daily, t = B.run_rsi2(sym, dd)
        elif kind == 'overnight': daily, t = B.run_overnight(sym, dd)
        else:
            t = B.run_intraday(sym, x5, dd, 'sip'); daily = B.to_daily(t, dd)
        daily = daily[daily.index >= pd.Timestamp('2016-01-01')]
        full = B.stats(daily, t, B.IS_START, END, dd.close)
        eq = (1 + daily[daily.index >= B.IS_START]).cumprod()
        pts = eq.iloc[np.linspace(0, len(eq) - 1, 80).astype(int)]
        tt = t[t.index >= B.IS_START].tail(8)
        F = fam[f'alpaca_{kind}']
        runs.append(dict(id=f'alpaca_{kind}_{sym}', name=f"{NAMES[kind]} · {sym}", market=f'{sym} · Webull sandbox paper',
                         tuned=False, source='Alpaca SIP bars via data.alpaca.markets (backtest_alpaca.py)', rules=F['rules'],
                         full=full, split_date='2024-01-01', in_sample=B.stats(daily, t, B.IS_START, B.OOS_START, dd.close),
                         out_of_sample=B.stats(daily, t, B.OOS_START, END, dd.close),
                         equity_curve=[dict(date=str(d.date()), equity=round(float(v), 4)) for d, v in pts.items()],
                         last_trades=[dict(entry_time=str(d.date()), exit_time=str(d.date()), side='long' if int(r.get('side', 1)) > 0 else 'short',
                                           entry=None, exit=None, ret=round(float(r.ret), 5)) for d, r in tt.iterrows()]))
json.dump(exp, open(f'{HERE}/stocks_expected.json', 'w'), indent=0)
ref = json.load(open(REF))
ref['strategies'] = [r for r in ref['strategies'] if not r['id'].startswith('alpaca_')] + runs
json.dump(ref, open(REF, 'w'), indent=1, default=str)
print({k: len(v) for k, v in exp.items()}, [r['id'] for r in runs])
