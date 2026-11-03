"""CLI: python -m kalshibot {scan,paper,status,calibrate,account}"""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from .client import KalshiClient
from .model import Config
from .paper import State

DATA = Path("data")


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(prog="kalshibot")
    ap.add_argument("--config", default="config.json")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("scan", help="read-only: print the bids the strategy would rest now")
    s.add_argument("--max-books", type=int, default=150)
    s.add_argument("--json", action="store_true")
    p = sub.add_parser("paper", help="paper trade against the live public tape")
    p.add_argument("--once", action="store_true")
    p.add_argument("--interval", type=int, default=60)
    p.add_argument("--max-books", type=int, default=150)
    p.add_argument("--state", default=str(DATA / "paper_state.json"))
    p.add_argument("--journal", default=str(DATA / "paper_journal.jsonl"))
    st = sub.add_parser("status", help="print paper book")
    st.add_argument("--state", default=str(DATA / "paper_state.json"))
    c = sub.add_parser("calibrate", help="measure longshot bias on settled markets")
    c.add_argument("--days", type=int, default=60)
    c.add_argument("--hours-before", type=float, default=24)
    c.add_argument("--min-volume", type=float, default=500)
    c.add_argument("--max-markets", type=int, default=1500)
    c.add_argument("--out", default=str(DATA / "calibration.json"))
    sub.add_parser("account", help="authenticated read-only: balance and positions (checks your keys)")
    a = ap.parse_args(argv)

    cfg = Config.load(a.config)
    client = KalshiClient()

    if a.cmd == "scan":
        from .runner import scan

        qs = scan(client, cfg, max_books=a.max_books)
        if a.json:
            print(json.dumps([asdict(q) for q in qs], indent=1))
            return
        print(f"{'ticker':40} side  bid   ask   ours  model  edge   n   queue  title")
        for q in qs:
            print(f"{q.ticker[:40]:40} {q.side:4} {q.best_bid:.2f}  {q.best_ask:.2f}  {q.price:.2f}  "
                  f"{q.p_model:.3f} {q.edge:+.3f} {q.contracts:3d} {q.queue_ahead:6.0f}  {q.title[:50]}")
        print(f"{len(qs)} quotes (read-only, nothing placed)")
    elif a.cmd == "paper":
        from .runner import paper_cycle, run_forever

        if a.once:
            paper_cycle(client, cfg, Path(a.state), Path(a.journal), a.max_books)
        else:
            run_forever(client, cfg, Path(a.state), Path(a.journal), a.interval, a.max_books)
    elif a.cmd == "status":
        from .runner import summary

        stt = State.load(Path(a.state), cfg.starting_cash)
        print(summary(stt))
        for pos in stt.positions.values():
            print(f"  POS {pos.ticker} {pos.side} x{pos.contracts} cost ${pos.cost:.2f}")
        for o in stt.orders.values():
            print(f"  BID {o.ticker} {o.side} {o.remaining}@{o.price:.2f} queue {o.queue_ahead:.0f} edge {o.edge:+.3f}")
    elif a.cmd == "calibrate":
        from .calibrate import run

        res = run(client, a.days, a.hours_before, a.min_volume, a.max_markets, Path(a.out))
        print(f"{res['markets']} markets, price {a.hours_before}h before close")
        print(f"{'bin':10} {'n':>5} {'q':>6} {'win%':>6} {'ratio':>6} {'maker$':>7} {'taker$':>7}")
        for b in res["buckets"]:
            print(f"{b['bin']:10} {b['n']:5d} {b['mean_longshot_price']:6.3f} {b['longshot_win_rate']:6.3f} "
                  f"{b['ratio'] or 0:6.2f} {b['fav_edge_maker']:+7.4f} {b['fav_edge_taker']:+7.4f}")
        print(f"wrote {a.out}; set \"calibration_path\" in config.json to use it")
    elif a.cmd == "account":
        print(json.dumps({"balance": client.balance(), "positions": client.positions()}, indent=1))


if __name__ == "__main__":
    main()
