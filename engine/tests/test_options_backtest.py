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


def test_exact_one_dte_never_falls_back_to_same_day_or_next_week():
    groups={('2026-07-23','call'):[dict(symbol='0dte',strike_price='100')],
            ('2026-07-24','call'):[dict(symbol='1dte',strike_price='100')],
            ('2026-07-27','call'):[dict(symbol='monday',strike_price='100')]}
    assert choose_contract(groups,'2026-07-23',1,100,exact_dte=1)=='1dte'
    assert choose_contract(groups,'2026-07-24',1,100,exact_dte=1) is None
    assert choose_contract(groups,'2026-07-23',1,100)=='0dte'


def test_matched_comparison_preserves_exit_events_but_only_common_entries():
    from backtestceo.one_dte import matched_signals
    original=[dict(t='t1',symbol='SPY',side=1,contract='0DTE'),
              dict(t='t2',symbol='SPY',side=-1,contract='another'),
              dict(t='t3',symbol='SPY',exit_side=-1)]
    eligible=[dict(t='t1',symbol='SPY',side=1,contract='1DTE')]
    assert matched_signals(original,eligible)==[original[0],original[2]]


def test_exact_zero_dte_skips_later_expiry_instead_of_falling_back():
    groups={('2026-07-24','call'):[dict(symbol='same-day',strike_price='100')],
            ('2026-07-27','put'):[dict(symbol='later-put',strike_price='100')]}
    assert choose_contract(groups,'2026-07-24',1,100,exact_dte=0)=='same-day'
    assert choose_contract(groups,'2026-07-24',-1,100,exact_dte=0) is None
