"""Long-option replay from real Databento one-second NBBO snapshots.
Crossing fills are simulated at displayed size after 1s latency, not guaranteed executions.
"""
import csv,gzip,json,math,hashlib
from collections import defaultdict,Counter
from datetime import datetime,timedelta
from .options_backtest import OUT,CAPITAL,BUDGET,FEE,prepare,keys,Throttled,at
from .databento_quotes import DEST
from .cross_backtest import NY


def valid(q):
    return q is not None and all(math.isfinite(x) for x in q[:2]) and 0<q[0]<=q[1] and q[2]>0 and q[3]>0


def read_day(day,quote_dir=None):
    path=(quote_dir or DEST)/(day+'.csv.gz');manifest=json.loads(path.with_suffix('.json').read_text())
    if hashlib.sha256(path.read_bytes()).hexdigest()!=manifest['sha256']:raise ValueError('Quote archive hash mismatch')
    events=defaultdict(list);invalid=0
    with gzip.open(path,'rt') as f:
        for r in csv.DictReader(f):
            timestamp=at(r['ts_recv']);sec=int(timestamp.timestamp())
            if str(timestamp.date())!=day:raise ValueError('Wrong quote session')
            symbol=r['symbol'].replace(' ','')
            try:q=(float(r['bid_px_00']),float(r['ask_px_00']),int(r['bid_sz_00']),int(r['ask_sz_00']))
            except (ValueError,TypeError):q=None
            if not valid(q):invalid+=1
            events[sec].append((symbol,q)) # Invalid updates invalidate prior quotes instead of keeping stale markets.
    return events,invalid


def run(signals,extra_slip=.01,latency=1,quote_dir=None,premium_budget=BUDGET):
    days=defaultdict(list)
    for e in signals:days[str(e['t'].date())].append(e)
    cash=CAPITAL;positions={};trades=[];daily=[];reject=Counter();peak=CAPITAL;dd=0;invalid=0;missing_marks=0
    def close(sym,p,q,now,reason):
        nonlocal cash
        px=max(0,q[0]-extra_slip);net=p['qty']*((px-p['entry'])*100-2*FEE)
        cash+=p['qty']*(px*100-FEE)
        trades.append(dict(symbol=sym,contract=p['contract'],qty=p['qty'],entry_time=p['entry_time'].isoformat(),exit_time=now.isoformat(),
            entry_ask=p['ask'],entry_fill=p['entry'],exit_bid=q[0],exit_fill=px,net_pnl=round(net,4),reason=reason,
            entry_spread=p['spread'],exit_spread=q[1]-q[0],source='Databento CBBO-1s',latency_seconds=latency))
        del positions[sym]
        return net
    for day,day_signals in sorted(days.items()):
        if positions:break
        if not any('contract' in e for e in day_signals):
            daily.append(dict(day=day,net_pnl=0,losses=0,halted=False,unpriced_seconds=0))
            continue
        quotes,invalid_count=(read_day(day) if quote_dir is None else read_day(day,quote_dir));invalid+=invalid_count
        events=defaultdict(list)
        for e in day_signals:events[int(e['t'].timestamp())].append(e)
        begin=datetime.fromisoformat(day).replace(hour=9,minute=30,tzinfo=NY);start=int(begin.timestamp())
        market={};pending=[];losses=0;halt=False;startcash=cash;stale_seconds=0
        for sec in range(start,start+390*60):
            now=datetime.fromtimestamp(sec,NY)
            for c,q in quotes.get(sec,[]):market[c]=(q,sec)
            def quote(c):
                q,ts=market.get(c,(None,0))
                return q if sec-ts<=2 and valid(q) else None
            # Fill orders that were generated at an earlier information timestamp.
            for sym,p in list(positions.items()):
                if p.get('due',float('inf'))<=sec:
                    q=quote(p['contract'])
                    if q and q[2]>=p['qty']:
                        if close(sym,p,q,now,p['reason'])<0:losses+=1
            if losses>=2:halt=True
            for e,due,deadline in list(pending):
                if sec<due:continue
                if halt:reject['two_loss_daily_lock']+=1;pending.remove((e,due,deadline));continue
                sym=e['symbol']
                if sym in positions:reject['already_open']+=1;pending.remove((e,due,deadline));continue
                if sec>deadline:reject['no_valid_quote_within_5s']+=1;pending.remove((e,due,deadline));continue
                q=quote(e['contract'])
                if q is None:continue
                equity=cash;good=True
                for p in positions.values():
                    mark=quote(p['contract'])
                    if mark is None:good=False;break
                    equity+=max(0,mark[0]-extra_slip)*p['qty']*100-FEE*p['qty']
                if not good:reject['unpriced_open_position']+=1;pending.remove((e,due,deadline));continue
                entry=q[1]+extra_slip;unit=entry*100+FEE
                qty=min(1,int(equity*premium_budget//(entry*100+2*FEE)),int(cash//unit),q[3])
                if qty<1:reject['premium_budget_cash_or_size']+=1;pending.remove((e,due,deadline));continue
                cash-=qty*unit
                positions[sym]=dict(contract=e['contract'],side=e['side'],qty=qty,entry=entry,entry_time=now,
                    stop=entry*.75,target=entry*1.5,ask=q[1],spread=q[1]-q[0])
                pending.remove((e,due,deadline))
            for e in sorted(events.get(sec,[]),key=lambda e:(e['symbol'],'contract'in e)):
                sym=e['symbol'];p=positions.get(sym)
                if 'exit_side'in e:
                    if p and e['exit_side']==-p['side'] and 'due'not in p:p.update(due=sec+latency,reason='opposite_cross')
                else:
                    if halt:reject['two_loss_daily_lock']+=1
                    elif p:reject['already_open']+=1
                    else:pending.append((e,sec+latency,sec+5+latency))
            for sym,p in positions.items():
                if 'due'in p:continue
                q=quote(p['contract'])
                if now.hour*60+now.minute>=955:p.update(due=sec+latency,reason='session_exit')
                elif q:
                    executable=max(0,q[0]-extra_slip)
                    if executable<=p['stop']:p.update(due=sec+latency,reason='premium_stop')
                    elif executable>=p['target']:p.update(due=sec+latency,reason='premium_target')
            marked=cash;good=True
            for p in positions.values():
                q=quote(p['contract'])
                if q is None:good=False;break
                marked+=max(0,q[0]-extra_slip)*p['qty']*100-FEE*p['qty']
            if good:peak=max(peak,marked);dd=max(dd,peak-marked)
            else:stale_seconds+=1
        missing_marks+=stale_seconds
        daily.append(dict(day=day,net_pnl=round(cash-startcash,2) if not positions else None,losses=losses,halted=halt,unpriced_seconds=stale_seconds))
        print('Replayed quotes',day,'trades',len(trades),'equity',round(cash,2),'open',len(positions),flush=True)
    vals=[t['net_pnl'] for t in trades];wins=sum(v for v in vals if v>0);loss=-sum(v for v in vals if v<0)
    return dict(starting_capital=CAPITAL,ending_equity=round(cash,2) if not positions else None,
      net_pnl=round(cash-CAPITAL,2) if not positions else None,return_pct=round(100*(cash/CAPITAL-1),3) if not positions else None,
      trades=trades,daily=daily,closed_trades=len(trades),win_rate_pct=100*sum(v>0 for v in vals)/len(vals) if vals else None,
      profit_factor=wins/loss if loss else None,observed_drawdown=round(dd,2),drawdown_complete=missing_marks==0,
      unpriced_position_seconds=missing_marks,invalid_quote_records=invalid,rejections=dict(reject),
      unresolved_positions={s:{k:v for k,v in p.items() if k!='entry_time'} for s,p in positions.items()},
      extra_slippage_per_side=extra_slip,latency_seconds=latency)


def main():
    keys();signals,_,coverage=prepare(Throttled(OUT/'.unused-cache'))
    result=run(signals)
    result.update(type='SIMULATED_LONG_OPTIONS_EXECUTION_ON_REAL_ONE_SECOND_NBBO',coverage=coverage,
      assumptions=['Prior completed raw 3-minute signals; EMA9/VWAP cross aligned with EMA21; same-time 20-session ATR median filter',
       'Entry windows 09:45-11:30 and 14:00-15:30 ET; 1s signal-to-order latency; reject entry after 5s grace',
       'ATM standard contract, nearest expiry within 7 days; option eligibility validated by subsequent observed quote, not future profitability',
       'At most one contract, 2% of equity maximum premium and round-trip fees, cash constrained; no borrowing',
       'Buy ask + $0.01; sell bid - $0.01; $0.65 commission per contract per side; sufficient displayed size required',
       '25% premium stop, 50% target monitored at bid net slippage; next quote at least 1s later executes, so gaps can exceed stop',
       'Opposite cross or 15:55 ET submits exit; unpriced exits remain open and invalidate final equity',
       'Two total net losing trades per day across portfolio block new entries; open trades still managed',
       'NBBO snapshots sampled at 1s, timestamps based on ts_recv; reject crossed, nonpositive or size-zero quotes and sample gaps >2s',
       'Displayed liquidity is not a guaranteed fill; hidden queue, subsecond movement, broker routing, quote fade and auction behavior unmodeled',
       'SPX excluded: no validated SPX underlying/contract selection feed; SPY signal is not SPX option execution',
       'Exploratory defaults, same already-examined period; no claim of out-of-sample validation'])
    stress=run(signals,extra_slip=.03,latency=2)
    result['execution_stress']={k:v for k,v in stress.items() if k not in ('trades','daily')}
    target=OUT/'quote-results.json';target.write_text(json.dumps(result,indent=2)+'\n')
    with (OUT/'quote-trades.csv').open('w') as f:
        if result['trades']:
            w=csv.DictWriter(f,fieldnames=list(result['trades'][0]));w.writeheader();w.writerows(result['trades'])
    with (OUT/'quote-stress-trades.csv').open('w') as f:
        if stress['trades']:
            w=csv.DictWriter(f,fieldnames=list(stress['trades'][0]));w.writeheader();w.writerows(stress['trades'])
    print({k:v for k,v in result.items() if k not in ('trades','daily','assumptions','coverage')},flush=True)

if __name__=='__main__':main()
