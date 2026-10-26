"""Read-only diagnostic of the frozen real-NBBO run; does not change strategy or rerun it."""
import csv,gzip,json,re,statistics,hashlib,bisect
from datetime import datetime,timedelta
from collections import defaultdict,Counter
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'engine'))
from backtestceo.quote_backtest import valid
from backtestceo.options_backtest import at
OUT=ROOT/'data/backtests/options-vwap-ema-3m-20260724-20261023';DEST=OUT/'loss-analysis';DEST.mkdir(exist_ok=True)
r=json.loads((OUT/'quote-results.json').read_text())
trades=sorted(r['trades'],key=lambda t:(t['entry_time'],t['symbol']))
assert len(trades)==r['closed_trades']==143
assert len({(t['symbol'],t['contract'],t['entry_time']) for t in trades})==143
by_day=defaultdict(lambda:defaultdict(list))
for i,t in enumerate(trades,1):
 t['trade_id']=f'T{i:03}'
 en=datetime.fromisoformat(t['entry_time']);ex=datetime.fromisoformat(t['exit_time'])
 t['direction']='CALL' if re.search(r'C\d{8}$',t['contract']) else 'PUT'
 t['hold_minutes']=(ex-en).total_seconds()/60
 t['dte']=(datetime.strptime(t['contract'][-15:-9],'%y%m%d').date()-en.date()).days
 t['entry_spread_pct']=100*t['entry_spread']/t['entry_ask']
 t['session']='morning' if en.hour<12 else 'afternoon'
 t['entry_bucket']=en.strftime('%H:')+('00' if en.minute<30 else '30')
 t['commission']=1.30*t['qty'];t['extra_slippage']=2*t['qty']
 t['spread_crossing_cost']=(t['entry_spread']+t['exit_spread'])/2*100*t['qty']
 t['midpoint_move_pnl']=((t['exit_bid']+t['exit_spread']/2)-(t['entry_ask']-t['entry_spread']/2))*100*t['qty']
 t['net_return_on_premium_pct']=100*t['net_pnl']/(t['entry_fill']*100*t['qty'])
 t['_en']=en.timestamp();t['_ex']=ex.timestamp();t['_postend']=min((ex+timedelta(minutes=30)).timestamp(),ex.replace(hour=15,minute=55,second=0).timestamp())
 t['max_bid_while_open']=None;t['min_bid_while_open']=None;t['max_bid_after_exit_30m']=None
 t['valid_held_samples']=0;t['valid_post_exit_samples']=0
 by_day[str(en.date())][t['contract']].append(t)
for day,contracts in sorted(by_day.items()):
 p=OUT/'databento-quotes'/f'{day}.csv.gz'
 m=json.loads(p.with_suffix('.json').read_text())
 assert hashlib.sha256(p.read_bytes()).hexdigest()==m['sha256']
 with gzip.open(p,'rt') as f:
  for row in csv.DictReader(f):
   c=row['symbol'].replace(' ','')
   if c not in contracts:continue
   try:q=(float(row['bid_px_00']),float(row['ask_px_00']),int(row['bid_sz_00']),int(row['ask_sz_00']))
   except (ValueError,TypeError):continue
   if not valid(q):continue
   sec=at(row['ts_recv']).timestamp();bid=q[0]
   for t in contracts[c]:
    if t['_en']<=sec<=t['_ex']:
     t['valid_held_samples']+=1
     t['max_bid_while_open']=bid if t['max_bid_while_open'] is None else max(bid,t['max_bid_while_open'])
     t['min_bid_while_open']=bid if t['min_bid_while_open'] is None else min(bid,t['min_bid_while_open'])
    elif t['_ex']<sec<=t['_postend']:
     t['valid_post_exit_samples']+=1
     t['max_bid_after_exit_30m']=bid if t['max_bid_after_exit_30m'] is None else max(bid,t['max_bid_after_exit_30m'])
 print('Audited quote paths',day,flush=True)
for t in trades:
 unit=t['qty']*100
 t['max_net_pnl_while_open']=None if t['max_bid_while_open'] is None else (t['max_bid_while_open']-.01-t['entry_fill'])*unit-t['commission']
 t['max_net_pnl_after_exit_30m']=None if t['max_bid_after_exit_30m'] is None else (t['max_bid_after_exit_30m']-.01-t['entry_fill'])*unit-t['commission']
 t['was_net_profitable_before_exit']=t['max_net_pnl_while_open'] is not None and t['max_net_pnl_while_open']>0
 t['recovered_to_net_breakeven_within_30m']=t['max_net_pnl_after_exit_30m'] is not None and t['max_net_pnl_after_exit_30m']>=0
 for k in list(t):
  if k.startswith('_'):del t[k]
win=[t for t in trades if t['net_pnl']>0];loss=[t for t in trades if t['net_pnl']<0]

def agg(ts):
 ls=[t for t in ts if t['net_pnl']<0];ws=[t for t in ts if t['net_pnl']>0]
 return dict(trades=len(ts),wins=len(ws),losses=len(ls),net_pnl=round(sum(t['net_pnl'] for t in ts),2),
    losing_dollars=round(sum(t['net_pnl'] for t in ls),2),winning_dollars=round(sum(t['net_pnl'] for t in ws),2),
    win_rate_pct=100*len(ws)/len(ts) if ts else None,
    median_hold_minutes=statistics.median(t['hold_minutes'] for t in ts) if ts else None)
result=dict(total=agg(trades),entry_fills=len(trades),exit_fills=len(trades),total_fills=2*len(trades),
 win_mean=statistics.mean(t['net_pnl'] for t in win),loss_mean=statistics.mean(t['net_pnl'] for t in loss),
 breakeven_win_rate_pct=100*(-statistics.mean(t['net_pnl'] for t in loss))/(statistics.mean(t['net_pnl'] for t in win)-statistics.mean(t['net_pnl'] for t in loss)),
 losses_were_profitable_before_exit=sum(t['was_net_profitable_before_exit'] for t in loss),
 losses_recovered_30m=sum(t['recovered_to_net_breakeven_within_30m'] for t in loss),
 losses_with_postexit_samples=sum(t['valid_post_exit_samples']>0 for t in loss),
 loss_duration_counts={str(m):sum(t['hold_minutes']<=m for t in loss) for m in [1,3,5,10,15]},
 cost_decomposition={k:round(sum(t[k] for t in trades),2) for k in ['midpoint_move_pnl','spread_crossing_cost','extra_slippage','commission']},
 cost_flipped_losses=sum(t['net_pnl']<0 and t['midpoint_move_pnl']>=0 for t in trades),
 groups={field:{str(k):agg([t for t in trades if t[field]==k]) for k in sorted({t[field] for t in trades})}
         for field in ['symbol','direction','reason','dte','session','entry_bucket']})
assert abs(sum(t['net_pnl'] for t in trades)-r['net_pnl'])<.001
cost=result['cost_decomposition'];assert abs(cost['midpoint_move_pnl']-cost['spread_crossing_cost']-cost['extra_slippage']-cost['commission']-r['net_pnl'])<.001
for name,ts in [('all-trades-enriched.csv',trades),('losing-trades.csv',sorted(loss,key=lambda t:t['net_pnl']))]:
 with (DEST/name).open('w') as f:
  w=csv.DictWriter(f,fieldnames=list(trades[0]));w.writeheader();w.writerows(ts)
(DEST/'summary.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
