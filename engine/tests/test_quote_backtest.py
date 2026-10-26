from datetime import datetime,timedelta
from backtestceo.quote_backtest import run,valid
from backtestceo.cross_backtest import NY
from backtestceo.databento_quotes import api_key,occ


def test_credentials_use_only_valid_token_not_accidentally_pasted_trailing_text(monkeypatch):
    key='db-'+'a'*29
    monkeypatch.setenv('DATABENTO_API_KEY',key+' extra pasted label and text')
    assert api_key()==key
    assert occ('SPY260724C00600000')=='SPY   260724C00600000'


def test_quote_validity_rejects_missing_crossed_and_non_executable_sizes():
    assert valid((1,1.1,1,1))
    assert not valid((1.2,1.1,1,1))
    assert not valid((1,1.1,0,1))
    assert not valid((float('nan'),1.1,1,1))


def test_quotes_execute_after_latency_at_actual_sides_and_count_net_losses(monkeypatch):
    now=datetime(2026,7,24,10,0,tzinfo=NY);base=int(now.timestamp())
    signals=[dict(t=now+timedelta(minutes=i),symbol='SPY',contract='C',side=1) for i in (0,1,2)]
    quotes={}
    for minute in (0,1,2):
        t=base+minute*60
        quotes[t+1]=[('C',(.99,1.,1,1))]
        quotes[t+2]=[('C',(.70,.71,1,1))]
        quotes[t+3]=[('C',(.60,.61,1,1))]
    monkeypatch.setattr('backtestceo.quote_backtest.read_day',lambda day:(quotes,0))
    r=run(signals)
    assert r['closed_trades']==2
    assert r['trades'][0]['entry_fill']==1.01
    assert r['trades'][0]['exit_fill']==.59
    assert r['trades'][0]['exit_time'].startswith('2026-07-24T10:00:03')
    assert r['rejections']['two_loss_daily_lock']==1
    assert r['net_pnl']==round(sum(t['net_pnl'] for t in r['trades']),2)


def test_missing_quote_is_never_filled_from_future_or_synthetic_price(monkeypatch):
    now=datetime(2026,7,24,10,0,tzinfo=NY)
    monkeypatch.setattr('backtestceo.quote_backtest.read_day',lambda day:({},0))
    r=run([dict(t=now,symbol='SPY',contract='C',side=1)])
    assert r['closed_trades']==0 and r['net_pnl']==0
    assert r['rejections']['no_valid_quote_within_5s']==1


def test_open_exposure_invalidates_final_equity_when_exit_quotes_missing(monkeypatch):
    now=datetime(2026,7,24,10,0,tzinfo=NY)
    q={int(now.timestamp())+1:[('C',(.99,1.,1,1))]}
    monkeypatch.setattr('backtestceo.quote_backtest.read_day',lambda day:(q,0))
    r=run([dict(t=now,symbol='SPY',contract='C',side=1)])
    assert r['ending_equity'] is None and r['net_pnl'] is None
    assert r['unresolved_positions'] and not r['drawdown_complete']


def test_target_is_not_a_guaranteed_fill_price_after_latency(monkeypatch):
    now=datetime(2026,7,24,10,0,tzinfo=NY);base=int(now.timestamp())
    quotes={base+1:[('C',(.99,1.,1,1))],base+2:[('C',(1.60,1.61,1,1))],base+3:[('C',(1.40,1.41,1,1))]}
    monkeypatch.setattr('backtestceo.quote_backtest.read_day',lambda day:(quotes,0))
    r=run([dict(t=now,symbol='SPY',contract='C',side=1)])
    assert r['trades'][0]['reason']=='premium_target'
    assert r['trades'][0]['exit_fill']==1.39
    assert r['trades'][0]['exit_fill']<r['trades'][0]['entry_fill']*1.5


def test_premium_budget_rejects_unaffordable_contract_instead_of_fractional_options(monkeypatch):
    now=datetime(2026,7,24,10,0,tzinfo=NY);base=int(now.timestamp())
    monkeypatch.setattr('backtestceo.quote_backtest.read_day',lambda day:({base+1:[('C',(4.,4.10,10,10))]},0))
    r=run([dict(t=now,symbol='SPY',contract='C',side=1)])
    assert r['closed_trades']==0
    assert r['rejections']['premium_budget_cash_or_size']==1
    assert r['ending_equity']==10000
