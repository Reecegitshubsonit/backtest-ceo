"""Signal and trade parity between the paper runner's pure-Python rules and /workspace/backtests/backtest.py.
expected.json was produced by backtest.py itself on the same sample bars (fixtures/paper/make_fixtures.py)."""
import csv, json
from datetime import datetime
from pathlib import Path

import pytest

from backtestceo.paper import strategies as S

FX = Path(__file__).parent / "fixtures" / "paper"
EXP = json.loads((FX / "expected.json").read_text())


def load(name):
    with open(FX / f"{name}.csv") as f:
        return [dict(ts=datetime.fromisoformat(r["ts"]), o=float(r["open"]), h=float(r["high"]), l=float(r["low"]),
                     c=float(r["close"]), v=float(r["volume"])) for r in csv.DictReader(f)]


def norm(trades):
    return [(str(t["entry_time"]), str(t["exit_time"]), t["side"], round(t["entry"], 6), round(t["exit"], 6), t.get("contracts")) for t in trades]


@pytest.fixture(scope="module")
def eth4h():
    bars = S.resample(load("eth_1h"), 4)
    assert len(bars) == EXP["eth4h_bars"]
    return bars


@pytest.mark.parametrize("name", ["alphainsider", "supertrend"])
def test_4h_signals_and_trades_match_backtest(eth4h, name):
    sig = S.SIGNALS[name](eth4h)
    for k in ("le", "lx", "se", "sx"):
        mism = [i for i, (a, b) in enumerate(zip(sig[k], EXP[name]["signals"][k])) if a != b]
        assert not mism, f"{name}.{k} differs at bars {mism[:5]}"
    assert norm(S.replay_bars(eth4h, sig)) == norm(EXP[name]["trades"])


def test_ema_cross_with_stop_matches_backtest():
    bars = load("btc_1h")
    sig = S.sig_emacross(bars)
    for k in ("le", "lx"):
        assert sig[k] == EXP["emacross"]["signals"][k]
    assert norm(S.replay_bars(bars, sig)) == norm(EXP["emacross"]["trades"])


def test_first5m_qqq_matches_backtest():
    trades = S.first5m_replay(load("qqq_5m"), risk=200.0, pt=1.0, max_lev=4, equity=10_000.0)
    exp = EXP["first5m_qqq"]["trades"]
    # backtest.py sizes with its running equity; entries, exits and sides must match exactly
    assert [t[:5] for t in norm(trades)] == [t[:5] for t in norm(exp)]
