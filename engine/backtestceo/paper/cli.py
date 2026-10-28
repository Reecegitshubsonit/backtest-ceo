"""python -m backtestceo.paper <command>

  check                     safety rules, which key NAMES are present (never values), kill switch state
  start [--dry-run]         start the runner in the background (pid file in the state dir)
  run   [--dry-run]         run in the foreground (what `start` launches)
  stop                      stop the background runner (SIGTERM; open paper positions are left as they are)
  status                    pid, mode, per-strategy status, positions and P&L
  kill | unkill             create / remove the KILL file (same effect as PAPER_TRADING_KILL_SWITCH=1)
  smoke-test --confirm      one tiny paper order per broker (see --help); without --confirm it only prints the plan
"""
import argparse
import json
import math
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import config as C
from . import envfile
from .brokers import ALPACA_MIN_CRYPTO_NOTIONAL, AlpacaPaperBroker, FakeBroker, WebullSandboxBroker, new_client_order_id
from .feed import LiveEvents
from .marketdata import AlpacaData, ReplayData, load_csv
from .runner import Runner
from .safety import KillSwitchEngaged, SafetyError, check_env, kill_switch_on, require_paper

REPO = Path(__file__).resolve().parents[3]
DEFAULT_ENV = REPO / ".env"
DEFAULT_STATE = Path(os.environ.get("BACKTEST_CEO_CACHE", str(Path.home() / ".cache" / "backtest-ceo"))) / "paper"
FIXTURES = REPO / "engine" / "tests" / "fixtures" / "paper"


def _args(argv):
    p = argparse.ArgumentParser(prog="python -m backtestceo.paper", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("command", choices=["check", "start", "run", "stop", "status", "kill", "unkill", "smoke-test"])
    p.add_argument("--dry-run", action="store_true", help="fake brokers + replayed sample bars on a simulated clock; no keys, no network except the local feed")
    p.add_argument("--env-file", default=str(DEFAULT_ENV), help="read-only; only the variable names the runner needs are read")
    p.add_argument("--config", help="JSON overrides (caps can only be tightened)")
    p.add_argument("--state-dir", default=str(DEFAULT_STATE))
    p.add_argument("--live-events", default=None, help="live-events URL (default http://127.0.0.1:8030)")
    p.add_argument("--no-feed", action="store_true", help="do not post to the live-events service (events still go to events.jsonl)")
    p.add_argument("--sim-start", default="2026-09-01T13:00:00+00:00", help="dry run: simulated start time")
    p.add_argument("--sim-hours", type=float, default=72, help="dry run: simulated hours to run")
    p.add_argument("--sim-step-min", type=float, default=5, help="dry run: simulated minutes per tick")
    p.add_argument("--sim-sleep", type=float, default=0.02, help="dry run: real seconds per tick")
    p.add_argument("--confirm", action="store_true", help="smoke-test: actually send the paper orders")
    p.add_argument("--broker", choices=["alpaca", "webull", "both"], default="both", help="smoke-test: which broker(s)")
    p.add_argument("--extended-hours", action="store_true", help="smoke-test: Webull LIMIT order in the extended session (support_trading_session=ALL)")
    p.add_argument("--alpaca-notional", type=float, default=10.0, help="smoke-test: Alpaca BTC/USD buy size in USD (Alpaca minimum $10)")
    return p.parse_args(argv)


def _state_dir(a, dry):
    d = Path(a.state_dir) / ("dry-run" if dry else "live")
    d.mkdir(parents=True, exist_ok=True)
    return d


def _env(a):
    return envfile.load(a.env_file, os.environ)


def _kill_check(a, env, sdir):
    reader = (lambda: envfile.read(a.env_file, ("PAPER_TRADING_KILL_SWITCH",))) if Path(a.env_file).expanduser().exists() else None
    return lambda: kill_switch_on(env, sdir / "KILL", reader)


def _feed(a, cfg, sdir, label):
    return LiveEvents(a.live_events or cfg.live_events_url, source=f"paper-runner · {label}"[:80], log_path=sdir / "events.jsonl", enabled=not a.no_feed)


def build(a, dry):
    cfg = C.load(a.config)
    sdir = _state_dir(a, dry)
    if dry:
        env = envfile.Env()
        kill = _kill_check(a, envfile.Env(PAPER_TRADING_KILL_SWITCH=os.environ.get("PAPER_TRADING_KILL_SWITCH", "")), sdir)
        series = {("ETH/USD", 60): load_csv(FIXTURES / "eth_1h.csv"), ("BTC/USD", 60): load_csv(FIXTURES / "btc_1h.csv"),
                  ("QQQ", 5): load_csv(FIXTURES / "qqq_5m.csv")}
        for sym in sorted({s.symbol for s in cfg.strategies if s.rule in ("sip", "rsi2", "overnight")}):
            for m, suffix in ((5, "5m"), (1440, "1d")):
                f = FIXTURES / f"{sym.lower()}_{suffix}.csv"
                if f.exists():
                    series[(sym, m)] = load_csv(f)
        data = ReplayData(series)
        data.now = datetime.fromisoformat(a.sim_start)
        brokers = {"alpaca": FakeBroker("alpaca", data.last_price, kill, crypto_fee=0.0025), "webull": FakeBroker("webull", data.last_price, kill)}
        feed = _feed(a, cfg, sdir, "DRY RUN · fake brokers, replayed bars")
        return Runner(cfg, data, brokers, feed, kill, sdir / "state.json", mode="dry-run"), sdir
    env = _env(a)
    require_paper(env)  # WEBULL_ENV=sandbox, ALPACA_PAPER_TRADING_ONLY=true, paper/sandbox URLs only
    kill = _kill_check(a, env, sdir)
    akey, asec = env.first(envfile.ALPACA_KEY_VARS), env.first(envfile.ALPACA_SECRET_VARS)
    brokers = {}
    if any(s.broker == "alpaca" and s.enabled for s in cfg.strategies):
        brokers["alpaca"] = AlpacaPaperBroker(akey, asec, kill)
    if any(s.broker == "webull" and s.enabled for s in cfg.strategies):
        brokers["webull"] = WebullSandboxBroker(env.first(envfile.WEBULL_KEY_VARS), env.first(envfile.WEBULL_SECRET_VARS),
                                                env.first(envfile.WEBULL_ACCOUNT_VARS), kill, region=env.get("WEBULL_REGION") or "us",
                                                token_dir=sdir / "webull-token")
    data = AlpacaData(akey, asec, feed=env.get("ALPACA_DATA_FEED") or "iex")
    feed = _feed(a, cfg, sdir, "PAPER · Alpaca paper + Webull sandbox")
    return Runner(cfg, data, brokers, feed, kill, sdir / "state.json", mode="paper"), sdir


def cmd_check(a):
    env = _env(a)
    print(f"env file: {a.env_file} ({'found' if Path(a.env_file).expanduser().exists() else 'NOT FOUND'}; values are never shown)")
    ok_all = True
    for rule, ok, detail in check_env(env):
        ok_all &= ok
        print(f"  [{'PASS' if ok else 'FAIL'}] {rule} - {detail}")
    for label, names in (("Alpaca key", envfile.ALPACA_KEY_VARS), ("Alpaca secret", envfile.ALPACA_SECRET_VARS), ("Webull app key", envfile.WEBULL_KEY_VARS),
                         ("Webull app secret", envfile.WEBULL_SECRET_VARS), ("Webull account id (optional)", envfile.WEBULL_ACCOUNT_VARS)):
        found = [n for n in names if env.get(n)]
        print(f"  {label}: {'present as ' + found[0] if found else 'missing (' + ' | '.join(names) + ')'}")
    fd = (env.get("ALPACA_DATA_FEED") or "iex").strip().lower()
    print(f"  Alpaca stock data feed (5m bars, quotes): {fd if fd in ('iex', 'sip', 'delayed_sip', 'otc', 'boats') else 'custom'}; daily bars: sip")
    sdir = _state_dir(a, False)
    print(f"  kill switch: {'ON' if _kill_check(a, env, sdir)() else 'off'}")
    return 0 if ok_all else 2


def _pidfile(a, dry):
    return _state_dir(a, dry) / "runner.pid"


def _alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def cmd_run(a):
    r, sdir = build(a, a.dry_run)
    pf = sdir / "runner.pid"
    pf.write_text(str(os.getpid()))
    stop = {"v": False}
    signal.signal(signal.SIGTERM, lambda *_: stop.update(v=True))
    signal.signal(signal.SIGINT, lambda *_: stop.update(v=True))
    try:
        if a.dry_run:
            t0, step = datetime.fromisoformat(a.sim_start), timedelta(minutes=a.sim_step_min)
            n = {"i": 0}

            def clock():
                return t0 + n["i"] * step

            def sleep(_):
                n["i"] += 1
                time.sleep(a.sim_sleep)
            r.run(clock, sleep=sleep, max_ticks=int(a.sim_hours * 60 / a.sim_step_min), publish_every=12, should_stop=lambda: stop["v"])
        else:
            r.run(lambda: datetime.now(timezone.utc), should_stop=lambda: stop["v"])
    finally:
        if pf.exists() and pf.read_text().strip() == str(os.getpid()):
            pf.unlink()
    return 0 if not r.halted else 3


def cmd_start(a):
    pf = _pidfile(a, a.dry_run)
    if pf.exists() and _alive(int(pf.read_text() or 0)):
        print(f"already running (pid {pf.read_text().strip()})")
        return 1
    if not a.dry_run:
        require_paper(_env(a))  # fail fast in the foreground, before daemonising
    argv = [sys.executable, "-m", "backtestceo.paper", "run"] + [x for x in sys.argv[2:]]
    logf = open(_state_dir(a, a.dry_run) / "runner.log", "a")
    p = subprocess.Popen(argv, cwd=str(REPO / "engine"), stdout=logf, stderr=subprocess.STDOUT, start_new_session=True)
    time.sleep(1.5)
    if p.poll() is not None:
        print(f"runner exited immediately (code {p.returncode}); see {logf.name}")
        return 1
    print(f"started {'DRY RUN' if a.dry_run else 'PAPER'} runner, pid {p.pid}; log {logf.name}")
    return 0


def cmd_stop(a):
    rc = 1
    for dry in (False, True):
        pf = _pidfile(a, dry)
        if pf.exists():
            pid = int(pf.read_text() or 0)
            if pid and _alive(pid):
                os.kill(pid, signal.SIGTERM)
                for _ in range(50):
                    if not _alive(pid):
                        break
                    time.sleep(0.2)
                print(f"stopped {'dry-run' if dry else 'paper'} runner (pid {pid})")
                rc = 0
            pf.unlink(missing_ok=True)
    if rc:
        print("no runner running")
    return 0


def cmd_status(a):
    for dry in (False, True):
        sdir = _state_dir(a, dry)
        pf, sf = sdir / "runner.pid", sdir / "state.json"
        running = pf.exists() and _alive(int(pf.read_text() or 0))
        if not sf.exists() and not running:
            continue
        st = json.loads(sf.read_text()) if sf.exists() else {}
        print(f"{'DRY RUN' if dry else 'PAPER'}: {'running pid ' + pf.read_text().strip() if running else 'not running'}; updated {st.get('updated')}"
              + (f"; HALTED: {st['halted']}" if st.get("halted") else ""))
        for k, v in st.get("strategies", {}).items():
            p = v.get("pos")
            pos = f"{p['side']} {p['qty']:g} @ {p['entry']:.2f}" if p else "flat"
            print(f"  {k:18s} {v.get('status', ''):40s} {pos:28s} realized ${v.get('realized_usd', 0):,.2f}  fills {len(v.get('fills', []))}")
    print(f"kill file: {'present' if (_state_dir(a, False) / 'KILL').exists() else 'absent'}")
    return 0


def cmd_kill(a, on):
    for dry in (False, True):
        f = _state_dir(a, dry) / "KILL"
        f.touch() if on else f.unlink(missing_ok=True)
    print("KILL file " + ("created: no orders will be sent; a running runner halts on its next loop" if on else "removed"))
    return 0


def smoke(a, brokers, data, feed, kill, log=print):
    """One tiny paper order per broker. Alpaca: $10 BTC/USD market buy, then sell the filled qty back.
    Webull: QQQ LIMIT buy of 1 share at the current ask (extended session with --extended-hours); if it fills it is
    sold back at the bid with a LIMIT order, otherwise it is cancelled after 30 s."""
    out = {}
    if kill():
        raise KillSwitchEngaged("kill switch is on: smoke test not run")
    if "alpaca" in brokers:
        if a.alpaca_notional < ALPACA_MIN_CRYPTO_NOTIONAL:
            raise ValueError(f"--alpaca-notional must be at least ${ALPACA_MIN_CRYPTO_NOTIONAL:.0f} (Alpaca crypto minimum)")
        b = brokers["alpaca"]
        before = b.position_qty("BTC/USD") or 0.0
        o = b.submit("BTC/USD", "buy", notional=a.alpaca_notional, client_order_id=new_client_order_id("smoke"))
        o = b.wait_fill(o["client_order_id"]) if o["status"] != "filled" else o
        res = dict(buy=o)
        if o["status"] == "filled" and o["filled_qty"] > 0:
            held = b.position_qty("BTC/USD") or 0.0
            res["position_after_fees"] = held
            if before <= 0:
                # nothing else held BTC: DELETE /v2/positions/BTCUSD liquidates exactly what is there
                c = b.close_position("BTC/USD")
                res["close"] = b.wait_fill(c["client_order_id"]) if c and c.get("client_order_id") and c["status"] != "filled" else c
            else:
                # other BTC (e.g. a runner position) is held: sell only what this buy added, after fees
                q = math.floor(max(0.0, min(held - before, o["filled_qty"])) * 1e9) / 1e9
                s = b.submit("BTC/USD", "sell", qty=q, client_order_id=new_client_order_id("smoke"))
                res["sell"] = b.wait_fill(s["client_order_id"]) if s["status"] != "filled" else s
        out["alpaca"] = res
    if "webull" in brokers:
        b = brokers["webull"]
        q = data.quote("QQQ")
        limit = round(q["ask"], 2)
        if hasattr(b, "preview"):
            out.setdefault("webull", {})["preview"] = b.preview("QQQ", "buy", qty=1, notional=None, order_type="limit", limit_price=limit, extended_hours=a.extended_hours)
        o = b.submit("QQQ", "buy", qty=1, order_type="limit", limit_price=limit, extended_hours=a.extended_hours, client_order_id=new_client_order_id("smoke"))
        o = b.wait_fill(o["client_order_id"], timeout=30) if o["status"] != "filled" else o
        res = out.setdefault("webull", {})
        res.update(quote=q, buy=o)
        if o["status"] == "filled":
            q2 = data.quote("QQQ")
            s = b.submit("QQQ", "sell", qty=1, order_type="limit", limit_price=round(q2["bid"], 2), extended_hours=a.extended_hours, client_order_id=new_client_order_id("smoke"))
            s = b.wait_fill(s["client_order_id"], timeout=30) if s["status"] != "filled" else s
            if s["status"] != "filled":
                s = b.cancel(s["client_order_id"])
            res["sell"] = s
        else:
            res["cancel"] = b.cancel(o["client_order_id"])
    for name, r in out.items():
        feed.emit(dict(kind="agent_activity", slot="risk", task=f"RULE-BASED · smoke test {name}", state="working",
                       log=json.dumps({k: (v.get("status") if isinstance(v, dict) and "status" in v else v) for k, v in r.items() if k != "preview"}, default=str)[:300]))
    feed.flush()
    return out


def cmd_smoke(a):
    which = ["alpaca", "webull"] if a.broker == "both" else [a.broker]
    plan = [f"Alpaca paper: market BUY ${a.alpaca_notional:.2f} of BTC/USD (gtc), then sell back the post-fee position (DELETE /v2/positions/BTCUSD if no other BTC is held)",
            f"Webull sandbox: LIMIT BUY 1 QQQ at the latest ask ({'extended session ALL' if a.extended_hours else 'CORE session'}, DAY);"
            " sell back at the bid if filled, else cancel after 30 s"]
    plan = [p for p, n in zip(plan, ["alpaca", "webull"]) if n in which]
    if not a.confirm and not a.dry_run:
        print("smoke test plan (nothing sent; add --confirm to send):\n  " + "\n  ".join(plan))
        return 0
    if a.dry_run:
        r, sdir = build(a, True)
        r.data.now = datetime.fromisoformat(a.sim_start)
        brokers = {k: v for k, v in r.brokers.items() if k in which}
        res = smoke(a, brokers, r.data, r.feed, r.kill_check)
    else:
        env = _env(a)
        require_paper(env)
        sdir = _state_dir(a, False)
        kill = _kill_check(a, env, sdir)
        akey, asec = env.first(envfile.ALPACA_KEY_VARS), env.first(envfile.ALPACA_SECRET_VARS)
        brokers = {}
        if "alpaca" in which:
            brokers["alpaca"] = AlpacaPaperBroker(akey, asec, kill)
        if "webull" in which:
            brokers["webull"] = WebullSandboxBroker(env.first(envfile.WEBULL_KEY_VARS), env.first(envfile.WEBULL_SECRET_VARS),
                                                    env.first(envfile.WEBULL_ACCOUNT_VARS), kill, region=env.get("WEBULL_REGION") or "us", token_dir=sdir / "webull-token")
        res = smoke(a, brokers, AlpacaData(akey, asec, feed=env.get("ALPACA_DATA_FEED") or "iex"), _feed(a, C.load(a.config), sdir, "SMOKE TEST · paper"), kill)
    print(json.dumps(res, indent=1, default=str))
    return 0


def main(argv=None):
    a = _args(sys.argv[1:] if argv is None else argv)
    try:
        return {"check": cmd_check, "start": cmd_start, "run": cmd_run, "stop": cmd_stop, "status": cmd_status,
                "kill": lambda a: cmd_kill(a, True), "unkill": lambda a: cmd_kill(a, False), "smoke-test": cmd_smoke}[a.command](a)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    except SafetyError as e:
        print(f"SAFETY: {e}", file=sys.stderr)
        return 2
