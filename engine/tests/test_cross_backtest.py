from datetime import datetime,timedelta
from copy import deepcopy
from backtestceo.cross_backtest import NY,study,indicators


def session():
    start=datetime(2026,7,24,9,30,tzinfo=NY)
    return [dict(t=start+timedelta(minutes=3*i),o=100.,h=101.,l=99.,c=100.,v=100,pv=10000,complete=True,
                 signal=0,trend=1,atr=1.,ready=True,vol_ok=True) for i in range(130)]


def test_confirmed_signal_enters_next_open_and_two_total_losses_lock_portfolio():
    bars=session()
    for i in (4,8,11):bars[i]['signal']=1
    for i in (5,9):bars[i]['signal']=-1;bars[i]['trend']=-1
    for i in (6,10):bars[i]['o']=99
    trades,coverage,blocked=study({'SPY':{'2026-07-24':bars}})
    assert len(trades)==2 and blocked=={'SPY':1}
    assert trades[0]['entry_time'].startswith('2026-07-24T09:45')
    assert trades[0]['exit_time'].startswith('2026-07-24T09:48')
    assert all(t['net_bps']<0 for t in trades)


def test_missing_minutes_exclude_session_instead_of_inventing_fills():
    bars=session();bars[12]['complete']=False
    trades,coverage,_=study({'SPY':{'2026-07-24':bars}})
    assert trades==[]
    assert coverage['SPY']['incomplete_sessions']==['2026-07-24']


def test_indicator_future_changes_cannot_change_prior_signals():
    bars=session()
    for i,b in enumerate(bars):
        b['c']=100+i/100;b['pv']=b['c']*b['v']
    prefix=indicators({'2026-07-24':deepcopy(bars[:80])})['2026-07-24']
    full=indicators({'2026-07-24':deepcopy(bars)})['2026-07-24']
    for a,b in zip(prefix,full):
        for k in ('signal','trend','atr','vol_ok'):assert a[k]==b[k]
