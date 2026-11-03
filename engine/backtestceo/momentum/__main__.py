"""python -m backtestceo.momentum {backtest|sweep|scan|paper} ...  (run from engine/)"""
import argparse
import sys
from pathlib import Path

from .config import Config, parse_overrides


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m backtestceo.momentum")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("backtest", "sweep"):
        p = sub.add_parser(name)
        p.add_argument("--days", type=int, default=60)
        p.add_argument("--set", nargs="*", default=[], metavar="key=value")
        p.add_argument("--out", default=str(Path(__file__).resolve().parents[3] / "docs" / "momentum-backtest"))
    p = sub.add_parser("scan", help="one live scanner pass (read-only)")
    p.add_argument("--set", nargs="*", default=[], metavar="key=value")
    p = sub.add_parser("paper", help="Alpaca paper trading loop")
    p.add_argument("--set", nargs="*", default=[], metavar="key=value")
    p.add_argument("--live", action="store_true", help="send orders to the Alpaca PAPER account (default: dry run)")
    p.add_argument("--once", action="store_true", help="one scan+signal pass, then exit")
    a = ap.parse_args(argv)
    cfg = Config().with_(**parse_overrides(a.set))

    if a.cmd in ("backtest", "sweep"):
        from . import backtest as bt
        from .data import Data
        data = Data()
        days, uni, minute = bt.prepare(data, a.days, cfg)
        if a.cmd == "backtest":
            trades, scanned, halts = bt.run(days, uni, minute, cfg)
            st = bt.stats(trades, days, cfg)
            bt.write(Path(a.out), cfg, trades, scanned, halts, st)
            print(bt.fmt(st))
            print(f"wrote {a.out}")
        else:
            rows = []
            for name, kw in bt.SWEEP.items():
                c = cfg.with_(**kw)
                trades, _, _ = bt.run(days, uni, minute, c)
                st = bt.stats(trades, days, c)
                rows.append((name, st))
                print(f"{name:28s} trades={st['trades']:4d} pnl={st['net_pnl']:9.2f} wr={st['win_rate']:.3f} "
                      f"pf={st['profit_factor']} avgR={st['avg_r']} maxDD={st['max_drawdown_usd']}", flush=True)
            Path(a.out).mkdir(parents=True, exist_ok=True)
            with open(Path(a.out) / "sweep.md", "w") as f:
                f.write("| variant | trades | net P&L $ | win rate | profit factor | avg R | max DD $ |\n|---|---:|---:|---:|---:|---:|---:|\n")
                for name, st in rows:
                    f.write(f"| {name} | {st['trades']} | {st['net_pnl']:.0f} | {st['win_rate']:.0%} | {st['profit_factor']} | "
                            f"{st['avg_r']} | {st['max_drawdown_usd']:.0f} |\n")
    else:
        from . import paper
        return paper.main(a, cfg)


if __name__ == "__main__":
    sys.exit(main())
