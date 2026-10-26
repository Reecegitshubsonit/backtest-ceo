"""Frozen-strategy exact-calendar-1DTE comparison, with separate Databento archives."""
import csv,json,shutil
from collections import defaultdict,Counter
from .options_backtest import OUT as BASE,keys,prepare,Throttled
from .databento_quotes import download_jobs,cache_valid
from .quote_backtest import run
OUT=BASE.parent/'options-vwap-ema-3m-1dte-20260724-20261023'


def matched_signals(original,one_dte_signals):
    eligible={(s['t'],s['symbol'],s['side']) for s in one_dte_signals if 'contract'in s}
    return [s for s in original if 'contract'not in s or (s['t'],s['symbol'],s['side']) in eligible]


def main():
    OUT.mkdir(parents=True,exist_ok=True);keys()
    signals,_,coverage=prepare(Throttled(OUT/'.unused-cache'),exact_dte=1,fetch_option_bars=False)
    serial=[{**s,'t':s['t'].isoformat()} for s in signals]
    (OUT/'signals.json').write_text(json.dumps(serial)+'\n')
    (OUT/'coverage.json').write_text(json.dumps(coverage,indent=2)+'\n')
    grouped=defaultdict(set)
    for s in signals:
        if 'contract'in s:grouped[str(s['t'].date())].add(s['contract'])
    jobs=[dict(day=d,symbols=sorted(cs)) for d,cs in sorted(grouped.items())]
    dest=OUT/'databento-quotes';dest.mkdir(exist_ok=True)
    for job in jobs:
        if cache_valid(job,BASE/'databento-quotes') and not cache_valid(job,dest):
            path=BASE/'databento-quotes'/(job['day']+'.csv.gz')
            shutil.copy2(path,dest/path.name);shutil.copy2(path.with_suffix('.json'),dest/path.with_suffix('.json').name)
    download_jobs(jobs,dest)
    result=run(signals,quote_dir=dest)
    result.update(type='EXACT_CALENDAR_1DTE_REAL_NBBO_OPTIONS_REPLAY',exact_calendar_dte=1,coverage=coverage,
                  assumptions=[a.replace('ATM standard contract, nearest expiry within 7 days;', 'ATM standard contract, exactly one calendar day to expiration; skip if unavailable;') for a in json.loads((BASE/'quote-results.json').read_text())['assumptions']],
                  start='2026-07-24',end='2026-10-23',
                  changed_rule='Replace nearest expiry within seven days with exactly next-calendar-day expiry; skip otherwise.')
    stress=run(signals,extra_slip=.03,latency=2,quote_dir=dest)
    result['execution_stress']={k:v for k,v in stress.items() if k not in ('trades','daily')}
    control_path=OUT/'matched-baseline-results.json'
    if not control_path.exists():
        original,_,_=prepare(Throttled(OUT/'.unused-cache'),fetch_option_bars=False)
        control_signals=matched_signals(original,signals)
        control=run(control_signals)
        control['entry_opportunities']=sum('contract'in s for s in control_signals)
        control['comparison']='Original nearest expiry on the same exact-1DTE-eligible signals, with risk independently replayed.'
        control_path.write_text(json.dumps(control,indent=2)+'\n')
        with (OUT/'matched-baseline-trades.csv').open('w') as f:
            if control['trades']:
                w=csv.DictWriter(f,fieldnames=list(control['trades'][0]));w.writeheader();w.writerows(control['trades'])
    (OUT/'quote-results.json').write_text(json.dumps(result,indent=2)+'\n')
    for name,ts in [('quote-trades.csv',result['trades']),('quote-stress-trades.csv',stress['trades']),
                    ('losing-trades.csv',[t for t in result['trades'] if t['net_pnl']<0])]:
        with (OUT/name).open('w') as f:
            if ts:
                w=csv.DictWriter(f,fieldnames=list(ts[0]));w.writeheader();w.writerows(ts)
    print({k:v for k,v in result.items() if k not in ('trades','daily','assumptions','coverage')},flush=True)

if __name__=='__main__':main()
