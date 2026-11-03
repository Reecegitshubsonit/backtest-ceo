"""Walk-forward check: grid-search 32 variants on the first 30 sessions, score them on the last 30.

    python -m backtestceo.momentum.walkforward
"""
import itertools

from . import backtest as bt
from .config import Config
from .data import Data


def main():
    cfg = Config()
    days, uni, minute = bt.prepare(Data(), 60, cfg)
    A, B = days[:30], days[30:]
    grid = {"min_gap_pct": [10, 20], "min_rvol": [5, 10], "patterns": [cfg.patterns, ("first_pullback",)], "bailout_bars": [5, 0], "entry_until": ["11:00", "10:30"]}
    res = []
    for vals in itertools.product(*grid.values()):
        c = cfg.with_(**dict(zip(grid, vals)))
        ta, _, _ = bt.run(A, uni, minute, c); tb, _, _ = bt.run(B, uni, minute, c)
        sa, sb = bt.stats(ta, A, c), bt.stats(tb, B, c)
        res.append((sa["net_pnl"], sb["net_pnl"], sa["trades"], sb["trades"], dict(zip(grid, vals))))
    res.sort(key=lambda r: -r[0])
    for r in res[:8]: print("IS %8.0f OOS %8.0f  n=%d/%d  %s" % r)
    print("best-IS OOS:", res[0][1], " mean OOS of all:", sum(r[1] for r in res)/len(res), " OOS>0 count:", sum(r[1]>0 for r in res), "/", len(res))


if __name__ == "__main__":
    main()
