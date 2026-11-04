"""python -m weather {scan,paper,live,calibrate,status}   (run from the kalshi/ folder)"""
from __future__ import annotations

import argparse
import json
import time
from dataclasses import asdict
from pathlib import Path

from kalshibot.client import KalshiClient
from kalshibot.runner import summary

from .model import WxConfig
from .trader import WxTrader, scan

DATA = Path("data")


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(prog="weather")
    ap.add_argument("--config", default="weather_config.json")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("scan", help="read-only: show mispriced temperature brackets now")
    s.add_argument("--json", action="store_true")
    for name in ("paper", "live"):
        p = sub.add_parser(name, help=f"{name} trade every --interval seconds")
        p.add_argument("--once", action="store_true")
        p.add_argument("--interval", type=int, default=900)
        if name == "live":
            p.add_argument("--live", action="store_true", help="required confirmation for real orders")
    c = sub.add_parser("calibrate", help="measure forecast error vs Kalshi settled values")
    c.add_argument("--days", type=int, default=60)
    c.add_argument("--series", nargs="*")
    b = sub.add_parser("backtest", help="walk-forward test on Kalshi's real past prices")
    b.add_argument("--days", type=int, default=58)
    b.add_argument("--series", nargs="*")
    st = sub.add_parser("status")
    st.add_argument("--live", action="store_true")
    a = ap.parse_args(argv)
    cfg = WxConfig.load(a.config)

    if a.cmd == "scan":
        opps = scan(KalshiClient(min_interval=0.25), cfg)
        if a.json:
            print(json.dumps([asdict(o) for o in opps], indent=1))
            return
        print(f"{'ticker':32} {'bracket':14} side  ask   model  edge   mu    sd   obs   lead")
        for o in opps:
            print(f"{o.ticker[:32]:32} {o.label[:14]:14} {o.side:4} {o.ask:.2f}  {o.p_model:.3f} {o.edge:+.3f} "
                  f"{o.mu:5.1f} {o.sd:4.1f} {'' if o.observed is None else o.observed:5} {o.lead}")
        print(f"{len(opps)} opportunities (read-only, nothing placed)")
    elif a.cmd in ("paper", "live"):
        live = a.cmd == "live"
        if live and not a.live:
            raise SystemExit("add --live to confirm real orders")
        t = WxTrader(KalshiClient(allow_trading=live, min_interval=0.25), cfg, DATA, live=live)
        if live:
            print(f"WEATHER LIVE MODE: real orders. Kill switch: touch {cfg.kill_file}")
        while True:
            try:
                for r in t.cycle():
                    if r["result"] == "bought" or r.get("reason") not in ("already_holding", "no_room_or_liquidity"):
                        print(json.dumps(r))
                print(time.strftime("%H:%M"), summary(t.state))
            except Exception as e:
                print("cycle error:", e)
            if a.once:
                return
            time.sleep(a.interval)
    elif a.cmd == "calibrate":
        from .calibrate import run

        run(KalshiClient(min_interval=0.25), a.series, a.days, Path(cfg.calibration_path))
        print(f"wrote {cfg.calibration_path}")
    elif a.cmd == "backtest":
        from .backtest import run as bt

        res = bt(KalshiClient(min_interval=0.25), cfg, a.series, a.days, DATA / "weather_backtest.json")
        print(f"\n{res['brackets']} quoted brackets | Brier model {res['brier_model']} vs market {res['brier_market']}"
              " (lower is better)")
        print(f"{'variant':18} {'bets':>5} {'win%':>6} {'staked':>8} {'pnl':>8} {'roi':>7} {'t':>6}")
        for k, v in {**res["variants"], "YOUR CONFIG": res["config_result"]}.items():
            if v.get("bets"):
                print(f"{k:18} {v['bets']:5d} {v['win_rate']:6.1%} {v['staked']:8.2f} {v['pnl']:+8.2f} {v['roi']:+7.1%} {v['t']:6.2f}")
            else:
                print(f"{k:18}     0")
        print("\nby city (your config):")
        for s_, v in res["by_station"].items():
            print(f"  {s_:4} {v['bets']:4d} bets  pnl {v['pnl']:+7.2f}  roi {v['roi']:+6.1%}  t {v['t']:5.2f}")
        print("details: data/weather_backtest.json")
    elif a.cmd == "status":
        path = DATA / ("wx_live_state.json" if a.live else "wx_paper_state.json")
        from kalshibot.paper import State

        stt = State.load(path, cfg.starting_cash)
        print(summary(stt))
        for p in stt.positions.values():
            print(f"  {p.ticker} {p.side} x{p.contracts} cost ${p.cost:.2f}")


if __name__ == "__main__":
    main()
