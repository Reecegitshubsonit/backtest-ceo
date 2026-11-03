"""Walk-forward fix-up of the options60 study.

Train = the 200 sessions before the original 60-day window; test = the original 60 sessions (untouched while
tuning). Each family's parameters are chosen by train Sharpe only, then run once on test.

    python3 -m backtestceo.options_fix            # needs data/options60 cache (see options60 + fetch long)

Families
  credit:  0DTE iron condor / butterfly / put spread / call spread with entry time, strike offset, wing width,
           stop-loss (x credit) and profit target grids, plus an opening-range volatility filter.
  signal:  the same 0DTE credit spreads but the side picked by an indicator (EMA 9/21, VWAP, RSI14, RSI(2))
           -> "indicator signal expressed as option premium selling".
  shares:  indicator signals on shares, re-tuned (bar size, entry window, trend filter, hold time).
"""
import json, math, sys, itertools
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from datetime import date
from pathlib import Path

from . import options60 as o

TEST_DAYS, TRAIN_DAYS = 60, 200
OUT = o.ROOT / "docs/backtests/options60-fix"
MIN_TRADES = 30


# ------------------------------------------------------------------ data
def load():
    o.WARM_START = date(2025, 9, 1)
    base = o.cached
    o.cached = lambda name, fn: base(name.replace("-5m.json", "-5m-long.json"), fn)
    und = {s: o.underlying(s) for s in o.SYMBOLS}
    o.cached = base
    days = sorted(set.intersection(*(set(d) for d in und.values())))
    days = [d for d in days if date.fromisoformat(d) <= o.END][-(TEST_DAYS + TRAIN_DAYS):]
    return und, days


class Tape:
    """Option 5-min bars of one day: fill = VWAP of first bar at/after t (<=3 bars); mark = last close <= t."""
    HM = [f"{m // 60:02d}:{m % 60:02d}" for m in range(570, 960, 5)]

    def __init__(self, raw):
        self.raw = raw; self._marks = {}

    def fill(self, s, hm, look=3):
        bs = self.raw.get(s)
        if not bs: return None
        i = self.HM.index(hm)
        for h in self.HM[i:i + look]:
            if h in bs: return float(bs[h].get("vw") or bs[h]["c"])
        return None

    def marks(self, s):
        if s not in self._marks:
            bs, last, arr = self.raw.get(s, {}), None, []
            for h in self.HM:
                if h in bs: last = float(bs[h]["c"])
                arr.append(last)
            self._marks[s] = arr
        return self._marks[s]


def day_ctx(und, days):
    """Per (sym, day): bars, tape path, prev close, daily RSI2 / SMA filters."""
    ctx = {}
    for sym in o.SYMBOLS:
        closes = []
        allds = sorted(und[sym])
        for d in allds:
            bs = und[sym][d]
            closes.append(bs[-1]["c"])
        dclose = dict(zip(allds, closes))
        # daily RSI(2) and SMA(5/200-ish -> 50, limited warm-up) on closes up to previous day
        g = l = None; rsi2 = {}; prev = None
        for d in allds:
            c = dclose[d]
            if prev is not None:
                ch = c - prev; up, dn = max(ch, 0), max(-ch, 0)
                g = up if g is None else (g + up) / 2; l = dn if l is None else (l + dn) / 2
            rsi2[d] = None if g is None else (100.0 if l == 0 else 100 - 100 / (1 + g / l)); prev = c
        for k, d in enumerate(allds):
            if d not in days: continue
            p = allds[k - 1]
            hist = closes[max(0, k - 50):k]
            ctx[(sym, d)] = dict(bars=und[sym][d], prev_close=dclose[p], d_rsi2=rsi2[p],
                                 sma50=sum(hist) / len(hist), nxt=allds[k + 1] if k + 1 < len(allds) else None)
    return ctx


# ------------------------------------------------------------------ credit structures
LEGS = {
    "IC":  lambda a, w: [("P", -a - w, 1), ("P", -a, -1), ("C", a, -1), ("C", a + w, 1)],
    "PUT": lambda a, w: [("P", -a, -1), ("P", -a - w, 1)],
    "CALL": lambda a, w: [("C", a, -1), ("C", a + w, 1)],
}


def run_structure(sym, d, bars, tape, kind, a, w, entry, stop, tgt):
    hm = [b["hm"] for b in bars]
    if entry not in hm: return None
    i = hm.index(entry)
    spot = bars[i - 1]["c"]
    e = date.fromisoformat(d)
    legs = []
    for right, off, q in LEGS[kind](a, w):
        k = round(spot * (1 + off)); s = o.occ(sym, e, right, k)
        p = tape.fill(s, entry)
        if p is None: return None
        legs.append((s, right, k, q, p))
    if len({(l[1], l[2]) for l in legs}) < len(legs): return None
    v0 = sum(q * p for _, _, _, q, p in legs)           # negative = credit received
    credit = -v0
    if credit <= 0.02: return None
    cost = sum(o.leg_cost(p, q) for *_, q, p in legs)
    exit_i = None
    if stop or tgt:
        mk = [tape.marks(s) for s, *_ in legs]
        ti = Tape.HM.index(entry)
        for j in range(ti + 1, Tape.HM.index("15:45") + 1):
            vals = [m[j] for m in mk]
            if any(v is None for v in vals): continue
            pnl = (sum(q * v for v, (_, _, _, q, _) in zip(vals, legs)) - v0) * 100
            if (stop and pnl <= -stop * credit * 100) or (tgt and pnl >= tgt * credit * 100):
                exit_i = j + 1; break
    if exit_i is not None:
        h = Tape.HM[exit_i]; gross = xcost = 0.0
        for s_, _, _, q, p in legs:
            x = tape.fill(s_, h, 2)
            if x is None: x = tape.marks(s_)[exit_i - 1]
            gross += q * (x - p) * 100
            if x >= 0.05: xcost += o.leg_cost(x, q)      # sub-nickel legs left to expire
        return gross - cost - xcost, cost + xcost
    settle = bars[-1]["c"]; pnl = 0.0
    for s, r, k, q, p in legs:
        iv = max(0.0, settle - k) if r == "C" else max(0.0, k - settle)
        pnl += q * (iv - p) * 100
    return pnl - cost, cost


# ------------------------------------------------------------------ indicator side pickers
def side_ema(b, c): return 1 if b["e9"] > b["e21"] else -1
def side_vwap(b, c): return 1 if b["c"] > b["vwap"] else -1
def side_trend(b, c):
    if b["c"] > b["vwap"] and b["e9"] > b["e21"]: return 1
    if b["c"] < b["vwap"] and b["e9"] < b["e21"]: return -1
    return 0
def side_rsi14_rev(b, c): return -1 if b["rsi14"] > 60 else 1 if b["rsi14"] < 40 else 0
def side_rsi14_mom(b, c): return 1 if b["rsi14"] > 55 else -1 if b["rsi14"] < 45 else 0
def side_daily_rsi2(b, c):
    r = c["d_rsi2"]
    return 0 if r is None else 1 if r < 25 else -1 if r > 75 else 0
SIDES = {"EMA9>21": side_ema, "VWAP side": side_vwap, "EMA+VWAP trend": side_trend,
         "RSI14 reversion": side_rsi14_rev, "RSI14 momentum": side_rsi14_mom, "daily RSI(2) reversion": side_daily_rsi2}


# ------------------------------------------------------------------ grid evaluation
ENTRIES = ["10:00", "11:00", "12:30", "14:00", "15:00"]
OFFS = [0.0, 0.0025, 0.005, 0.0075]
WINGS = [0.005, 0.01]
STOPS = [None, 1.0, 2.0]
TGTS = [None, 0.5]
ORF = [None, 0.006, 0.010]          # skip day if (high-low) of session so far / open > x


def configs():
    for kind in ("IC", "PUT", "CALL"):
        for c in itertools.product(OFFS, WINGS, ENTRIES, STOPS, TGTS, ORF):
            yield ("credit", kind, None) + c
    for side in SIDES:
        for c in itertools.product(OFFS, WINGS, ENTRIES, STOPS, TGTS, ORF):
            yield ("signal", "DIR", side) + c


def eval_config(cfg, ctx, days, tapes):
    fam, kind, side, a, w, entry, stop, tgt, orf = cfg
    trades = []
    for (sym, d), c in ctx.items():
        if d not in days: continue
        bars = c["bars"]; hm = [b["hm"] for b in bars]
        if entry not in hm: continue
        i = hm.index(entry); pre = bars[:i]
        if orf:
            rng = (max(b["h"] for b in pre) - min(b["l"] for b in pre)) / bars[0]["o"]
            if rng > orf: continue
        k = kind
        if fam == "signal":
            s = SIDES[side](bars[i - 1], c)
            if s == 0: continue
            k = "PUT" if s == 1 else "CALL"
        r = run_structure(sym, d, bars, tapes[(sym, d)], k, a, w, entry, stop, tgt)
        if r: trades.append(dict(day=d, sym=sym, pnl=r[0], cost=r[1]))
    return trades


_G = {}
def _init(ctx, days):
    _G["ctx"] = ctx; _G["days"] = set(days)
    _G["tapes"] = {k: Tape(json.loads((o.CACHE / f"opt/{k[0]}-{k[1]}.json").read_text())) for k in ctx}


def _work(cfgs):
    out = []
    for cfg in cfgs:
        t = eval_config(cfg, _G["ctx"], _G["days"], _G["tapes"])
        out.append((cfg, t))
    return out


def fmt(cfg):
    fam, kind, side, a, w, entry, stop, tgt, orf = cfg
    k = side + " -> put/call spread" if fam == "signal" else {"IC": "iron fly" if a == 0 else "iron condor",
                                                               "PUT": "bull put spread", "CALL": "bear call spread"}[kind]
    return (f"{k}; short {a*100:.2f}% OTM, wing {w*100:.1f}%, enter {entry}, stop "
            f"{'none' if not stop else f'{stop:g}x credit'}, target {'none' if not tgt else f'{int(tgt*100)}%'}, "
            f"range filter {'none' if not orf else f'<{orf*100:.1f}%'}")


def main():
    und, days = load()
    train, test = days[:TRAIN_DAYS], days[TRAIN_DAYS:]
    ctx = day_ctx(und, days)
    ctx = {k: v for k, v in ctx.items() if (o.CACHE / f"opt/{k[0]}-{k[1]}.json").exists() and len(v["bars"]) >= 70}
    cfgs = list(configs())
    print(f"{len(cfgs)} configs, train {train[0]}..{train[-1]}, test {test[0]}..{test[-1]}", flush=True)
    chunks = [cfgs[i::16] for i in range(16)]
    with ProcessPoolExecutor(4, initializer=_init, initargs=(ctx, train)) as ex:
        res = [r for part in ex.map(_work, chunks) for r in part]
    scored = []
    for cfg, t in res:
        m = o.metrics(t, train)
        if m["trades"] >= MIN_TRADES: scored.append((m["sharpe"], cfg, m))
    scored.sort(key=lambda x: -x[0])
    # pick best per family/kind/side, then evaluate once on test
    best = {}
    for sh, cfg, m in scored:
        key = (cfg[0], cfg[1] if cfg[0] == "credit" else cfg[2], "fly" if cfg[1] == "IC" and cfg[3] == 0 else "")
        best.setdefault(key, (cfg, m))
    _init(ctx, test)
    rows = []
    for key, (cfg, mtr) in best.items():
        tt = eval_config(cfg, _G["ctx"], _G["days"], _G["tapes"])
        mte = o.metrics(tt, test)
        rows.append(dict(config=fmt(cfg), cfg=cfg, train=mtr, test=mte, test_trades=tt))
    rows.sort(key=lambda r: -(r["test"].get("sharpe") or -99))
    top = []
    for sh, cfg, m in scored[:50]:
        mt = o.metrics(eval_config(cfg, _G["ctx"], _G["days"], _G["tapes"]), test)
        top.append(dict(config=fmt(cfg), train_sharpe=sh, test=mt))
    shares_rows = shares_study(und, ctx, train, test)
    report(rows, shares_rows, len(cfgs), train, test, scored, top)


# ------------------------------------------------------------------ shares re-tune
def agg(bars, n):
    out = []
    for i in range(0, len(bars) - n + 1, n):
        g = bars[i:i + n]; last = g[-1]
        out.append(dict(last, o=g[0]["o"], h=max(b["h"] for b in g), l=min(b["l"] for b in g)))
    return out


def shares_study(und, ctx, train, test):
    """Same signals on shares: bar size x entry window x daily trend filter; pick on train, test once."""
    grid = list(itertools.product(o.INDICATOR.items(), [1, 3, 6], [("09:45", "15:30"), ("10:30", "15:00")],
                                  [False, True]))
    def run(spec, ds):
        (name, fn), n, (t0, t1), trend = spec; trades = []
        for (sym, d), c in ctx.items():
            if d not in ds: continue
            bars = agg(c["bars"], n)
            for side, i, j in o.signal_trades(bars, fn):
                if not (t0 <= bars[i]["hm"] < t1): continue
                if trend and (side == 1) != (c["prev_close"] > c["sma50"]): continue
                if j + 1 >= len(bars): continue
                eb, xb = bars[i + 1], bars[j + 1]
                ep, xp = eb["o"], xb["o"]
                cost = o.SHARE_SLIP * (ep + xp) * o.SHARE_QTY
                trades.append(dict(day=d, sym=sym, pnl=side * (xp - ep) * o.SHARE_QTY - cost, cost=cost))
        return trades
    best = {}
    for spec in grid:
        m = o.metrics(run(spec, set(train)), train)
        if m["trades"] >= MIN_TRADES and (spec[0][0] not in best or m["sharpe"] > best[spec[0][0]][1]["sharpe"]):
            best[spec[0][0]] = (spec, m)
    rows = []
    for name, (spec, mtr) in best.items():
        mte = o.metrics(run(spec, set(test)), test)
        rows.append(dict(config=f"{name} on shares; {spec[1]*5}-min bars, entries {spec[2][0]}-{spec[2][1]}, "
                                f"daily-trend filter {'on' if spec[3] else 'off'}", train=mtr, test=mte))
    return rows


def report(rows, shares_rows, n_cfg, train, test, scored, top):
    OUT.mkdir(parents=True, exist_ok=True)
    def line(r):
        a, b = r["train"], r["test"]
        if not b.get("trades"): return f"| {r['config']} | {a['trades']} | {a['sharpe']:.2f} | 0 | | | | | | REJECTED |"
        ok = "PASS" if b["trades"] >= MIN_TRADES and b["exp"] > 0 and b["sharpe"] > 1 else \
             ("REJECTED (<30)" if b["trades"] < MIN_TRADES else "FAIL")
        return (f"| {r['config']} | {a['trades']} | {a['sharpe']:.2f} | {b['trades']} | {b['win']*100:.1f} | "
                f"{b['exp']:.2f} | {b['total']:.0f} | {b['mdd']:.0f} | {b['sharpe']:.2f} | {ok} |")
    H = ["| Config (chosen on train) | Train trades | Train Sharpe | Test trades | Test win % | Test exp $ | "
         "Test total $ | Test max DD $ | Test Sharpe | Verdict |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|---|"]
    L = [f"# Options strategy fix-up: walk-forward", "",
         f"Train {train[0]}..{train[-1]} ({len(train)} sessions), test {test[0]}..{test[-1]} ({len(test)} sessions, "
         f"the original window, untouched while tuning). SPY + QQQ. {n_cfg} option configs searched; best per "
         f"family by train Sharpe (>= {MIN_TRADES} train trades), then run once on test. PASS = test >= "
         f"{MIN_TRADES} trades, expectancy > 0, Sharpe > 1.", "", "## Options (0DTE premium selling, plain and indicator-sided)", ""] + H
    L += [line(r) for r in rows]
    L += ["", "## Indicator signals on shares (re-tuned)", ""] + H + [line(r) for r in shares_rows]
    ts = sorted(t["test"].get("sharpe", 0) for t in top)
    L += ["", "## Robustness: top 50 train configs (all families) on test", "",
          f"{sum(t['test'].get('exp', 0) > 0 for t in top)}/50 profitable on test; median test Sharpe "
          f"{ts[len(ts)//2]:.2f}; worst {ts[0]:.2f}; best {ts[-1]:.2f}.", "",
          "| Train rank | Config | Train Sharpe | Test trades | Test exp $ | Test Sharpe |", "|---:|---|---:|---:|---:|---:|"]
    L += [f"| {i+1} | {t['config']} | {t['train_sharpe']:.2f} | {t['test'].get('trades',0)} | "
          f"{t['test'].get('exp',0):.2f} | {t['test'].get('sharpe',0):.2f} |" for i, t in enumerate(top[:20])]
    (OUT / "README.md").write_text("\n".join(L) + "\n")
    (OUT / "results.json").write_text(json.dumps(
        [dict(config=r["config"], train=r["train"], test=r["test"]) for r in rows + shares_rows], indent=1))
    (OUT / "train_ranking.json").write_text(json.dumps(
        [dict(config=fmt(c), sharpe=s, trades=m["trades"], exp=m["exp"]) for s, c, m in scored[:200]], indent=1))
    print("\n".join(L))


if __name__ == "__main__":
    main()
