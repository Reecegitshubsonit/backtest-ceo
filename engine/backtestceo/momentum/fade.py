"""Gapper Fade: short the biggest small-cap gappers after the first 5 minutes, cover at the close.

The same scanner as the momentum strategy (gap %, relative volume, $2-20; no news, no float), traded on the side
the data favours: in 2026 the stocks that open +30% or more close lower about two times in three.

Rule (fixed before the out-of-sample test, see README):
  scan at 09:35   gap at the 09:30 open >= 30% vs prev close, open $2-20, RVOL >= 2 by 09:34
  rank            biggest gap first, at most `max_positions` per day
  entry           short at the 09:35 open, equal dollars per position
  stop            buy-stop 50% above entry (disaster stop for squeezes)
  exit            cover at 15:55

    python -m backtestceo.momentum.fade backtest --end 2026-11-03 [--set key=value ...]
    python -m backtestceo.momentum.fade paper [--live]     # Alpaca PAPER; dry run by default
"""
import argparse
import json
import os
import statistics as st
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, fields, replace
from datetime import date, datetime, timedelta
from pathlib import Path

from .data import ET, Data


@dataclass(frozen=True)
class FadeConfig:
    min_gap_pct: float = 30.0
    min_price: float = 2.0
    max_price: float = 20.0
    min_rvol: float = 2.0
    entry_at: str = "09:35"
    stop_pct: float = 50.0
    cover_at: str = "15:55"
    notional: float = 1_000.0          # dollars short per position
    max_positions: int = 5
    max_volume_frac: float = 0.05      # shares <= 5% of the 09:30-09:34 volume
    slippage_pct: float = 0.2          # per side
    adv_days: int = 20

    def with_(self, **kw):
        return replace(self, **kw)


def _min(s: str) -> int:
    h, m = map(int, s.split(":"))
    return h * 60 + m


def _slip(px, cfg):
    return max(0.01, px * cfg.slippage_pct / 100)


# ------------------------------------------------------------------ backtest
def candidates(sd, cfg: FadeConfig):
    """Return (gap, k) if the symbol-day qualifies at entry time, else None. sd is a gappers.SymDay."""
    gap = (sd.open / sd.pc - 1) * 100
    if gap < cfg.min_gap_pct or not (cfg.min_price <= sd.open <= cfg.max_price):
        return None
    at = _min(cfg.entry_at)
    k = next((x for x in range(sd.i930, len(sd.m)) if sd.m[x] >= at), None)
    if k is None or k == sd.i930 or sd.m[k] > at + 5 or sd.rvol(k - 1) < cfg.min_rvol:
        return None
    return gap, k


def trade(sd, k, cfg: FadeConfig):
    fill = sd.o[k] - _slip(sd.o[k], cfg)
    stop = round(fill * (1 + cfg.stop_pct / 100), 2)
    early_vol = sum(sd.v[sd.i930:k])
    q = int(min(cfg.notional / fill, early_vol * cfg.max_volume_frac))
    if q < 1:
        return None
    cover = _min(cfg.cover_at)
    for j in range(k, len(sd.m)):
        if sd.h[j] >= stop:
            px = stop if j == k else max(sd.o[j], stop)
            px += _slip(px, cfg)
            why = "stop"
            break
        if sd.m[j] >= cover:
            px, why = sd.c[j] + _slip(sd.c[j], cfg), "cover"
            break
    else:
        j = len(sd.m) - 1
        px, why = sd.c[j] + _slip(sd.c[j], cfg), "last"
    return {"date": str(sd.d), "symbol": sd.sym, "gap_pct": round((sd.open / sd.pc - 1) * 100, 1),
            "rvol": round(sd.rvol(k - 1), 1), "entry": round(fill, 4), "stop": stop, "exit": round(px, 4),
            "exit_time": f"{sd.m[j] // 60:02d}:{sd.m[j] % 60:02d}", "why": why, "shares": q,
            "pnl": round((fill - px) * q, 2), "ret_pct": round((fill - px) / fill * 100, 2)}


def backtest(days, symdays, cfg: FadeConfig):
    by_day = defaultdict(list)
    for sd in symdays:
        c = candidates(sd, cfg)
        if c:
            by_day[sd.d].append((c[0], c[1], sd))
    trades = []
    for d in sorted(by_day):
        for gap, k, sd in sorted(by_day[d], key=lambda x: -x[0])[:cfg.max_positions]:
            t = trade(sd, k, cfg)
            if t:
                trades.append(t)
    return trades


def stats(trades, days, cfg: FadeConfig):
    pnl = [t["pnl"] for t in trades]
    byd = defaultdict(float)
    for t in trades:
        byd[t["date"]] += t["pnl"]
    daily = [byd.get(str(d), 0.0) for d in days]
    eq = peak = dd = 0.0
    for x in daily:
        eq += x; peak = max(peak, eq); dd = min(dd, eq - peak)
    w, lo = sum(x for x in pnl if x > 0), -sum(x for x in pnl if x < 0)
    sd_ = st.pstdev(daily) if len(daily) > 1 else 0
    mid = str(days[len(days) // 2 - 1])
    return {"sessions": len(days), "first": str(days[0]), "last": str(days[-1]), "trades": len(trades),
            "days_traded": len(byd), "green_days": sum(v > 0 for v in byd.values()), "net_pnl": round(sum(pnl), 2),
            "avg_ret_pct": round(st.mean(t["ret_pct"] for t in trades), 2) if trades else 0,
            "median_ret_pct": round(st.median(t["ret_pct"] for t in trades), 2) if trades else 0,
            "win_rate": round(sum(x > 0 for x in pnl) / len(pnl), 3) if pnl else 0,
            "profit_factor": round(w / lo, 2) if lo else None, "stops_hit": sum(t["why"] == "stop" for t in trades),
            "worst_trade": min(pnl) if pnl else 0, "best_trade": max(pnl) if pnl else 0,
            "worst_day": round(min(daily), 2), "max_drawdown": round(dd, 2),
            "daily_sharpe_annualized": round(st.mean(daily) / sd_ * 252 ** 0.5, 2) if sd_ else None,
            "first_half_pnl": round(sum(t["pnl"] for t in trades if t["date"] <= mid), 2),
            "second_half_pnl": round(sum(t["pnl"] for t in trades if t["date"] > mid), 2),
            "max_gross_short": cfg.notional * cfg.max_positions}


# ------------------------------------------------------------------ paper trading
class FadeTrader:
    """One session: at entry time short the qualifying gappers, keep a buy-stop on each, cover at cover time."""

    def __init__(self, cfg: FadeConfig, data: Data, broker, shortable, now=lambda: datetime.now(ET), log=print):
        self.cfg, self.data, self.broker, self.shortable, self.now, self.log = cfg, data, broker, shortable, now, log
        self.positions = {}  # sym -> {qty, entry, stop_id}
        self.entered = self.covered = False

    def scan(self):
        """Gainers + most-actives -> snapshot -> gap at the 09:30 open, price band, RVOL vs 20-day ADV."""
        c = self.cfg
        syms = sorted(set(self.data.movers(50)) | set(self.data.most_actives(100)))
        snaps = self.data.snapshots(syms) if syms else {}
        rows = []
        for s, sn in snaps.items():
            sn = sn or {}
            day, prevd = sn.get("dailyBar") or {}, sn.get("prevDailyBar") or {}
            o, pc, v = day.get("o"), prevd.get("c"), day.get("v") or 0
            if not (o and pc) or not (c.min_price <= o <= c.max_price) or (o / pc - 1) * 100 < c.min_gap_pct:
                continue
            rows.append((s, (o / pc - 1) * 100, o, v))
        if not rows:
            return []
        today = self.now().date()
        daily = self.data.daily([r[0] for r in rows], today - timedelta(days=45), today - timedelta(days=1), "split")
        out = []
        for s, gap, o, v in rows:
            hist = daily.get(s, [])[-c.adv_days:]
            if len(hist) < 10:
                continue
            adv = sum(b["v"] for b in hist) / len(hist)
            mins = self.now().hour * 60 + self.now().minute - 570
            rv = v / (adv * min(1.0, max(30, mins) / 390)) if adv else 0
            if rv >= c.min_rvol:
                out.append({"sym": s, "gap": gap, "open": o, "rvol": rv, "early_vol": v})
        return sorted(out, key=lambda r: -r["gap"])

    def enter(self):
        c = self.cfg
        picks = []
        for r in self.scan():
            if len(picks) >= c.max_positions:
                break
            ok, why = self.shortable(r["sym"])
            if not ok:
                self.log(f"skip {r['sym']} gap {r['gap']:.1f}%: {why}")
                continue
            picks.append(r)
        for r in picks:
            last = latest_trade(self.data, r["sym"]) or r["open"]
            if hasattr(self.broker, "tick"):
                self.broker.tick(r["sym"], last)  # dry run: price the market order
            q = int(min(c.notional / last, r["early_vol"] * c.max_volume_frac))
            if q < 1:
                continue
            o = self.broker.submit(symbol=r["sym"], qty=str(q), side="sell", type="market", time_in_force="day")
            filled = self.wait_fill(o["id"])
            if not filled:
                self.log(f"{r['sym']}: short not filled")
                continue
            qty, px = filled
            stop = round(px * (1 + c.stop_pct / 100), 2)
            so = self.broker.submit(symbol=r["sym"], qty=str(qty), side="buy", type="stop", time_in_force="day",
                                    stop_price=f"{stop:.2f}")
            self.positions[r["sym"]] = {"qty": qty, "entry": px, "stop": stop, "stop_id": so["id"]}
            self.log(f"SHORT {qty} {r['sym']} @ {px:.4f} (gap {r['gap']:.1f}%, rvol {r['rvol']:.1f}) stop {stop}")
        self.entered = True

    def wait_fill(self, oid, tries=30):
        for _ in range(tries):
            o = self.broker.order(oid)
            if o.get("status") == "filled":
                return int(float(o["filled_qty"])), float(o["filled_avg_price"])
            if o.get("status") in ("canceled", "rejected", "expired"):
                return None
            time.sleep(1)
        self.broker.cancel(oid)
        o = self.broker.order(oid)
        q = int(float(o.get("filled_qty") or 0))
        return (q, float(o["filled_avg_price"])) if q else None

    def cover_all(self):
        for s, p in list(self.positions.items()):
            so = self.broker.order(p["stop_id"])
            if so.get("status") == "filled":
                self.log(f"{s}: stopped out @ {so.get('filled_avg_price')}")
            else:
                self.broker.cancel(p["stop_id"])
                o = self.broker.submit(symbol=s, qty=str(p["qty"]), side="buy", type="market", time_in_force="day")
                f = self.wait_fill(o["id"])
                self.log(f"COVER {p['qty']} {s} @ {f[1] if f else '?'}  pnl {((p['entry'] - f[1]) * p['qty']) if f else 0:.2f}")
            del self.positions[s]
        self.covered = True

    def step(self):
        m = self.now().hour * 60 + self.now().minute
        if not self.entered and m >= _min(self.cfg.entry_at):
            if m <= _min(self.cfg.entry_at) + 5:
                self.enter()
            else:
                self.log("past the entry window: no entries today")
                self.entered = True
        if self.entered and not self.covered and m >= _min(self.cfg.cover_at):
            self.cover_all()


def latest_trade(data, sym):
    try:
        return data.get("/v2/stocks/trades/latest", {"symbols": sym, "feed": data.feed})["trades"][sym]["p"]
    except Exception:
        return None


def paper_main(a, cfg: FadeConfig):
    from ..paper import envfile, safety
    from .paper import REPO, AlpacaPaper, DryRun, log
    env = envfile.load(REPO / ".env", os.environ)
    data = Data(feed=env.get("ALPACA_DATA_FEED") or "iex")
    if a.live:
        if (env.get("ALPACA_PAPER_TRADING_ONLY") or "").lower() != "true":
            raise safety.SafetyError("--live needs ALPACA_PAPER_TRADING_ONLY=true")
        bad = [k for k in safety.ALPACA_URL_VARS if env.get(k) and safety.host_of(env[k]) != "paper-api.alpaca.markets"]
        if bad:
            raise safety.SafetyError("Alpaca base URL is not the paper endpoint: " + ",".join(bad))
        broker = AlpacaPaper(env)

        def shortable(sym):
            try:
                asset = broker.req("GET", f"/v2/assets/{sym}")
            except RuntimeError as e:
                return False, f"asset lookup failed ({e})"
            if not asset.get("shortable"):
                return False, "not shortable"
            if not asset.get("easy_to_borrow"):
                return False, "hard to borrow"
            return True, ""
    else:
        broker = DryRun()

        def shortable(sym):
            return True, "dry run: borrow not checked"
    log(f"fade start {broker!r} notional ${cfg.notional} x {cfg.max_positions}, stop +{cfg.stop_pct}%")
    tr = FadeTrader(cfg, data, broker, shortable, log=log)
    while not tr.covered:
        try:
            tr.step()
        except safety.SafetyError:
            raise
        except Exception as e:
            log(f"fade error: {e.__class__.__name__}: {e}")
        if a.once:
            break
        for s in tr.positions:
            if isinstance(broker, DryRun):
                px = latest_trade(data, s)
                if px:
                    broker.tick(s, px)
        time.sleep(5)
    return 0


# ------------------------------------------------------------------ cli
def parse_set(pairs):
    types = {f.name: f.type for f in fields(FadeConfig)}
    out = {}
    for p in pairs:
        k, v = p.split("=", 1)
        if k not in types:
            raise SystemExit(f"unknown field {k}")
        t = types[k]
        out[k] = int(v) if t in ("int", int) else float(v) if t in ("float", float) else v
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m backtestceo.momentum.fade")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("backtest")
    b.add_argument("--end", default="2026-11-03")
    b.add_argument("--days", type=int, default=60)
    b.add_argument("--set", nargs="*", default=[])
    b.add_argument("--out", default=None)
    p = sub.add_parser("paper")
    p.add_argument("--live", action="store_true")
    p.add_argument("--once", action="store_true")
    p.add_argument("--set", nargs="*", default=[])
    a = ap.parse_args(argv)
    cfg = FadeConfig().with_(**parse_set(a.set))
    if a.cmd == "paper":
        return paper_main(a, cfg)
    from .gappers import prepare
    days, symdays = prepare(date.fromisoformat(a.end), a.days)
    trades = backtest(days, symdays, cfg)
    s = stats(trades, days, cfg)
    print(json.dumps(s, indent=1))
    if a.out:
        Path(a.out).mkdir(parents=True, exist_ok=True)
        (Path(a.out) / f"fade_{s['first']}_{s['last']}.json").write_text(
            json.dumps({"config": cfg.__dict__, "stats": s, "trades": trades}, indent=1))


if __name__ == "__main__":
    from backtestceo.momentum.fade import main as _main
    _main()
