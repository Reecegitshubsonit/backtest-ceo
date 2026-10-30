from backtestceo.filter_experiment import early_side

def b(gap,atr=1):return dict(ema_vwap_gap=gap,atr=atr)

def test_early_signal_precedes_cross_without_future_data():
    assert early_side(b(-.2),b(-.08))==1
    assert early_side(b(.2),b(.08))==-1
    assert early_side(b(-.08),b(.02))==0
    assert early_side(b(-.08),b(-.1))==0
    assert early_side(b(-.8),b(-.3))==0
    assert early_side(b(-.2),b(-.08,None))==0


def test_ten_percent_premium_limit_admits_one_contract_without_changing_stop(monkeypatch):
    from datetime import datetime
    from backtestceo.cross_backtest import NY
    from backtestceo.quote_backtest import run
    now=datetime(2026,7,24,10,0,tzinfo=NY);sec=int(now.timestamp())
    quotes={sec+1:[('C',(7.99,8.,1,1))],sec+2:[('C',(5.,5.01,1,1))],sec+3:[('C',(4.99,5.,1,1))]}
    monkeypatch.setattr('backtestceo.quote_backtest.read_day',lambda day:(quotes,0))
    signals=[dict(t=now,symbol='SPY',contract='C',side=1)]
    assert run(signals,premium_budget=.05)['closed_trades']==0
    r=run(signals,premium_budget=.10)
    assert r['closed_trades']==1 and r['trades'][0]['qty']==1
    assert r['trades'][0]['reason']=='premium_stop'
    assert r['trades'][0]['net_pnl']<0
