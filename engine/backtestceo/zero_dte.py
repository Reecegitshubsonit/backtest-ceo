"""Exact same-day expiry replay using existing, hash-verified quote archives only."""
import csv
import json
from collections import Counter
from datetime import datetime
from .options_backtest import OUT as BASE, prepare
from .databento_quotes import cache_valid
from .quote_backtest import run

OUT = BASE.parent / 'options-vwap-ema-3m-0dte-20260724-20261023'

class CachedOnly:
    requests = 0
    def _get(self, *args, **kwargs):
        raise RuntimeError('Missing cached underlying data; no network fallback')
    def _paged(self, *args, **kwargs):
        raise RuntimeError('Missing cached contract metadata; no network fallback')

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    signals, _, coverage = prepare(CachedOnly(), exact_dte=0, fetch_option_bars=False)
    entries = [s for s in signals if 'contract' in s]
    grouped = {}
    for s in entries:
        assert datetime.strptime(s['contract'][-15:-9], '%y%m%d').date() == s['t'].date()
        grouped.setdefault(str(s['t'].date()), set()).add(s['contract'])
    quote_dir = BASE / 'databento-quotes'
    for day, symbols in grouped.items():
        if not cache_valid(dict(day=day, symbols=sorted(symbols)), quote_dir):
            raise RuntimeError(f'Missing verified same-day quote coverage: {day}')
    (OUT/'signals.json').write_text(json.dumps([{**s, 't':s['t'].isoformat()} for s in signals])+'\n')
    result = run(signals, quote_dir=quote_dir)
    stress = run(signals, extra_slip=.03, latency=2, quote_dir=quote_dir)
    result.update(type='EXACT_CALENDAR_0DTE_REAL_NBBO_OPTIONS_REPLAY', exact_calendar_dte=0,
                  start='2026-07-24', end='2026-10-23', coverage=coverage,
                  eligible_signals_by_direction=dict(Counter('call' if s['side']==1 else 'put' for s in entries)),
                  new_data_download_cost_usd=0,
                  assumptions=[a.replace('nearest expiry within 7 days', 'exact same-day expiry; skip if unavailable')
                               for a in json.loads((BASE/'quote-results.json').read_text())['assumptions']],
                  execution_stress={k:v for k,v in stress.items() if k not in ('trades','daily')})
    for name, trades in [('quote-trades.csv', result['trades']), ('quote-stress-trades.csv', stress['trades']),
                         ('losing-trades.csv', sorted([t for t in result['trades'] if t['net_pnl']<0], key=lambda t:t['net_pnl']))]:
        with (OUT/name).open('w') as f:
            if trades:
                writer=csv.DictWriter(f, fieldnames=list(trades[0]));writer.writeheader();writer.writerows(trades)
    assert result['closed_trades'] + sum(result['rejections'].values()) == len(entries)
    assert round(sum(t['net_pnl'] for t in result['trades']),2)==result['net_pnl']
    for right in ('C','P'):
        trades=[t for t in result['trades'] if t['contract'][-9]==right]
        result['calls' if right=='C' else 'puts']=dict(trades=len(trades), winners=sum(t['net_pnl']>0 for t in trades),
            losers=sum(t['net_pnl']<0 for t in trades), net_pnl=round(sum(t['net_pnl'] for t in trades),2))
    result['losing_exit_reasons']=dict(Counter(t['reason'] for t in result['trades'] if t['net_pnl']<0))
    (OUT/'quote-results.json').write_text(json.dumps(result,indent=2)+'\n')
    print('RESULT',json.dumps({k:v for k,v in result.items() if k not in ('trades','daily','assumptions','coverage')}),flush=True)

if __name__=='__main__':main()
