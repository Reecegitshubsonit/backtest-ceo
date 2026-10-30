"""Underlying-only VWAP/EMA signal study. Does not simulate option returns."""
import csv,gzip,json,statistics,hashlib
from collections import defaultdict,deque
from datetime import datetime,date,timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
NY=ZoneInfo('America/New_York')
SYMBOLS=['SPY','QQQ','IWM','AAPL','MSFT','NVDA','AMZN','GOOGL','META','TSLA']
START='2026-07-24'; END='2026-10-23'; WARM='2026-06-01'

def load(path):
    buckets={}
    with gzip.open(path,'rt') as f:
        for r in csv.DictReader(f):
            if not WARM<=r['t'][:10]<=END:continue
            t=datetime.fromisoformat(r['t'].replace('Z','+00:00')).astimezone(NY)
            minute=t.hour*60+t.minute
            if not 570<=minute<960:continue
            k=(str(t.date()),(minute-570)//3)
            x=buckets.setdefault(k,dict(t=t.replace(minute=t.minute-t.minute%3,second=0),o=float(r['o']),h=-float('inf'),l=float('inf'),c=0,v=0,pv=0,minutes=set()))
            x['h']=max(x['h'],float(r['h']));x['l']=min(x['l'],float(r['l']));x['c']=float(r['c'])
            v=float(r['v']);x['v']+=v;x['pv']+=float(r['vw'])*v;x['minutes'].add(minute)
    days=defaultdict(list)
    for (d,b),x in sorted(buckets.items()):
        x['complete']=len(x.pop('minutes'))==3
        days[d].append(x)
    return days

def indicators(days):
    ema9=ema21=prev=None; atr=None; n=0;trs=[]
    histories=defaultdict(lambda:deque(maxlen=20))
    for d,bars in sorted(days.items()):
        pv=vol=0;lastdiff=None;session_atrs=[]
        for b in bars:
            c=b['c'];ema9=c if ema9 is None else ema9+.2*(c-ema9)
            ema21=c if ema21 is None else ema21+(c-ema21)/11
            tr=b['h']-b['l'] if prev is None else max(b['h']-b['l'],abs(b['h']-prev),abs(b['l']-prev))
            prev=c; n+=1
            if atr is None:
                trs.append(tr)
                if len(trs)==14:atr=sum(trs)/14
            else:atr=(13*atr+tr)/14
            pv+=b['pv'];vol+=b['v'];vwap=pv/vol if vol else c;diff=ema9-vwap
            direction=1 if lastdiff is not None and lastdiff<=0<diff else -1 if lastdiff is not None and lastdiff>=0>diff else 0
            slot=b['t'].hour*60+b['t'].minute
            history=histories[slot]
            b.update(ema9=ema9,ema21=ema21,vwap=vwap,ema_vwap_gap=diff,signal=direction,trend=1 if ema9>ema21 else -1,atr=atr,
                     vol_ok=atr is not None and len(history)==20 and atr>statistics.median(history),
                     ready=n>=105)
            if atr is not None:session_atrs.append((slot,atr))
            lastdiff=diff
        for slot,value in session_atrs:histories[slot].append(value)
    return days

def study(all_days,start=START,end=END):
    trades=[];coverage={};positions={};losses=defaultdict(int);events=defaultdict(dict);skipped=defaultdict(int)
    for sym,days in all_days.items():
        valid=[];bad=[]
        for d,bars in sorted(days.items()):
            if not start<=d<=end:continue
            if len(bars)!=130 or not all(b['complete'] for b in bars):bad.append(d);continue
            valid.append(d)
            for i,b in enumerate(bars):events[b['t']][sym]=(bars,i)
        coverage[sym]=dict(complete_sessions=len(valid),incomplete_sessions=bad)
    for t,group in sorted(events.items()):
        day=str(t.date());minute=t.hour*60+t.minute
        # Execute previously confirmed signals at this candle's opening, never at its close.
        for sym,(bars,i) in sorted(group.items()):
            b=bars[i];p=positions.get(sym);prev=bars[i-1] if i else None
            opposite=p and prev and prev['signal']==-p['side']
            if p and opposite:
                close(trades,losses,positions,sym,b['o'],t,'opposite_cross')
            if i and not p and prev['signal'] and prev['ready'] and prev['vol_ok'] and prev['trend']==prev['signal'] and ((585<=minute<690) or (840<=minute<930)):
                if losses[day]>=2:skipped[sym]+=1;continue
                positions[sym]=dict(side=prev['signal'],price=b['o'],time=t,atr=prev['atr'])
        # Liquidate at 15:54 close (15:57 ET); three-minute data cannot specify 15:55 fills.
        if minute==954:
            for sym,(bars,i) in sorted(group.items()):
                if sym in positions:close(trades,losses,positions,sym,bars[i]['c'],t+timedelta(minutes=3),'session_exit')
    assert not positions
    return trades,coverage,dict(skipped)

def close(trades,losses,positions,sym,price,t,reason):
    p=positions.pop(sym);gross=p['side']*(price-p['price'])/p['price']*10000
    net=gross-4 # Assumed 2bp per side UNDERLYING friction sensitivity, not options fees/spread.
    trades.append(dict(symbol=sym,side='bullish' if p['side']==1 else 'bearish',entry_time=p['time'].isoformat(),exit_time=t.isoformat(),entry_price=p['price'],exit_price=price,gross_bps=gross,net_bps=net,move_atr=p['side']*(price-p['price'])/p['atr'],reason=reason))
    if net<0:losses[str(t.date())]+=1

def summarize(ts):
    values=[x['net_bps'] for x in ts]
    wins=sum(v for v in values if v>0);loss=-sum(v for v in values if v<0)
    return dict(trades=len(ts),win_rate_pct=100*sum(v>0 for v in values)/len(values) if values else None,
                mean_net_underlying_bps=statistics.mean(values) if values else None,
                profit_factor_underlying=wins/loss if loss else None,
                sum_net_underlying_bps=sum(values))

def main():
    root=Path(__file__).resolve().parents[2];out=root/'data/backtests/vwap-ema-3m-20260724-20261023';out.mkdir(parents=True,exist_ok=True)
    all_days={};inputs={}
    for sym in SYMBOLS:
        path=root/'data'/('etfs' if sym in ('SPY','QQQ','IWM') else 'stocks')/'1Min'/f'{sym}.csv.gz'
        all_days[sym]=indicators(load(path));inputs[sym]=dict(path=str(path),bytes=path.stat().st_size)
        print('Loaded',sym,flush=True)
    trades,coverage,skipped=study(all_days)
    result=dict(type='underlying_signal_study_NOT_options_backtest',start=START,end=END,
                summary=summarize(trades),by_symbol={s:summarize([t for t in trades if t['symbol']==s]) for s in SYMBOLS},
                coverage=coverage,blocked_entries_after_two_losses=skipped,inputs=inputs,
                assumptions=['EMA9/21 continuous across RTH sessions; daily VWAP from minute vw*volume',
                 'ATR14 Wilder includes overnight gap; above 20-prior-session median at same time of day',
                 'Confirmed EMA9 crossing VWAP, aligned with EMA21; next-bar open entry',
                 'Exits opposite cross at next open or 15:57 ET; no option premium stop or profit target',
                 'Entries 09:45-11:30 and 14:00-15:30 ET; skip incomplete 130-bar sessions',
                 'Portfolio two-loss lock based on underlying net move, not option P&L; deterministic symbol-order ties',
                 '2bp per side assumed underlying friction; no dollars, options returns, or capital equity curve',
                 'SPX shares SPY signal only, no duplicate exposure or SPX option results',
                 'GOOGL used for Alphabet; all choices are exploratory defaults, not user-confirmed optimized rules'])
    (out/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    if trades:
        with (out/'trades.csv').open('w') as f:
            w=csv.DictWriter(f,fieldnames=list(trades[0]));w.writeheader();w.writerows(trades)
    print(json.dumps(result['summary']),flush=True)

if __name__=='__main__':main()
