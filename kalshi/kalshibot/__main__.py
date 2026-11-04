"""CLI: python -m kalshibot {scan,paper,status,calibrate,account}"""
from __future__ import annotations

import argparse
import json
import sys
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
    cp = sub.add_parser("copy", help="paper copy-trading of followed traders")
    cp.add_argument("mode", choices=["stream", "serve", "inbox", "signal", "settle", "status"])
    cp.add_argument("text", nargs="?", help="for mode=signal: one JSON or notification text")
    cp.add_argument("--copy-config", default="copy_config.json")
    cp.add_argument("--host", default="127.0.0.1")
    cp.add_argument("--port", type=int, default=8787)
    cp.add_argument("--token", default=None, help="require X-Token header (default: $COPY_TOKEN)")
    cp.add_argument("--inbox", default=str(DATA / "signals.jsonl"))
    cp.add_argument("--state", default=str(DATA / "copy_state.json"))
    cp.add_argument("--journal", default=str(DATA / "copy_journal.jsonl"))
    cp.add_argument("--live", action="store_true", help='real orders (also needs "live": true in the copy config)')
    ld = sub.add_parser("leaders", help="rank Kalshi leaderboard traders by copyability (data: rivo.markets)")
    ld.add_argument("--refresh", action="store_true", help="re-download pages (otherwise use cache)")
    ld.add_argument("--cache", default=str(DATA / "rivo"))
    ld.add_argument("--top", type=int, default=10)
    ld.add_argument("--slippage", type=float, default=0.02)
    ld.add_argument("--write", default=None, help="write picks into this copy config (e.g. copy_config.json)")
    ld.add_argument("--feed", action="store_true",
                    help="re-score on $1,000+ trades from Rivo's API (what the stream carries); needs RIVO_API_KEY")
    ld.add_argument("--candidates", type=int, default=40, help="with --feed: how many page-ranked traders to re-score")
    ld.add_argument("--max-rows", type=int, default=120, help="with --feed: trades per trader (5,000/day budget)")
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
    elif a.cmd == "copy":
        import os

        from . import copy as cpy
        from .runner import summary

        ccfg = cpy.CopyConfig.load(a.copy_config)
        state, journal = Path(a.state), Path(a.journal)
        if a.live:
            client = KalshiClient(allow_trading=True)
            state, journal = state.with_name("live_state.json"), journal.with_name("live_journal.jsonl")
            print(f"LIVE MODE: real orders. Kill switch: touch {ccfg.kill_file}")
        eng = cpy.CopyEngine(client, ccfg, state, journal, live=a.live)
        if a.mode == "stream":
            from . import rivo_stream

            rivo_stream.run(eng, Path(a.state).with_name("rivo_stream.json"))
        elif a.mode == "serve":
            cpy.serve(eng, a.host, a.port, a.token or os.environ.get("COPY_TOKEN"))
        elif a.mode == "inbox":
            cpy.tail_inbox(eng, Path(a.inbox))
        elif a.mode == "signal":
            print(json.dumps(eng.handle(cpy.parse_signal(a.text)), indent=1))
        elif a.mode == "settle":
            eng.settle_all()
            print(summary(eng.state))
        else:
            print(summary(eng.state))
            for pos in eng.state.positions.values():
                print(f"  POS {pos.ticker} {pos.side} x{pos.contracts} cost ${pos.cost:.2f} via {eng.owner.get(pos.ticker, '?')}")
    elif a.cmd == "leaders":
        from . import leaders as L

        pages = L.fetch(None, Path(a.cache), refresh=a.refresh)
        keep, drop = L.rank(pages, L.Rules(slippage=a.slippage))
        if a.feed:
            import os
            from datetime import datetime, timedelta, timezone

            key = os.environ.get("RIVO_API_KEY") or sys.exit("Set RIVO_API_KEY")
            rules = L.Rules(slippage=a.slippage)
            # candidates: everyone not ruled out by structure (market maker / idle / parlays), best page t first
            structural = ("market maker", "idle", "parlays")
            pool = keep + sorted((t for t in drop if not any(r.startswith(structural) for r in t.reasons)
                                  and t.sim_n), key=lambda t: -(t.t_stat or -99))
            since = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
            scores = []
            for t in pool[:a.candidates]:
                rows = L.api_trades(key, t.name.lower(), since, a.max_rows)
                scores.append(L.score_feed(t.name.lower(), rows, rules))
                print(f"  {t.name}: {len(rows)} trades", file=sys.stderr)
            print(L.feed_report(scores, a.top))
            Path(a.cache, "_feed_scored.json").write_text(json.dumps([asdict(s) for s in scores], indent=1))
            if a.write:
                best = sorted((s for s in scores if not s.reasons), key=lambda s: -s.t)[:a.top]
                base = json.loads(Path(a.write).read_text()) if Path(a.write).exists() else {}
                base["traders"] = {s.name: 1.0 for s in best}
                Path(a.write).write_text(json.dumps(base, indent=1))
                print(f"wrote {len(best)} traders to {a.write}")
            return
        print(L.report(keep, drop, a.top))
        L.dump(keep, drop, Path(a.cache) / "_scored.json")
        if a.write:
            L.write_config(keep, Path(a.write), a.top, Path("copy_config.example.json"))
            print(f"wrote top {min(a.top, len(keep))} to {a.write}")
    elif a.cmd == "account":
        print(json.dumps({"balance": client.balance(), "positions": client.positions()}, indent=1))


if __name__ == "__main__":
    main()
