"""No-news momentum on gappers: gap % + relative volume + indicators, long only, full-day 1-min bars.

Entry families (one trade per symbol-day):
  orb  opening-range breakout: first N minutes from 09:30, buy stop at the range high (+1c)
  pmh  premarket-high breakout: buy stop at the 04:00-09:29 high
  hod  high-of-day breakout in an uptrend (close > VWAP, EMA9 > EMA20 on 1-min), from 09:45
Stops: range low, VWAP, a fraction of the 14-day ATR, or the low of the last 5 bars.
Exits: hold to 15:55, trail on 5-min close < 5-min EMA9, 1-min close < VWAP, or a fixed R target.

    python -m backtestceo.momentum.gappers prepare --end 2026-11-03     # download (cached)
    python -m backtestceo.momentum.gappers search  --end 2026-11-03     # grid on that period
"""
import argparse
import hashlib
import itertools
import json
import pickle
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from .backtest import sessions, tradable_symbol
from .data import CACHE, ET, Data, parse_t

SLIP = 0.2  # % per side, min 1c


def slip(px: float, pct: float = SLIP) -> float:
    return max(0.01, px * pct / 100)


# ------------------------------------------------------------------ universe + data
def gap_universe(data: Data, days, prev, min_gap=5.0, min_price=2.0, max_price=20.0, min_adv=100_000, adv_days=20, log=print):
    """Every symbol seen in the news feed over the period (a proxy for the listed universe; news is NOT required
    on the day). A symbol-day is downloaded when its open is in the price band and its high reaches +min_gap% —
    a necessary condition for any entry that requires price >= prev close +min_gap%."""
    syms = set()
    for d in days:
        try:
            news = data.news_for_day(d, prev[d], "11:30")
        except RuntimeError as e:  # news only seeds the symbol list; the other days cover it
            log(f"{d}: news unavailable ({e}); skipped for the symbol list")
            news = []
        for n in news:
            syms |= {s for s in n["symbols"] if tradable_symbol(s)}
    syms = sorted(syms)
    start, end = days[0] - timedelta(days=int(adv_days * 1.6) + 10), days[-1]
    tag = f"news{len(syms)}_" + hashlib.sha1(",".join(syms).encode()).hexdigest()[:10]
    raw = data.daily_cached(syms, start, end, "raw", tag)
    adj = data.daily_cached(syms, start, end, "split", tag)
    out = {d: [] for d in days}
    for s in syms:
        r = {parse_t(b["t"]).astimezone(ET).date(): b for b in raw.get(s, [])}
        a = [(parse_t(b["t"]).astimezone(ET).date(), b) for b in adj.get(s, [])]
        idx = {dd: k for k, (dd, _) in enumerate(a)}
        for d in days:
            if d not in r or d not in idx:
                continue
            k = idx[d]
            hist = a[max(0, k - adv_days):k]
            if len(hist) < 10 or hist[-1][0] != prev[d] or not a[k][1]["c"]:
                continue
            f = r[d]["c"] / a[k][1]["c"]
            pc = hist[-1][1]["c"] * f
            adv = sum(b["v"] for _, b in hist) / len(hist) / f
            rd = r[d]
            if adv < min_adv or not (min_price <= rd["o"] <= max_price) or rd["h"] < pc * (1 + min_gap / 100):
                continue
            trs, prev_c = [], None
            for _, b in hist[-15:]:
                if prev_c is not None:
                    trs.append(max(b["h"] - b["l"], abs(b["h"] - prev_c), abs(b["l"] - prev_c)))
                prev_c = b["c"]
            atr = sum(trs) / len(trs) * f if trs else 0.0
            out[d].append({"sym": s, "pc": pc, "adv": adv, "atr": atr})
    log(f"gap universe: {len(syms)} symbols, {sum(len(v) for v in out.values())} symbol-days")
    return out


def prepare(end: date, n_days: int = 60, log=print):
    p = CACHE / f"gappers_{end}_{n_days}.pkl"
    if p.exists():
        class _U(pickle.Unpickler):
            def find_class(self, module, name):
                return globals()[name] if module == "__main__" else super().find_class(module, name)
        with open(p, "rb") as f:
            return _U(f).load()
    data = Data()
    days, prev = sessions(data, n_days, end)
    uni = gap_universe(data, days, prev, log=log)
    symdays = []
    for d in days:
        syms = [u["sym"] for u in uni[d]]
        bars = data.minute(syms, d, "04:00", "16:00") if syms else {}
        for u in uni[d]:
            sd = SymDay.build(d, u, bars.get(u["sym"], []))
            if sd:
                symdays.append(sd)
        log(f"{d}: {len(syms)} symbols")
    out = (days, symdays)
    p.write_bytes(pickle.dumps(out))
    return out


# ------------------------------------------------------------------ per symbol-day arrays
@dataclass
class SymDay:
    d: date
    sym: str
    pc: float
    adv: float
    atr: float
    m: list      # minute of day (ET) per bar
    o: list
    h: list
    l: list
    c: list
    v: list
    vwap: list
    cumv: list
    e9: list
    e20: list
    i930: int    # index of the first bar at/after 09:30
    pmh: float   # premarket high (04:00-09:29)
    open: float  # 09:30 open
    tr5: list    # per bar: True if 5-min close < 5-min EMA9 at this bar (bar ends a 5-min bucket)

    @staticmethod
    def build(d, u, rows):
        if not rows:
            return None
        m, o, h, l, c, v = [], [], [], [], [], []
        for r in rows:
            t = parse_t(r["t"]).astimezone(ET)
            m.append(t.hour * 60 + t.minute)
            o.append(r["o"]); h.append(r["h"]); l.append(r["l"]); c.append(r["c"]); v.append(r["v"])
        i930 = next((i for i, x in enumerate(m) if x >= 570), None)
        if i930 is None or m[i930] > 575:
            return None
        vwap, cumv, e9, e20 = [], [], [], []
        pv = cv = 0.0
        a9 = a20 = None
        for i in range(len(m)):
            tp = (h[i] + l[i] + c[i]) / 3
            pv += tp * v[i]; cv += v[i]
            vwap.append(pv / cv if cv else c[i]); cumv.append(cv)
            a9 = c[i] if a9 is None else a9 + 0.2 * (c[i] - a9)
            a20 = c[i] if a20 is None else a20 + (2 / 21) * (c[i] - a20)
            e9.append(a9); e20.append(a20)
        # 5-min close vs 5-min EMA9, flagged on the last 1-min bar of each bucket (09:30-09:34 -> flag at 09:34 bar)
        tr5 = [False] * len(m)
        a5 = None
        for i in range(len(m)):
            last = i == len(m) - 1 or m[i + 1] // 5 != m[i] // 5
            if last:
                a5 = c[i] if a5 is None else a5 + 0.2 * (c[i] - a5)
                tr5[i] = c[i] < a5
        pre = [h[i] for i in range(i930)]
        return SymDay(d, u["sym"], u["pc"], u["adv"], u["atr"], m, o, h, l, c, v, vwap, cumv, e9, e20, i930,
                      max(pre) if pre else 0.0, o[i930], tr5)

    def rvol(self, i):
        mins = self.m[i] + 1 - 570
        return self.cumv[i] / (self.adv * min(1.0, max(30, mins) / 390)) if self.adv else 0.0


# ------------------------------------------------------------------ one trade per symbol-day
def simulate(sd: SymDay, P: dict):
    """Returns (entry_min, exit_min, entry, stop, exit_px, reason) or None."""
    gap_open = (sd.open / sd.pc - 1) * 100
    if gap_open < P["gap"] or not (P["pmin"] <= sd.open <= P["pmax"]):
        return None
    kind, n = P["kind"], len(sd.m)
    i = sd.i930
    level = None
    if kind == "orb":
        end_m = 570 + P["or"]
        j = i
        while j < n and sd.m[j] < end_m:
            j += 1
        if j >= n or j == i:
            return None
        hi, lo = max(sd.h[i:j]), min(sd.l[i:j])
        if P.get("green", True) and sd.c[j - 1] <= sd.open:
            return None
        if sd.rvol(j - 1) < P["rvol"] or (P.get("vwap", True) and sd.c[j - 1] <= sd.vwap[j - 1]):
            return None
        level, rng_low, start = round(hi + 0.01, 2), lo, j
    elif kind == "pmh":
        if sd.pmh <= 0 or sd.open >= sd.pmh:
            return None
        level, rng_low, start = round(sd.pmh + 0.01, 2), None, i
    elif kind == "hod":
        start = i
        while start < n and sd.m[start] < 585:
            start += 1
        rng_low = None
    else:
        raise ValueError(kind)
    until = P["until"]
    hod = max(sd.h[i:start]) if start > i else sd.open
    for k in range(start, n):
        if sd.m[k] > until:
            return None
        if kind == "hod":
            prev = k - 1
            ok = sd.c[prev] > sd.vwap[prev] and sd.e9[prev] > sd.e20[prev] and sd.rvol(prev) >= P["rvol"]
            level = round(hod + 0.01, 2) if ok else None
        elif kind == "pmh":
            prev = max(0, k - 1)
            if sd.rvol(prev) < P["rvol"] or (P.get("vwap", True) and sd.c[prev] <= sd.vwap[prev]):
                hod = max(hod, sd.h[k])
                continue
        trig = level is not None and sd.h[k] >= level
        hod = max(hod, sd.h[k])
        if not trig:
            continue
        if sd.o[k] > level * 1.01:  # gapped through: do not chase
            return None
        fill = max(sd.o[k], level) + slip(level)
        if fill < sd.pc * (1 + P["gap"] / 100) or not (P["pmin"] <= fill <= P["pmax"]):
            return None
        stop = stop_price(sd, P["stop"], k, fill, rng_low)
        if stop is None or stop >= fill or (fill - stop) / fill * 100 > P.get("max_stop", 8.0) or fill - stop < 0.02:
            return None
        return run_exit(sd, P, k, fill, stop)
    return None


def stop_price(sd, mode, k, fill, rng_low):
    if mode == "range":
        return round(rng_low - 0.01, 2) if rng_low is not None else round(min(sd.l[max(0, k - 5):k]) - 0.01, 2)
    if mode == "swing":
        return round(min(sd.l[max(0, k - 5):k]) - 0.01, 2)
    if mode == "vwap":
        return round(sd.vwap[k - 1] - 0.01, 2)
    if mode.startswith("atr"):
        return round(fill - float(mode[3:]) * sd.atr, 2) if sd.atr else None
    raise ValueError(mode)


def run_exit(sd, P, k, fill, stop):
    n, ex = len(sd.m), P["exit"]
    r = fill - stop
    s0 = stop  # initial stop for sizing / R
    tgt = fill + float(ex[3:]) * r if ex.startswith("tgt") else None
    for j in range(k, n):
        if sd.l[j] <= stop:
            px = stop if j == k else min(sd.o[j], stop)
            return sd.m[k], sd.m[j], fill, s0, px - slip(px), "stop"
        if tgt and j > k and sd.h[j] >= tgt + 0.01:
            return sd.m[k], sd.m[j], fill, s0, tgt, "target"
        if sd.m[j] >= 955:
            return sd.m[k], sd.m[j], fill, s0, sd.c[j] - slip(sd.c[j]), "eod"
        if ex == "trail5" and sd.tr5[j] and j > k:
            return sd.m[k], sd.m[j], fill, s0, sd.c[j] - slip(sd.c[j]), "trail5"
        if ex == "vwap" and sd.c[j] < sd.vwap[j]:
            return sd.m[k], sd.m[j], fill, s0, sd.c[j] - slip(sd.c[j]), "vwap"
        if P.get("be") and sd.h[j] >= fill + P["be"] * r:
            stop = max(stop, round(fill, 2))
    j = n - 1
    return sd.m[k], sd.m[j], fill, s0, sd.c[j] - slip(sd.c[j]), "last"


# ------------------------------------------------------------------ short side (fade the gapper)
def _up5(sd):
    """Per bar: True when a 5-min bucket closes above its 5-min EMA9 (cached on the object)."""
    if getattr(sd, "_up5", None) is None:
        f, a5 = [False] * len(sd.m), None
        for i in range(len(sd.m)):
            if i == len(sd.m) - 1 or sd.m[i + 1] // 5 != sd.m[i] // 5:
                a5 = sd.c[i] if a5 is None else a5 + 0.2 * (sd.c[i] - a5)
                f[i] = sd.c[i] > a5
        sd._up5 = f
    return sd._up5


def simulate_short(sd: SymDay, P: dict):
    """Short entries on gappers. Returns (entry_min, exit_min, entry, stop, exit_px, reason) or None."""
    gap_open = (sd.open / sd.pc - 1) * 100
    if gap_open < P["gap"] or not (P["pmin"] <= sd.open <= P["pmax"]):
        return None
    kind, n, i = P["kind"], len(sd.m), sd.i930
    t0 = P.get("at", 575)
    k = i
    while k < n and sd.m[k] < t0:
        k += 1
    if k >= n:
        return None
    rng_hi = max(sd.h[i:k]) if k > i else sd.open
    level = None
    if kind == "s_orbl":
        level = round(min(sd.l[i:k]) - 0.01, 2) if k > i else None
        if level is None or sd.rvol(k - 1) < P["rvol"]:
            return None
    while k < n:
        if sd.m[k] > P["until"]:
            return None
        prev = k - 1
        fill = None
        if kind == "s_open":
            if sd.rvol(prev) < P["rvol"] or (P.get("red", True) and sd.c[prev] >= sd.open):
                return None
            fill = sd.o[k] - slip(sd.o[k])
        elif kind == "s_vwap":
            if sd.c[prev] < sd.vwap[prev] and sd.rvol(prev) >= P["rvol"]:
                fill = sd.o[k] - slip(sd.o[k])
        elif kind == "s_orbl":
            if sd.l[k] <= level:
                if sd.o[k] < level * 0.99:
                    return None  # gapped through: do not chase
                fill = min(sd.o[k], level) - slip(level)
        if fill is not None:
            hod = max(sd.h[i:k])
            st = P["stop"]
            if st == "hod":
                stop = round(hod + 0.01, 2)
            elif st == "range":
                stop = round(rng_hi + 0.01, 2)
            elif st.startswith("atr"):
                stop = round(fill + float(st[3:]) * sd.atr, 2) if sd.atr else None
            elif st.startswith("pct"):
                stop = round(fill * (1 + float(st[3:]) / 100), 2)
            else:
                raise ValueError(st)
            if stop is None or stop <= fill or (stop - fill) / fill * 100 > P.get("max_stop", 15.0) or stop - fill < 0.02:
                return None
            return short_exit(sd, P, k, fill, stop)
        k += 1
    return None


def short_exit(sd, P, k, fill, stop):
    n, ex = len(sd.m), P["exit"]
    r = stop - fill
    tgt = fill - float(ex[3:]) * r if ex.startswith("tgt") else None
    up5 = _up5(sd) if ex == "trail5" else None
    for j in range(k, n):
        if sd.h[j] >= stop:
            px = stop if j == k else max(sd.o[j], stop)
            return sd.m[k], sd.m[j], fill, stop, px + slip(px), "stop"
        if tgt and j > k and sd.l[j] <= tgt - 0.01:
            return sd.m[k], sd.m[j], fill, stop, tgt, "target"
        if sd.m[j] >= 955:
            return sd.m[k], sd.m[j], fill, stop, sd.c[j] + slip(sd.c[j]), "eod"
        if ex == "trail5" and up5[j] and j > k:
            return sd.m[k], sd.m[j], fill, stop, sd.c[j] + slip(sd.c[j]), "trail5"
        if ex == "vwap" and j > k and sd.c[j] > sd.vwap[j]:
            return sd.m[k], sd.m[j], fill, stop, sd.c[j] + slip(sd.c[j]), "vwap"
    j = n - 1
    return sd.m[k], sd.m[j], fill, stop, sd.c[j] + slip(sd.c[j]), "last"


# ------------------------------------------------------------------ portfolio
def portfolio(symdays, P, risk=100.0, max_notional=25_000.0, max_pos=3, daily_max_loss=300.0, liq=0.1):
    """Chronological: up to max_pos open, $risk per trade (capped by notional and 10% of the entry bar's volume),
    no new entries once the day's realized loss reaches daily_max_loss."""
    by_day = defaultdict(list)
    short = P.get("side") == "short"
    for sd in symdays:
        t = simulate_short(sd, P) if short else simulate(sd, P)
        if t:
            k = sd.m.index(t[0])
            by_day[sd.d].append((t, sd, k))
    trades = []
    for d in sorted(by_day):
        cands = sorted(by_day[d], key=lambda x: (x[0][0], -x[1].rvol(max(0, x[2] - 1))))
        open_ = []  # (exit_min, pnl)
        realized = 0.0
        for t, sd, k in cands:
            em, xm, fill, stop, px, why = t
            realized += sum(p for x, p in open_ if x <= em)
            open_ = [(x, p) for x, p in open_ if x > em]
            if len(open_) >= max_pos or realized <= -daily_max_loss:
                continue
            avgv = sum(sd.v[max(0, k - 5):k]) / max(1, len(sd.v[max(0, k - 5):k]))
            q = int(min(risk / abs(fill - stop), max_notional / fill, avgv * liq))
            if q < 1:
                continue
            pnl = (fill - px) * q if short else (px - fill) * q
            open_.append((xm, pnl))
            trades.append({"date": str(d), "sym": sd.sym, "entry_m": em, "exit_m": xm, "entry": round(fill, 4),
                           "stop": stop, "exit": round(px, 4), "why": why, "shares": q, "pnl": round(pnl, 2),
                           "r": round(pnl / (q * abs(fill - stop)), 3), "side": "short" if short else "long", "gap": round((sd.open / sd.pc - 1) * 100, 1)})
    return trades


def summarize(trades, days):
    pnl = [t["pnl"] for t in trades]
    rs = [t["r"] for t in trades]
    w, lo = sum(x for x in pnl if x > 0), -sum(x for x in pnl if x < 0)
    mid = str(days[len(days) // 2 - 1])
    eq = peak = dd = 0.0
    by = defaultdict(float)
    for t in trades:
        by[t["date"]] += t["pnl"]
    for d in days:
        eq += by.get(str(d), 0.0); peak = max(peak, eq); dd = min(dd, eq - peak)
    return {"n": len(trades), "pnl": round(sum(pnl), 2), "pf": round(w / lo, 2) if lo else None,
            "wr": round(sum(x > 0 for x in pnl) / len(pnl), 3) if pnl else 0, "avg_r": round(sum(rs) / len(rs), 3) if rs else 0,
            "h1": round(sum(t["pnl"] for t in trades if t["date"] <= mid), 2),
            "h2": round(sum(t["pnl"] for t in trades if t["date"] > mid), 2), "dd": round(dd, 2)}


BASE = {"kind": "orb", "or": 5, "gap": 10.0, "rvol": 5.0, "pmin": 2.0, "pmax": 20.0, "until": 660, "stop": "range",
        "exit": "eod", "green": True, "vwap": True, "max_stop": 8.0, "be": 0}


def grid():
    out = []
    for kind, orm in (("orb", 5), ("orb", 15), ("orb", 30), ("pmh", 0), ("hod", 0)):
        for gap, rv, stop, ex, until in itertools.product((5.0, 10.0, 20.0), (2.0, 5.0, 10.0),
                                                          ("range", "atr0.1", "atr0.25", "vwap"),
                                                          ("eod", "trail5", "vwap", "tgt2"), (630, 720)):
            if kind != "orb" and stop == "range":
                stop = "swing"
            out.append({**BASE, "kind": kind, "or": orm, "gap": gap, "rvol": rv, "stop": stop, "exit": ex, "until": until})
    for kind, at in (("s_open", 575), ("s_open", 600), ("s_vwap", 575), ("s_vwap", 600), ("s_orbl", 575), ("s_orbl", 600)):
        for gap, rv, stop, ex in itertools.product((10.0, 20.0, 40.0), (2.0, 5.0), ("hod", "atr0.5", "pct5", "pct10"),
                                                   ("eod", "tgt2", "vwap", "trail5")):
            out.append({**BASE, "side": "short", "kind": kind, "at": at, "or": 0, "gap": gap, "rvol": rv, "stop": stop,
                        "exit": ex, "until": 720, "max_stop": 15.0})
    uniq = {json.dumps(p, sort_keys=True): p for p in out}
    return list(uniq.values())


_SD = None


def _score(P):
    days, symdays = _SD
    return summarize(portfolio(symdays, P), days), P


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m backtestceo.momentum.gappers")
    ap.add_argument("cmd", choices=("prepare", "search", "run"))
    ap.add_argument("--end", default="2026-11-03")
    ap.add_argument("--days", type=int, default=60)
    ap.add_argument("--params", default="{}", help="JSON overrides of BASE for `run`")
    ap.add_argument("--out", default=None)
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args(argv)
    days, symdays = prepare(date.fromisoformat(a.end), a.days)
    if a.cmd == "prepare":
        print(f"{len(days)} sessions, {len(symdays)} symbol-days")
    elif a.cmd == "run":
        P = {**BASE, **json.loads(a.params)}
        tr = portfolio(symdays, P)
        print(json.dumps(summarize(tr, days)))
        if a.out:
            Path(a.out).write_text(json.dumps({"params": P, "summary": summarize(tr, days), "trades": tr}, indent=1))
    else:
        from multiprocessing import Pool
        global _SD
        _SD = (days, symdays)
        with Pool(a.workers) as pool:  # fork: workers inherit the loaded data
            rows = pool.map(_score, grid(), chunksize=8)
        rows.sort(key=lambda r: -r[0]["pnl"])
        out = a.out or str(CACHE / f"search_{a.end}.json")
        Path(out).write_text(json.dumps(rows))
        for s, P in rows[:25]:
            print(json.dumps(s), {k: P.get(k) for k in ("side", "kind", "or", "at", "gap", "rvol", "stop", "exit", "until")})
        print(f"{len(rows)} configs; positive: {sum(r[0]['pnl'] > 0 for r in rows)}; wrote {out}")


if __name__ == "__main__":  # run the imported module's main so pickled classes resolve to it, not __main__
    from backtestceo.momentum.gappers import main as _main
    _main()
