"""Premarket momentum: universe built from premarket bars themselves (no regular-session lookahead).

For each session, 04:00-09:29 1-minute bars are pulled for every symbol whose previous close is $1.50-25 and
20-day ADV >= 50k shares. A symbol-day is a candidate if any premarket bar trades >= +10% above the previous
close; that includes runners that collapse before the open. Full-day bars are then cached for candidates.

    python -m backtestceo.momentum.premarket prepare --end 2026-11-03
    python -m backtestceo.momentum.premarket drift   --end 2026-11-03
    python -m backtestceo.momentum.premarket search  --end 2026-11-03
"""
import argparse
import hashlib
import itertools
import json
import pickle
import statistics as st
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

from .backtest import sessions, tradable_symbol
from .data import CACHE, ET, Data, parse_t, pmap
from .gappers import SymDay

PM_GAP = 10.0


def _daily_context(data, days, prev, log):
    syms = set()
    for d in days:
        try:
            news = data.news_for_day(d, prev[d], "11:30")
        except RuntimeError:
            news = []
        for n in news:
            syms |= {s for s in n["symbols"] if tradable_symbol(s)}
    syms = sorted(syms)
    start, end = days[0] - timedelta(days=42), days[-1]
    tag = f"news{len(syms)}_" + hashlib.sha1(",".join(syms).encode()).hexdigest()[:10]
    raw = data.daily_cached(syms, start, end, "raw", tag)
    adj = data.daily_cached(syms, start, end, "split", tag)
    ctx = {d: {} for d in days}
    for s in syms:
        a = [(parse_t(b["t"]).astimezone(ET).date(), b) for b in adj.get(s, [])]
        r = {parse_t(b["t"]).astimezone(ET).date(): b for b in raw.get(s, [])}
        for k, (dd, b) in enumerate(a):
            if dd not in ctx or k < 10 or a[k - 1][0] != prev[dd]:
                continue
            # as-of-d units: use the raw/adj factor of the previous session (known before the open)
            pd_ = a[k - 1][0]
            f = r[pd_]["c"] / a[k - 1][1]["c"] if pd_ in r and a[k - 1][1]["c"] else 1.0
            hist = a[max(0, k - 20):k]
            pc = hist[-1][1]["c"] * f
            adv = sum(x["v"] for _, x in hist) / len(hist) / f
            if 1.5 <= pc <= 25 and adv >= 50_000:
                trs = [max(x["h"] - x["l"], abs(x["h"] - y["c"]), abs(x["l"] - y["c"])) for (_, y), (_, x) in zip(hist[-15:], hist[-14:])]
                ctx[dd][s] = {"sym": s, "pc": pc, "adv": adv, "atr": (sum(trs) / len(trs) * f) if trs else 0.0}
    log(f"premarket context: {len(syms)} symbols, avg {sum(len(v) for v in ctx.values()) / len(days):.0f} eligible/day")
    return ctx


def _pm_candidates(data, d, elig: dict):
    p = CACHE / "premarket" / f"{d}.json"
    if p.exists():
        return json.loads(p.read_text())
    syms = sorted(elig)
    out = []
    for i in range(0, len(syms), 400):
        chunk = syms[i:i + 400]
        bars = data._bars(chunk, "1Min", datetime_et(d, 4, 0), datetime_et(d, 9, 29), "raw")
        for s, rows in bars.items():
            if rows and max(r["h"] for r in rows) >= elig[s]["pc"] * (1 + PM_GAP / 100):
                out.append(s)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(sorted(out)))
    return sorted(out)


def datetime_et(d, h, m):
    from datetime import datetime, time as dtime
    return datetime.combine(d, dtime(h, m), ET)


def prepare(end: date, n_days: int = 60, log=print):
    p = CACHE / f"premarket_{end}_{n_days}.pkl"
    if p.exists():
        with open(p, "rb") as f:
            return pickle.load(f)
    data = Data()
    days, prev = sessions(data, n_days, end)
    ctx = _daily_context(data, days, prev, log)

    def one(d):
        cands = _pm_candidates(data, d, ctx[d])
        bars = data.minute(cands, d, "04:00", "16:00") if cands else {}
        sds = [SymDay.build(d, ctx[d][s], bars.get(s, [])) for s in cands]
        log(f"{d}: {len(cands)} premarket runners")
        return [x for x in sds if x]

    symdays = [x for chunk in pmap(one, days, 3) for x in chunk]
    out = (days, symdays)
    with open(p, "wb") as f:
        pickle.dump(out, f)
    return out


# ------------------------------------------------------------------ premarket trade simulation
def slip(px, pct):
    return max(0.01, px * pct / 100)


def pm_rvol(sd, i):
    """Premarket relative volume: volume since 04:00 / 20-day ADV (no time scaling; 0.1 = 10% of a normal day)."""
    return sd.cumv[i] / sd.adv if sd.adv else 0.0


def simulate(sd, P):
    """Long entries in premarket. Returns (entry_min, exit_min, entry, stop, exit, why) or None.

    kind 'hod'  : buy the break of the premarket high of day while up >= gap% and pm volume >= vol x ADV
    kind 'pb'   : after a new high, 1-3 bar pullback holding above VWAP, buy the break of the last bar's high
    kind 'first': first bar that reaches +gap% with volume: buy the next bar's open (momentum ignition)
    Exits: stop (swing low / pct), target R, trail prior-bar low after +1R, time exit at `exit_at`.
    """
    n, pc = len(sd.m), sd.pc
    sl = P["slip"]
    t0, t1, tx = P["from"], P["until"], P["exit_at"]
    hod = 0.0
    for k in range(1, n):
        m = sd.m[k]
        prev = k - 1
        hod_prev = hod
        hod = max(hod, sd.h[prev])
        if m < t0:
            continue
        if m > t1:
            return None
        up = (sd.c[prev] / pc - 1) * 100
        if up < P["gap"] or pm_rvol(sd, prev) < P["vol"] or not (P["pmin"] <= sd.c[prev] <= P["pmax"]):
            continue
        if P.get("vwap", True) and sd.c[prev] <= sd.vwap[prev]:
            continue
        kind = P["kind"]
        level = None
        if kind == "hod":
            level = round(hod + 0.01, 2)
        elif kind == "pb":
            j = max(range(max(0, prev - 3), prev + 1), key=lambda x: sd.h[x])
            if j < prev and sd.h[j] >= hod - 1e-9 and sd.l[prev] > sd.vwap[prev]:
                level = round(sd.h[prev] + 0.01, 2)
        elif kind == "first":
            level = sd.o[k]
        if level is None or sd.h[k] < level:
            continue
        if sd.o[k] > level * 1.01 and kind != "first":
            continue
        fill = max(sd.o[k], level) + slip(level, sl)
        if P["stop"] == "swing":
            stop = round(min(sd.l[max(0, k - 5):k]) - 0.01, 2)
        else:
            stop = round(fill * (1 - float(P["stop"][3:]) / 100), 2)
        if stop >= fill or (fill - stop) / fill * 100 > P.get("max_stop", 10) or fill - stop < 0.02:
            continue
        return _exit(sd, P, k, fill, stop)
    return None


def _exit(sd, P, k, fill, stop):
    n, sl, r = len(sd.m), P["slip"], fill - stop
    tgt = fill + P["tgt"] * r if P.get("tgt") else None
    trail = False
    s0 = stop  # report the initial stop: sizing and R use it, not the trailed one
    for j in range(k, n):
        if sd.l[j] <= stop:
            px = stop if j == k else min(sd.o[j], stop)
            return sd.m[k], sd.m[j], fill, s0, px - slip(px, sl), "trail" if trail else "stop"
        if tgt and j > k and sd.h[j] >= tgt + 0.01:
            return sd.m[k], sd.m[j], fill, s0, tgt, "target"
        if sd.m[j] >= P["exit_at"]:
            return sd.m[k], sd.m[j], fill, s0, sd.c[j] - slip(sd.c[j], sl), "time"
        if P.get("trail") and j > k:
            if sd.h[j] >= fill + r:
                trail = True
            if trail:
                stop = max(stop, round(sd.l[j] - 0.01, 2))
    j = n - 1
    return sd.m[k], sd.m[j], fill, s0, sd.c[j] - slip(sd.c[j], sl), "last"


def portfolio(symdays, P, risk=100.0, max_notional=10_000.0, liq=0.1, daily_max_loss=300.0, max_pos=2):
    by_day = defaultdict(list)
    for sd in symdays:
        t = simulate(sd, P)
        if t:
            by_day[sd.d].append((t, sd))
    trades = []
    for d in sorted(by_day):
        open_, realized = [], 0.0
        for t, sd in sorted(by_day[d], key=lambda x: x[0][0]):
            em, xm, fill, stop, px, why = t
            realized += sum(p for x, p in open_ if x <= em)
            open_ = [(x, p) for x, p in open_ if x > em]
            if len(open_) >= max_pos or realized <= -daily_max_loss:
                continue
            k = sd.m.index(em)
            avgv = sum(sd.v[max(0, k - 5):k]) / max(1, len(sd.v[max(0, k - 5):k]))
            q = int(min(risk / (fill - stop), max_notional / fill, avgv * liq))
            if q < 1:
                continue
            pnl = (px - fill) * q
            open_.append((xm, pnl))
            trades.append({"date": str(d), "sym": sd.sym, "entry": f"{em // 60:02d}:{em % 60:02d}",
                           "exit": f"{xm // 60:02d}:{xm % 60:02d}", "fill": round(fill, 4), "stop": stop,
                           "px": round(px, 4), "why": why, "shares": q, "pnl": round(pnl, 2),
                           "r": round((px - fill) / (fill - stop), 3)})
    return trades


def summarize(trades, days):
    pnl = [t["pnl"] for t in trades]
    w, lo = sum(x for x in pnl if x > 0), -sum(x for x in pnl if x < 0)
    mid = str(days[len(days) // 2 - 1])
    return {"n": len(trades), "pnl": round(sum(pnl), 2), "pf": round(w / lo, 2) if lo else None,
            "wr": round(sum(x > 0 for x in pnl) / len(pnl), 3) if pnl else 0,
            "avg_r": round(st.mean(t["r"] for t in trades), 3) if trades else 0,
            "h1": round(sum(t["pnl"] for t in trades if t["date"] <= mid), 2),
            "h2": round(sum(t["pnl"] for t in trades if t["date"] > mid), 2)}


BASE = {"kind": "hod", "gap": 20.0, "vol": 0.2, "pmin": 2.0, "pmax": 20.0, "from": 420, "until": 555, "exit_at": 569,
        "stop": "swing", "tgt": 2.0, "trail": False, "slip": 0.5, "vwap": True, "max_stop": 10}


def grid():
    out = []
    for kind, gap, vol, stop, ex, tw in itertools.product(
            ("hod", "pb", "first"), (10.0, 20.0, 40.0), (0.05, 0.2, 0.5), ("swing", "pct5"),
            (("tgt", 2.0, False), ("tgt", 0, True), ("tgt", 0, False)), ((420, 555, 569), (420, 555, 585), (480, 555, 569))):
        out.append({**BASE, "kind": kind, "gap": gap, "vol": vol, "stop": stop, "tgt": ex[1], "trail": ex[2],
                    "from": tw[0], "until": tw[1], "exit_at": tw[2]})
    return out


_D = None


def _score(P):
    days, sds = _D
    return summarize(portfolio(sds, P), days), P


def drift(days, sds):
    """Return from the first premarket bar that is up >= G% with volume >= V x ADV (07:00-09:15) to 09:29 / 09:45."""
    for G in (10, 20, 40):
        for V in (0.05, 0.2):
            r929, r945 = [], []
            for sd in sds:
                for k in range(1, len(sd.m)):
                    m = sd.m[k]
                    if m < 420:
                        continue
                    if m > 555:
                        break
                    p = k - 1
                    if (sd.c[p] / sd.pc - 1) * 100 >= G and pm_rvol(sd, p) >= V and 2 <= sd.c[p] <= 20:
                        e = sd.o[k]
                        a = next((x for x in range(k, len(sd.m)) if sd.m[x] >= 569), None)
                        b = next((x for x in range(k, len(sd.m)) if sd.m[x] >= 585), None)
                        if a is not None:
                            r929.append((sd.c[a] / e - 1) * 100)
                        if b is not None:
                            r945.append((sd.c[b] / e - 1) * 100)
                        break
            if r929:
                print(f"up>={G}% vol>={V}xADV  n={len(r929):4d}  to 09:29 mean {st.mean(r929):6.2f}% med {st.median(r929):6.2f}% "
                      f"up {sum(x > 0 for x in r929) / len(r929):.2f} | to 09:45 mean {st.mean(r945):6.2f}% med {st.median(r945):6.2f}%")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m backtestceo.momentum.premarket")
    ap.add_argument("cmd", choices=("prepare", "drift", "search", "run"))
    ap.add_argument("--end", default="2026-11-03")
    ap.add_argument("--params", default="{}")
    ap.add_argument("--workers", type=int, default=3)
    a = ap.parse_args(argv)
    days, sds = prepare(date.fromisoformat(a.end))
    if a.cmd == "prepare":
        print(len(days), "sessions,", len(sds), "symbol-days")
    elif a.cmd == "drift":
        drift(days, sds)
    elif a.cmd == "run":
        print(json.dumps(summarize(portfolio(sds, {**BASE, **json.loads(a.params)}), days)))
    else:
        from multiprocessing import Pool
        global _D
        _D = (days, sds)
        with Pool(a.workers) as pool:
            rows = pool.map(_score, grid(), chunksize=8)
        Path(CACHE / f"pm_search_{a.end}.json").write_text(json.dumps(rows))
        rows.sort(key=lambda r: -r[0]["pnl"])
        for s, P in rows[:15]:
            print(json.dumps(s), {k: P[k] for k in ("kind", "gap", "vol", "stop", "tgt", "trail", "from", "exit_at")})
        print(len(rows), "configs; positive:", sum(r[0]["pnl"] > 0 for r in rows),
              "; positive both halves:", sum(r[0]["h1"] > 0 and r[0]["h2"] > 0 for r in rows))


if __name__ == "__main__":
    from backtestceo.momentum.premarket import main as _main
    _main()


# ------------------------------------------------------------------ premarket fade (short)
PMF = {"gap": 30.0, "vol": 0.1, "pmin": 2.0, "pmax": 20.0, "from": 420, "until": 555, "stop_pct": 50.0,
       "cover": 955, "slip": 0.5, "notional": 1000.0, "max_pos": 5, "liq": 0.1}


def pm_fade_signal(sd, P):
    """First premarket bar (from..until) closing >= +gap% with pm volume >= vol x ADV -> short the next bar's open."""
    for k in range(1, len(sd.m)):
        m, p = sd.m[k], k - 1
        if sd.m[p] < P["from"]:
            continue
        if m > P["until"] + 1:
            return None
        if (sd.c[p] / sd.pc - 1) * 100 >= P["gap"] and pm_rvol(sd, p) >= P["vol"] and P["pmin"] <= sd.c[p] <= P["pmax"]:
            return k
    return None


def pm_fade(days, symdays, P):
    by_day = defaultdict(list)
    for sd in symdays:
        k = pm_fade_signal(sd, P)
        if k is not None:
            by_day[sd.d].append((sd.m[k], k, sd))
    trades = []
    for d in sorted(by_day):
        for _, k, sd in sorted(by_day[d], key=lambda x: x[0])[:P["max_pos"]]:  # earliest signals first
            fill = sd.o[k] - slip(sd.o[k], P["slip"])
            stop = fill * (1 + P["stop_pct"] / 100)
            q = int(min(P["notional"] / fill, sum(sd.v[max(0, k - 5):k]) / 5 * P["liq"] * 5))
            if q < 1:
                continue
            for j in range(k, len(sd.m)):
                if sd.h[j] >= stop:
                    px = stop if j == k else max(sd.o[j], stop)
                    px += slip(px, P["slip"]); why = "stop"; break
                if sd.m[j] >= P["cover"]:
                    px = sd.c[j] + slip(sd.c[j], 0.2 if sd.m[j] >= 570 else P["slip"]); why = "cover"; break
            else:
                j = len(sd.m) - 1; px = sd.c[j] + slip(sd.c[j], 0.2); why = "last"
            trades.append({"date": str(d), "sym": sd.sym, "entry": f"{sd.m[k] // 60:02d}:{sd.m[k] % 60:02d}",
                           "up_pct": round((sd.o[k] / sd.pc - 1) * 100, 1), "fill": round(fill, 4), "px": round(px, 4),
                           "why": why, "shares": q, "pnl": round((fill - px) * q, 2), "ret_pct": round((fill - px) / fill * 100, 2)})
    return trades


def pm_fade_stats(trades, days):
    pnl = [t["pnl"] for t in trades]
    byd = defaultdict(float)
    for t in trades:
        byd[t["date"]] += t["pnl"]
    eq = peak = dd = 0.0
    for d in days:
        eq += byd.get(str(d), 0.0); peak = max(peak, eq); dd = min(dd, eq - peak)
    w, lo = sum(x for x in pnl if x > 0), -sum(x for x in pnl if x < 0)
    mid = str(days[len(days) // 2 - 1])
    return {"trades": len(trades), "net_pnl": round(sum(pnl), 2), "pf": round(w / lo, 2) if lo else None,
            "win_rate": round(sum(x > 0 for x in pnl) / len(pnl), 3) if pnl else 0,
            "avg_ret_pct": round(st.mean(t["ret_pct"] for t in trades), 2) if trades else 0,
            "green_days": f"{sum(v > 0 for v in byd.values())}/{len(byd)}", "max_dd": round(dd, 2),
            "stops": sum(t["why"] == "stop" for t in trades), "worst": min(pnl) if pnl else 0,
            "h1": round(sum(t["pnl"] for t in trades if t["date"] <= mid), 2),
            "h2": round(sum(t["pnl"] for t in trades if t["date"] > mid), 2)}
