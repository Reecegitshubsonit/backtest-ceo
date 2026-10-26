from datetime import datetime,timedelta
from backtestceo.options_backtest import NY,simulate,choose_contract


def t(h,m):return datetime(2026,7,24,h,m,tzinfo=NY)


def test_option_losses_include_fees_and_lock_after_two_total_losses():
    signals=[dict(t=t(10,m),symbol='SPY',contract='C',side=1) for m in (0,3,6)]
    tape={}
    for m in (0,3,6):tape[t(10,m)]=dict(o=1,h=2,l=.5,c=1,v=100)
    r=simulate(signals,{('C','2026-07-24'):tape},.10)
    assert r['closed_trades']==2
    assert all(x['qty']==1 and x['reason']=='stop_intrabar' for x in r['trades'])
    assert r['rejections']['two_loss_daily_lock']==1
    assert r['net_pnl']==round(sum(x['net_pnl'] for x in r['trades']),2)
    assert r['unresolved_positions']==[]


def test_no_future_bar_entry_when_exact_next_minute_is_missing():
    signal=dict(t=t(10,0),symbol='SPY',contract='C',side=1)
    tape={t(10,1):dict(o=1,h=1,l=1,c=1,v=100)}
    r=simulate([signal],{('C','2026-07-24'):tape},.10)
    assert r['closed_trades']==0 and r['rejections']['no_next_minute_option_trade']==1


def test_unpriced_exit_keeps_exposure_and_prevents_final_profit_claim():
    signal=dict(t=t(10,0),symbol='SPY',contract='C',side=1)
    tape={t(10,0):dict(o=1,h=1,l=1,c=1,v=100)}
    r=simulate([signal],{('C','2026-07-24'):tape},.10)
    assert r['unresolved_positions'] and r['net_pnl'] is None and r['ending_equity'] is None


def test_atm_contract_selection_uses_only_expirations_on_or_after_session():
    groups={('2026-07-23','call'):[dict(symbol='expired',strike_price='100')],
            ('2026-07-24','call'):[dict(symbol='ATM',strike_price='100'),dict(symbol='OTM',strike_price='105')]}
    assert choose_contract(groups,'2026-07-24',1,101)=='ATM'
