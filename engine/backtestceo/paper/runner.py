"""The paper-trading runner: polls bars, applies the ported rules, sends every signal through the agent pipeline,
places approved orders on paper/sandbox brokers and streams everything to the live-events feed."""
import json
import math
import time as _time
from datetime import datetime, time, timedelta, timezone
from pathlib import Path

from . import strategies as S
from .feed import now_iso
from .pipeline import Pipeline
from .reference import FAMILIES, Reference, family_of
from .safety import KillSwitchEngaged

ET = S.ET


def _floor9(x):
    return math.floor(x * 1e9 + 1e-6) / 1e9


def _blank():
    return dict(pos=None, fills=[], closed=[], realized_usd=0.0, mark=None, last_bar=None, entries={}, status="waiting for data",
                stage="backtest", short_skip_bar=None, done_day=None, last_error=None)


class Runner:
    def __init__(self, cfg, data, brokers, feed, kill_check, state_path=None, reference=None, mode="paper", log=print):
        self.cfg, self.data, self.brokers, self.feed, self.kill_check = cfg, data, brokers, feed, kill_check
        self.state_path = Path(state_path) if state_path else None
        self.ref = reference or Reference()
        self.pipeline = Pipeline(feed)
        self.mode, self.log = mode, log
        self.strats = [s for s in cfg.strategies if s.enabled]
        self.st = {s.key: _blank() for s in self.strats}
        self.halted = None
        self.started = now_iso()
        if mode != "dry-run":  # a dry run replays from its own simulated start, so it never resumes old state
            self._load()

    # ---------- persistence ----------
    def _load(self):
        if self.state_path and self.state_path.exists():
            saved = json.loads(self.state_path.read_text()).get("strategies", {})
            for k, v in saved.items():
                if k in self.st:
                    self.st[k].update(v)

    def save(self, now=None):
        if not self.state_path:
            return
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.state_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(dict(mode=self.mode, updated=(now or datetime.now(timezone.utc)).isoformat(), halted=self.halted,
                                       started=self.started, strategies=self.st), default=str, indent=1))
        tmp.replace(self.state_path)

    # ---------- helpers ----------
    @staticmethod
    def _day(now):
        return now.astimezone(ET).date().isoformat()

    def _entries_today(self, key, now):
        return self.st[key]["entries"].get(self._day(now), 0)

    def _entries_total(self, now):
        d = self._day(now)
        return sum(v["entries"].get(d, 0) for v in self.st.values())

    def _ctx(self, s, now, **kw):
        fam = family_of(s.run)
        st = self.st[s.key]
        ctx = dict(id=f"{s.key}-{kw['bar_ts']:%Y%m%dT%H%M}-{kw['intent']}", name=fam["name"], key=s.key, run=s.run, symbol=s.symbol,
                   broker=s.broker, long_only=s.broker == "alpaca", open_positions=1 if st["pos"] else 0,
                   entries_today=self._entries_today(s.key, now), entries_today_total=self._entries_total(now), caps=self.cfg.caps,
                   kill=self.kill_check(), reference=self.ref.run_stats(s.run), require_positive_reference=False)
        ctx.update(kw)
        ctx["bar_ts"] = ctx["bar_ts"].isoformat()
        return ctx

    def _emit_status(self, s, msg, level="info", slot="scanner"):
        self.feed.emit(dict(kind="agent_activity", slot=slot, task=f"RULE-BASED · {s.key}: {msg}"[:200], state="error" if level == "error" else "working",
                            strategy=family_of(s.run)["name"], symbol=s.symbol, log=msg[:300], level=level))

    # ---------- orders ----------
    def _execute(self, s, now, side, reason, qty=None, notional=None, stop=None, bar_ts=None):
        st = self.st[s.key]
        broker = self.brokers[s.broker]
        crypto = "/" in s.symbol
        try:
            held_before = broker.position_qty(s.symbol) if crypto else None
            if crypto and side == "sell" and held_before is not None:
                qty = _floor9(min(qty, held_before))  # fees taken on the buy leave less than the filled qty
                if qty <= 0:
                    raise RuntimeError(f"no {s.symbol} left at the broker to sell")
            o = broker.submit(s.symbol, side, qty=qty, notional=notional)
            if o["status"] not in ("filled", "rejected", "canceled", "failed"):
                o = broker.wait_fill(o["client_order_id"])
        except KillSwitchEngaged as e:
            self._halt(str(e))
            return None
        except Exception as e:
            st["last_error"] = f"{e.__class__.__name__}: {str(e)[:160]}"
            st["status"] = "order error"
            self._emit_status(s, f"order error: {st['last_error']}", "error", slot="risk")
            return None
        if o["status"] != "filled" or not o.get("filled_price"):
            st["status"] = f"order {o['status']}"
            self._emit_status(s, f"order {o['client_order_id']} {o['status']}", "warn", slot="risk")
            return None
        px, q = float(o["filled_price"]), float(o["filled_qty"])
        if crypto and side == "buy" and held_before is not None:
            try:  # record the post-fee quantity actually added to the position, not the gross filled qty
                added = broker.position_qty(s.symbol) - held_before
                if 0 < added <= q + 1e-12:
                    q = _floor9(added)
            except Exception:
                pass
        fill = dict(time=now.isoformat(), side=side, qty=q, price=px, client_order_id=o["client_order_id"], reason=reason, broker=s.broker)
        st["fills"] = (st["fills"] + [fill])[-20:]
        if side in ("buy", "short"):
            d = 1 if side == "buy" else -1
            st["pos"] = dict(side="long" if d > 0 else "short", dir=d, qty=q, entry=px, opened_at=now.isoformat(),
                             entry_bar_ts=bar_ts.isoformat() if bar_ts else now.isoformat(),
                             stop=stop if stop is not None else None)
            day = self._day(now)
            st["entries"] = {day: st["entries"].get(day, 0) + 1}
            st["status"] = f"in position ({st['pos']['side']})"
        else:
            p = st["pos"]
            pnl = (px - p["entry"]) * p["qty"] * p["dir"]
            st["realized_usd"] = round(st["realized_usd"] + pnl, 2)
            st["closed"] = (st["closed"] + [dict(entry_time=p["opened_at"], exit_time=now.isoformat(), side=p["side"], entry=p["entry"], exit=px,
                                                  ret=(px / p["entry"] - 1) * p["dir"], pnl_usd=round(pnl, 2), reason=reason)])[-20:]
            st["pos"] = None
            st["status"] = "flat"
        self.feed.emit(dict(kind="agent_activity", slot="risk", task=f"RULE-BASED · fill {s.key}", state="working", strategy=family_of(s.run)["name"],
                            symbol=s.symbol, log=f"{'PAPER' if self.mode == 'paper' else 'DRY RUN'} fill {side} {q:g} {s.symbol} @ {px:.2f} ({s.broker})"))
        return fill

    def _halt(self, why):
        if not self.halted:
            self.halted = why
            for s in self.strats:
                self.st[s.key]["status"] = "halted · kill switch"
            self.feed.emit(dict(kind="agent_activity", slot="risk", task="RULE-BASED · KILL SWITCH: trading halted", state="error", log=why[:300], level="error"))

    # ---------- bar strategies (run_bars semantics) ----------
    def _bar_strategy(self, s, now):
        st, tf = self.st[s.key], timedelta(hours=s.tf_hours)
        if st["last_bar"]:
            due = datetime.fromisoformat(st["last_bar"]) + 2 * tf
            if now < due:
                return
        bars = self.data.bars(s.symbol, 60, now, timedelta(hours=self.cfg.lookback_hours))
        if s.tf_hours > 1:
            bars = [b for b in S.resample(bars, s.tf_hours) if b["ts"] + tf <= now]
        if len(bars) < 50:
            st["status"] = "waiting for data"
            return
        last = bars[-1]
        st["mark"] = last["c"]
        if st["last_bar"] == last["ts"].isoformat():
            return
        st["last_bar"] = last["ts"].isoformat()
        st["status"] = "flat" if not st["pos"] else f"in position ({st['pos']['side']})"
        sig, i = S.SIGNALS[s.rule](bars), len(bars) - 1
        age = (now - (last["ts"] + tf)).total_seconds()
        base = dict(bar_ts=last["ts"], bars=bars, price=last["c"], bar_age_s=age, max_bar_age_s=tf.total_seconds() * 1.5, session_ok=True)
        pos = st["pos"]
        # stop check on the completed bar (run_bars checks the bar's low against entry*(1-stop))
        if pos and sig["stop_pct"] and pos.get("stop") and last["ts"].isoformat() >= pos["entry_bar_ts"][:25] and last["l"] <= pos["stop"]:
            self._exit(s, now, base, f"{sig['stop_pct']:.0%} stop hit (low {last['l']:.2f} <= {pos['stop']:.2f})")
            pos = st["pos"]
        d = pos["dir"] if pos else 0
        close, opn = S.bar_action(d, sig, i)
        if close:
            self._exit(s, now, base, "exit signal (" + ("lx" if d > 0 and sig["lx"][i] else "se" if d > 0 else "sx/le") + ")")
        if (close or not pos) and opn:
            if opn < 0 and s.broker == "alpaca":
                if st["short_skip_bar"] is None:  # report once per run of short signals, not every bar
                    ctx = self._ctx(s, now, intent="entry", side="short", reason="short entry signal (se)", notional=self.cfg.caps.max_notional_usd, **base)
                    st["stage"] = self.pipeline.review(ctx).stage
                st["short_skip_bar"] = st["last_bar"]
                st["status"] = "flat · short signal (Alpaca crypto is long-only)"
                return
            st["short_skip_bar"] = None
            notional = self.cfg.caps.max_notional_usd
            ctx = self._ctx(s, now, intent="entry", side="buy" if opn > 0 else "short", reason="long entry signal (le)" if opn > 0 else "short entry signal (se)",
                            notional=notional, **base)
            rv = self.pipeline.review(ctx)
            st["stage"] = rv.stage
            if rv.approved:
                fill_bar = last["ts"] + tf  # filled during the next bar, as run_bars fills at its open
                f = self._execute(s, now, ctx["side"], ctx["reason"], notional=notional, bar_ts=fill_bar)
                if f and sig["stop_pct"]:
                    st["pos"]["stop"] = round(f["price"] * (1 - sig["stop_pct"]), 2)
        elif not opn:
            st["short_skip_bar"] = None

    def _exit(self, s, now, base, reason):
        st = self.st[s.key]
        p = st["pos"]
        ctx = self._ctx(s, now, intent="exit", side="sell" if p["dir"] > 0 else "cover", reason=reason, qty=p["qty"], **base)
        rv = self.pipeline.review(ctx)
        st["stage"] = rv.stage
        if rv.approved:
            self._execute(s, now, ctx["side"], reason, qty=p["qty"])

    # ---------- first 5-minute candle (s_first5m semantics, QQQ cross-check sizing) ----------
    def _first5m(self, s, now):
        st, et = self.st[s.key], now.astimezone(ET)
        eh, em = map(int, self.cfg.first5m_exit_et.split(":"))
        exit_t = time(eh, em)
        if et.weekday() >= 5:
            st["status"] = "market closed (weekend)" if not st["pos"] else st["status"]
            return
        today = et.date()
        bars = [b for b in self.data.bars(s.symbol, 5, now, timedelta(hours=12)) if b["ts"].astimezone(ET).date() == today]
        rth = [b for b in bars if S.FIRST5M_START <= b["ts"].astimezone(ET).time() <= S.FIRST5M_LAST]
        if rth:
            st["mark"] = rth[-1]["c"]
        p = st["pos"]
        if p:
            base = dict(bar_ts=rth[-1]["ts"] if rth else now, bars=rth, price=st["mark"] or p["entry"], bar_age_s=0, session_ok=True)
            hit = next((b for b in rth if b["ts"].isoformat() >= p["entry_bar_ts"][:25] and S.first5m_stop_hit(p["dir"], p["stop"], b)), None)
            if hit:
                self._exit(s, now, base, f"stop {p['stop']:.2f} hit on the {hit['ts'].astimezone(ET):%H:%M} bar")
            elif et.time() >= exit_t:
                self._exit(s, now, base, f"end of session exit ({self.cfg.first5m_exit_et} ET)")
            return
        if st["done_day"] == today.isoformat():
            return
        if et.time() < time(9, 35):
            st["status"] = "waiting for the 09:30 candle"
            return
        if et.time() > time(9, 45) or et.time() >= exit_t:
            st["done_day"] = today.isoformat()
            st["status"] = "no trade today (" + ("missed the 09:35 entry window" if rth else "no session bars: holiday or data gap") + ")"
            return
        sig = S.first5m_signal(rth)
        if not sig:
            if rth and rth[0]["ts"].astimezone(ET).time() == S.FIRST5M_START:
                st["done_day"], st["status"] = today.isoformat(), "no trade today (doji first candle)"
            return
        q = self.data.quote(s.symbol)
        price = q["ask"] if sig["side"] > 0 else q["bid"]
        st["done_day"] = today.isoformat()
        if not S.first5m_entry_ok(sig["side"], price, sig["stop"]):
            st["status"] = "no trade today (price already beyond the stop)"
            self._emit_status(s, st["status"])
            return
        n = S.first5m_size(price, sig["stop"], risk=self.cfg.first5m_risk_usd)
        n = min(n, int(self.cfg.caps.max_notional_usd // price))
        side = "buy" if sig["side"] > 0 else "short"
        sb = rth[0]
        ctx = self._ctx(s, now, intent="entry", side=side, qty=n, price=price, stop=sig["stop"], bar_ts=sig["signal_ts"], bars=rth,
                        reason=f"first 5-min candle {'bullish' if sig['side'] > 0 else 'bearish'} (O {sb['o']:.2f} C {sb['c']:.2f})",
                        bar_age_s=(now - (sig["signal_ts"] + timedelta(minutes=5))).total_seconds(), max_bar_age_s=15 * 60, session_ok=True)
        rv = self.pipeline.review(ctx)
        st["stage"] = rv.stage
        if rv.approved:
            self._execute(s, now, side, ctx["reason"], qty=n, stop=sig["stop"], bar_ts=sig["signal_ts"] + timedelta(minutes=5))

    # ---------- wall screens ----------
    def publish(self, now):
        label = "PAPER · Alpaca paper + Webull sandbox" if self.mode == "paper" else "DRY RUN · fake brokers, replayed bars"
        by_fam = {}
        for s in self.strats:
            by_fam.setdefault(family_of(s.run)["id"], []).append(s)
        for fam in FAMILIES:
            legs = []
            for s in by_fam.get(fam["id"], []):
                st = self.st[s.key]
                p, mark = st["pos"], st["mark"]
                unreal = round((mark - p["entry"]) * p["qty"] * p["dir"], 2) if p and mark else 0.0
                legs.append(dict(key=s.key, run=s.run, symbol=s.symbol, broker=s.broker, status=st["status"], stage=st["stage"],
                                 position=dict(p, mark=mark, unrealized_usd=unreal) if p else None, fills=st["fills"][-10:],
                                 closed=st["closed"][-10:], realized_usd=st["realized_usd"], unrealized_usd=unreal,
                                 entries_today=self._entries_today(s.key, now), last_error=st["last_error"]))
            run_ids = {s.run for s in by_fam.get(fam["id"], [])}
            not_run = [r for r in fam["runs"] if r not in run_ids]
            realized = round(sum(l["realized_usd"] for l in legs), 2)
            unreal = round(sum(l["unrealized_usd"] for l in legs), 2)
            status = "backtest-only (not run)" if not legs else ("halted · kill switch" if self.halted else
                     "in position" if any(l["position"] for l in legs) else "running · flat")
            ev = dict(kind="strategy_result", **self.ref.family_payload(fam))
            stages = [l["stage"] for l in legs]
            ev["stage"] = max(stages, key=["scanning", "strategist", "backtest", "validation", "risk", "ceo"].index) if stages else "backtest"
            ev["source"] = ("paper-runner · " + label)[:80]
            ev["paper"] = dict(mode=self.mode, label=label, status=status, legs=legs, backtest_only_runs=not_run,
                               pnl=dict(realized_usd=realized, unrealized_usd=unreal, total_usd=round(realized + unreal, 2)),
                               caps=dict(max_open_positions=self.cfg.caps.max_open_positions, max_notional_usd=self.cfg.caps.max_notional_usd,
                                         max_entries_per_day=self.cfg.caps.max_entries_per_day), updated=now.isoformat())
            self.feed.emit(ev)

    # ---------- loop ----------
    def step(self, now):
        if self.kill_check():
            self._halt("PAPER_TRADING_KILL_SWITCH is on (checked in the main loop)")
        if self.halted:
            return False
        for s in self.strats:
            try:
                (self._first5m if s.rule == "first5m" else self._bar_strategy)(s, now)
            except Exception as e:
                self.st[s.key]["last_error"] = f"{e.__class__.__name__}: {str(e)[:160]}"
                self._emit_status(s, f"error: {self.st[s.key]['last_error']}", "error")
            if self.halted:
                break
        return not self.halted

    def run(self, clock, sleep=_time.sleep, max_ticks=None, publish_every=10, should_stop=lambda: False):
        ticks = 0
        self.log(f"paper runner started ({self.mode}); strategies: {', '.join(s.key for s in self.strats)}")
        while not should_stop():
            now = clock()
            if hasattr(self.data, "now"):
                self.data.now = now
            ok = self.step(now)
            if ticks % publish_every == 0 or not ok:
                self.publish(now)
            self.save(now)
            self.feed.flush()
            ticks += 1
            if not ok or (max_ticks and ticks >= max_ticks):
                break
            sleep(self.cfg.poll_seconds)
        self.publish(clock())
        self.save()
        self.feed.flush()
        self.log(f"paper runner stopped after {ticks} ticks" + (f" (halted: {self.halted})" if self.halted else ""))
        return ticks
