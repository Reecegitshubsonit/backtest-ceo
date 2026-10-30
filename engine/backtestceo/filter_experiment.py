"""Predeclared causal early-entry and filter-ablation research, exact 2DTE."""
import csv,json,shutil
from collections import Counter,defaultdict
from datetime import timedelta
from functools import lru_cache
from .cross_backtest import SYMBOLS,START,END
from .options_backtest import OUT as BASE,underlying,contract_map,choose_contract
from .two_dte import CachedOnly,OUT as TWO
from .databento_quotes import cache_valid,download_jobs
from . import quote_backtest as replay
OUT=BASE.parent/'options-vwap-ema-3m-2dte-10pct-filter-study'
CONFIGS=[('confirmed_all','confirmed',True,True,True),('early_all','early',True,True,True),
         ('early_no_atr','early',False,True,True),('early_no_session','early',True,False,True),
         ('early_no_ema21','early',True,True,False),('early_no_filters','early',False,False,False)]

def early_side(previous,current):
    """Use completed candles only: projected next gap changes sign, within .15 ATR."""
    gap=current['ema_vwap_gap'];old=previous['ema_vwap_gap'];atr=current['atr']
    if atr is None or atr<=0 or old*gap<=0:return 0
    change=gap-old
    if gap<0 and change>0 and gap+change>=0 and abs(gap)<=.15*atr:return 1
    if gap>0 and change<0 and gap+change<=0 and abs(gap)<=.15*atr:return -1
    return 0

def signals_for(data,groups,mode,vol,session,trend):
    signals=[];counts=Counter()
    for symbol,days in data.items():
        for day,bars in sorted(days.items()):
            if not START<=day<=END:continue
            expected=[bars[0]['t'].replace(hour=9,minute=30)+timedelta(minutes=3*i) for i in range(130)]
            if [b['t'] for b in bars]!=expected:continue
            latched=0
            for i,b in enumerate(bars):
                t=b['t']+timedelta(minutes=3);minute=t.hour*60+t.minute
                if b['signal']:signals.append(dict(t=t,symbol=symbol,exit_side=b['signal']))
                side=b['signal'] if mode=='confirmed' else (early_side(bars[i-1],b) if i else 0)
                if mode=='early':
                    if not side:latched=0
                    elif side==latched:continue
                    else:latched=side
                if not side or not b['ready']:continue
                if vol and not b['vol_ok']:continue
                if trend and b['trend']!=side:continue
                if session and not(585<=minute<690 or 840<=minute<930):continue
                # No new entries after the unchanged 15:55 liquidation time.
                if minute>=955:continue
                counts['raw_signals']+=1
                c=choose_contract(groups[symbol],day,side,b['c'],exact_dte=2)
                if c is None:counts['no_exact_expiry']+=1;continue
                signals.append(dict(t=t,symbol=symbol,contract=c,side=side))
    return signals,dict(counts)

def main():
    OUT.mkdir(exist_ok=True,parents=True);api=CachedOnly()
    data={s:underlying(api,s) for s in SYMBOLS};groups={s:contract_map(s,api) for s in SYMBOLS}
    variants={};coverage={};required=defaultdict(set)
    for name,mode,vol,session,trend in CONFIGS:
        ss,cc=signals_for(data,groups,mode,vol,session,trend);variants[name]=ss;coverage[name]=cc
        for s in ss:
            if 'contract'in s:required[str(s['t'].date())].add(s['contract'])
    dest=OUT/'databento-quotes';dest.mkdir(exist_ok=True)
    jobs=[dict(day=d,symbols=sorted(cs)) for d,cs in sorted(required.items())]
    for job in jobs:
        for source in (TWO/'databento-quotes',BASE/'databento-quotes'):
            if not cache_valid(job,dest) and cache_valid(job,source):
                p=source/(job['day']+'.csv.gz');shutil.copy2(p,dest/p.name);shutil.copy2(p.with_suffix('.json'),dest/p.with_suffix('.json').name)
    (OUT/'definition.json').write_text(json.dumps(dict(configs=CONFIGS,premium_budget=.10,
        early_rule='Completed-bar gap approaches zero; linear projection crosses next bar; absolute gap <= 0.15 ATR14; first signal in consecutive approach episode',
        split='2026-09-01',validation_limit='Already-examined period; chronological robustness diagnostic, not untouched out-of-sample'),indent=2)+'\n')
    download_jobs(jobs,dest,estimate_cap=5)
    # Avoid decompressing the same session for every variant; bounded to manage memory.
    original=replay.read_day
    replay.read_day=lru_cache(maxsize=8)(original)
    results={}
    for name,ss in variants.items():
        segments={}
        for segment,select in [('july_august',lambda d:d<'2026-09-01'),('september_october',lambda d:d>='2026-09-01')]:
            selected=[s for s in ss if select(str(s['t'].date()))]
            r=replay.run(selected,quote_dir=dest,premium_budget=.10)
            r['eligible_signals']=sum('contract'in s for s in selected)
            assert not r['unresolved_positions']
            assert r['closed_trades']+sum(r['rejections'].values())==r['eligible_signals']
            assert round(sum(t['net_pnl'] for t in r['trades']),2)==r['net_pnl']
            with (OUT/f'{name}-{segment}-trades.csv').open('w') as f:
                if r['trades']:
                    w=csv.DictWriter(f,fieldnames=list(r['trades'][0]));w.writeheader();w.writerows(r['trades'])
            segments[segment]={k:v for k,v in r.items() if k not in ('trades','daily')}
            print('SCENARIO',name,segment,json.dumps(segments[segment]),flush=True)
        results[name]=dict(coverage=coverage[name],segments=segments)
        (OUT/'results.json').write_text(json.dumps(results,indent=2)+'\n')
    # Full-period baseline and early entry retain cash continuously across the split.
    for name in ('confirmed_all','early_all'):
        path=OUT/('confirmed-full-period-10pct.json' if name=='confirmed_all' else 'early-full-period-10pct.json')
        if path.exists():continue
        r=replay.run(variants[name],quote_dir=dest,premium_budget=.10)
        stress=replay.run(variants[name],quote_dir=dest,premium_budget=.10,extra_slip=.03,latency=2)
        r['premium_budget_pct']=10
        r['execution_stress']={k:v for k,v in stress.items() if k not in ('trades','daily')}
        path.write_text(json.dumps(r,indent=2)+'\n')
    print('DONE',flush=True)

if __name__=='__main__':main()
