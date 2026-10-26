"""Exploratory option trade-bar simulation with explicit modeled spread scenarios.
Not NBBO replay. No trading/orders. Reuses cached data; obtains missing Alpaca bars only.
"""
import csv,gzip,json,math,hashlib
from collections import defaultdict,Counter
from datetime import datetime,timedelta,date
from pathlib import Path
from .collect import keys,Throttled
from .alpaca import DATA, CONTRACTS_URL
from .cross_backtest import NY,SYMBOLS,START,END,WARM,indicators
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'data/backtests/options-vwap-ema-3m-20260724-20261023'
CACHE=OUT/'market-data'
FEE=.65;SLIP=.01;CAPITAL=10000.;BUDGET=.02


def at(s):return datetime.fromisoformat(s.replace('Z','+00:00')).astimezone(NY)


def request_bars(api,asset,symbols,start,end,path,tf='1Min'):
    if path.exists():return json.loads(path.read_text())
    params=dict(symbols=','.join(symbols),timeframe=tf,start=start,end=end,limit=10000)
    if asset=='stocks':params.update(feed='sip',adjustment='raw')
    url=DATA+('/v2/stocks/bars' if asset=='stocks' else '/v1beta1/options/bars')
    result={s:[] for s in symbols};token=None
    while True:
        body=api._get(url,{**params,**({'page_token':token} if token else {})})
        for s,rows in (body.get('bars') or {}).items():result.setdefault(s,[]).extend(rows)
        token=body.get('next_page_token')
        if not token:break
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(result));tmp.replace(path)
    return result


def underlying(api,symbol):
    path=CACHE/f'raw-{symbol}-3min.json'
    rows=request_bars(api,'stocks',[symbol],WARM+'T00:00:00Z','2026-10-24T00:00:00Z',path,'3Min')[symbol]
    days=defaultdict(list)
    for r in rows:
        t=at(r['t']);minute=t.hour*60+t.minute
        if 570<=minute<960:
            days[str(t.date())].append(dict(t=t,o=float(r['o']),h=float(r['h']),l=float(r['l']),c=float(r['c']),
                v=float(r['v']),pv=float(r.get('vw',r['c']))*float(r['v']),complete=True))
    for d,bs in days.items():
        bs.sort(key=lambda b:b['t'])
        if len({b['t'] for b in bs})!=len(bs):raise ValueError('Duplicate underlying timestamps')
    return indicators(days)


def contract_map(symbol, api):
    groups=defaultdict(list)
    source=ROOT/f'data/options/contracts/{symbol}.csv.gz'
    if source.exists():
        with gzip.open(source,'rt') as f: rows=list(csv.DictReader(f))
    else:
        path=CACHE/f'contracts-{symbol}.json'
        if path.exists():rows=json.loads(path.read_text())
        else:
            rows=[]
            for status in ('active','inactive'):
                rows+=api._paged(CONTRACTS_URL,dict(underlying_symbols=symbol,status=status,limit=10000,
                    expiration_date_gte=START,expiration_date_lte='2026-10-30'),lambda b:b.get('option_contracts') or [])
            path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(rows))
    for r in rows:
        if r['root_symbol']!=symbol or str(r.get('multiplier'))!='100':continue
        groups[(r['expiration_date'],r['type'])].append(r)
    return groups


def choose_contract(groups,day,side,spot):
    right='call' if side==1 else 'put'
    exps=sorted(e for e,r in groups if r==right and 0<=(date.fromisoformat(e)-date.fromisoformat(day)).days<=7)
    if not exps:return None
    return min(groups[(exps[0],right)],key=lambda r:(abs(float(r['strike_price'])-spot),float(r['strike_price'])))['symbol']


def prepare(api):
    signals=[];tapes={};coverage={}
    for symbol in SYMBOLS:
        days=underlying(api,symbol);groups=contract_map(symbol,api);needed=defaultdict(set);counts=Counter()
        for day,bars in sorted(days.items()):
            if not START<=day<=END:continue
            expected=[bars[0]['t'].replace(hour=9,minute=30)+timedelta(minutes=3*i) for i in range(130)]
            if [b['t'] for b in bars]!=expected:counts['incomplete_sessions']+=1;continue
            counts['complete_sessions']+=1
            for b in bars:
                minute=b['t'].hour*60+b['t'].minute+3
                # Signal is available at bar end, execution on following minute bar open.
                if not b['signal'] or not b['ready'] or not b['vol_ok'] or b['trend']!=b['signal']:continue
                if not ((585<=minute<690) or (840<=minute<930)):continue
                c=choose_contract(groups,day,b['signal'],b['c'])
                if c is None:counts['no_contract']+=1;continue
                time=b['t']+timedelta(minutes=3)
                signals.append(dict(t=time,symbol=symbol,contract=c,side=b['signal']))
                needed[day].add(c)
        # Include opposite cross events even when they are outside entry windows/confluence.
        for day,bars in sorted(days.items()):
            if not START<=day<=END:continue
            for b in bars:
                if b['signal']:signals.append(dict(t=b['t']+timedelta(minutes=3),symbol=symbol,exit_side=b['signal']))
        for day,contracts in sorted(needed.items()):
            lo=datetime.fromisoformat(day).replace(hour=9,minute=30,tzinfo=NY).astimezone(__import__('datetime').timezone.utc)
            hi=lo+timedelta(hours=6,minutes=30)
            path=CACHE/'options'/symbol/f'{day}.json'
            got=request_bars(api,'options',sorted(contracts),lo.isoformat(),hi.isoformat(),path)
            for c,rows in got.items():
                tape={}
                for r in rows:
                    t=at(r['t']);b={k:float(r[k]) for k in ('o','h','l','c','v')}
                    if str(t.date())!=day or t in tape:
                        raise ValueError('Mismatched session or duplicate option record')
                    if not all(math.isfinite(v) for v in b.values()) or not (0<b['l']<=min(b['o'],b['c'])<=max(b['o'],b['c'])<=b['h']) or b['v']<0:
                        raise ValueError('Invalid option OHLCV record')
                    tape[t]=b
                tapes[(c,day)]=tape
            counts['contracts_requested']+=len(contracts)
            counts['contracts_with_bars']+=sum(bool(v) for v in got.values())
        coverage[symbol]=dict(counts)
        print('Prepared',symbol,dict(counts),'requests',api.requests,flush=True)
    return signals,tapes,coverage


def price(anchor,side,spread):
    return round(max(.01,anchor*(1+side*spread/2)+side*SLIP),4)


def simulate(signals,tapes,spread):
    events=defaultdict(list)
    for s in signals:events[s['t']].append(s)
    days=sorted({str(t.date()) for t in events});cash=CAPITAL;positions={};closed=[];rejected=Counter();daily=[];peak=CAPITAL;drawdown=0;unresolved=[]
    for day in days:
        if positions:break # Never silently reset an unresolved overnight liability.
        losses=0;halt=False;day_start=cash;equity_complete=True
        start=datetime.fromisoformat(day).replace(hour=9,minute=30,tzinfo=NY)
        for m in range(390):
            now=start+timedelta(minutes=m)
            now_events=events.get(now,[])
            exit_events={e['symbol']:e['exit_side'] for e in now_events if 'exit_side'in e}
            exited=set()
            # Opening exits first, including gaps through stop/target. No stale quote fills.
            for sym,p in list(positions.items()):
                tape=tapes.get((p['contract'],day),{});bar=tape.get(now)
                reason=None;anchor=None;fill_time=now
                opposite=exit_events.get(sym)==-p['side']
                if opposite:p['exit_pending']='opposite_cross'
                if m>=385:p['exit_pending']=p.get('exit_pending') or 'session_exit'
                if bar and bar['v']>0:
                    opening=price(bar['o'],-1,spread)
                    if opening<=p['stop']:reason='stop_gap';anchor=bar['o']
                    elif opening>=p['target']:reason='target_gap';anchor=bar['o']
                    elif p.get('exit_pending'):reason=p['exit_pending'];anchor=bar['o']
                if reason:
                    cash,net=finish(p,anchor,spread,cash,now,reason,closed)
                    if net<0:losses+=1
                    del positions[sym];exited.add(sym)
            if losses>=2:halt=True
            for e in sorted(now_events,key=lambda x:x['symbol']):
                if 'contract' not in e:continue
                sym=e['symbol']
                if halt:rejected['two_loss_daily_lock']+=1;continue
                if sym in positions or sym in exited:rejected['already_open_or_same_bar_exit']+=1;continue
                bar=tapes.get((e['contract'],day),{}).get(now)
                # Exact next minute must have an executed trade; never search forward for favorable marks.
                if not bar or bar['v']<=0:rejected['no_next_minute_option_trade']+=1;continue
                # Last completed observed marks only when allocating risk; unpriced positions block entries.
                marked=cash;ok=True
                for p in positions.values():
                    if p.get('mark') is None or now-p['mark_time']>timedelta(minutes=5):ok=False;break
                    marked+=p['mark']*p['qty']*100-FEE*p['qty']
                if not ok:rejected['stale_open_position_mark']+=1;continue
                premium=price(bar['o'],1,spread);unit=premium*100+FEE
                qty=min(1,math.floor(marked*BUDGET/(premium*100+2*FEE)),math.floor(cash/unit))
                if qty<1:rejected['premium_budget_or_cash']+=1;continue
                cash-=qty*unit
                positions[sym]=dict(symbol=sym,contract=e['contract'],side=e['side'],qty=qty,entry=premium,
                    entry_time=now,stop=premium*.75,target=premium*1.5,mark=None,mark_time=now)
            # Intrabar exits only after entry. Stop wins ambiguous stop+target minute.
            for sym,p in list(positions.items()):
                bar=tapes.get((p['contract'],day),{}).get(now)
                if not bar or bar['v']<=0:continue
                low=price(bar['l'],-1,spread);high=price(bar['h'],-1,spread)
                reason=None;anchor=None
                if low<=p['stop']:
                    reason='stop_intrabar';anchor=bar['l'] # conservative minute low, not guaranteed stop fill
                elif high>=p['target']:
                    reason='target_intrabar';anchor=(p['target']+SLIP)/(1-spread/2)
                if reason:
                    cash,net=finish(p,anchor,spread,cash,now+timedelta(minutes=1),reason,closed)
                    if net<0:losses+=1
                    del positions[sym]
                else:p['mark']=price(bar['c'],-1,spread);p['mark_time']=now+timedelta(minutes=1)
            if losses>=2:halt=True
            marks_ok=all(p['mark'] is not None and now+timedelta(minutes=1)-p['mark_time']<=timedelta(minutes=5) for p in positions.values())
            if marks_ok:
                equity=cash+sum(p['mark']*p['qty']*100-FEE*p['qty'] for p in positions.values())
                peak=max(peak,equity);drawdown=max(drawdown,peak-equity)
            else:equity_complete=False
        if positions:
            unresolved=[dict(symbol=p['symbol'],contract=p['contract'],qty=p['qty'],entry=p['entry']) for p in positions.values()]
        daily.append(dict(day=day,net_pnl=round(cash-day_start,2) if not positions else None,losses=losses,halted=halt,marks_complete=equity_complete))
    vals=[t['net_pnl'] for t in closed];wins=sum(v for v in vals if v>0);loss=-sum(v for v in vals if v<0)
    return dict(spread_pct=spread*100,closed_trades=len(vals),win_rate_pct=100*sum(v>0 for v in vals)/len(vals) if vals else None,
        net_pnl=round(cash-CAPITAL,2) if not positions else None,return_pct=round((cash/CAPITAL-1)*100,3) if not positions else None,
        ending_equity=round(cash,2) if not positions else None,profit_factor=wins/loss if loss else None,
        observed_drawdown=round(drawdown,2),unresolved_positions=unresolved,rejections=dict(rejected),daily=daily,trades=closed,
        days_with_stale_or_missing_marks=sum(not d['marks_complete'] for d in daily))


def finish(p,anchor,spread,cash,t,reason,trades):
    exit_price=price(anchor,-1,spread);qty=p['qty'];cash+=qty*(exit_price*100-FEE)
    net=qty*((exit_price-p['entry'])*100-2*FEE)
    trades.append(dict(symbol=p['symbol'],contract=p['contract'],qty=qty,entry_time=p['entry_time'].isoformat(),exit_time=t.isoformat(),
        entry_price=p['entry'],exit_price=exit_price,net_pnl=round(net,4),reason=reason,fill_source='modeled_trade_bar_NOT_NBBO'))
    return cash,net


def main():
    OUT.mkdir(parents=True,exist_ok=True);keys();api=Throttled(OUT/'.unused-cache')
    signals,tapes,coverage=prepare(api)
    results=[simulate(signals,tapes,s) for s in (.05,.10,.20)]
    report=dict(type='MODELED_OPTIONS_TRADE_BAR_SIMULATION_NOT_EXECUTABLE_QUOTE_REPLAY',start=START,end=END,coverage=coverage,
        data_sha256={str(p.relative_to(OUT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(CACHE.rglob('*.json'))},
        capital=CAPITAL,premium_budget_pct=BUDGET*100,fee_per_contract_per_side=FEE,extra_slippage_per_side=SLIP,
        assumptions=['Actual raw underlying 3-minute SIP bars, EMA9/21, daily VWAP, prior-session ATR filter',
          'ATM standard 100-multiplier contract from existing metadata; nearest expiry 0-7 days; earliest observed option bar required at entry',
          '25% premium stop; 50% target; opposite-cross or 15:55 ET pending liquidation',
          'Trade-bar open as modeled midpoint anchor; 5/10/20% full spreads and 0.01 adverse slippage each side',
          'Stop/target collisions prioritize stop; intrabar stop uses minute low; target fills at threshold; these are assumptions, not quote evidence',
          'At most one contract per trade within 2% premium budget; no displayed size evidence or guaranteed liquidity',
          'No stale exits; unresolved position stops study; no forced expiry/assignment reconstruction',
          'Two losses net fees across portfolio stops entries; simultaneous entries alphabetical; one per underlying',
          'SPX not simulated; SPY cannot substitute for SPX option fills; no duplicate SPY exposure',
          'Not historical NBBO: spread, trade-print timing, target fills, price impact and partial-fill behavior unverified',
          'All defaults frozen before this run; no parameter optimization; same period already examined'],results=results)
    (OUT/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    for r in results:
        with (OUT/f"trades-spread-{r['spread_pct']:g}.csv").open('w') as f:
            if r['trades']:
                w=csv.DictWriter(f,fieldnames=list(r['trades'][0]));w.writeheader();w.writerows(r['trades'])
        print({k:v for k,v in r.items() if k not in ('trades','daily')},flush=True)

if __name__=='__main__':main()
