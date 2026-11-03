"""60-trading-day study: 5 structural options strategies + 5 indicator signals (EMA/VWAP/RSI)
traded as options and as shares. Alpaca SIP 5-min underlying bars + Alpaca option 5-min trade bars.

    python -m backtestceo.options60            # fetch (cached under data/options60/) and report

Read-only; no orders. Fills = VWAP of the bar after the signal bar (no quote history on Alpaca,
so option fills are trade-bar based and a modelled half-spread is charged on every leg).
"""
import json, math, os, time
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "data/options60"
OUT = ROOT / "docs/backtests/options60"
NY = ZoneInfo("America/New_York")
DATA = "https://data.alpaca.markets"
HDR = {"APCA-API-KEY-ID": os.environ.get("APCA_API_KEY_ID", "x"),
       "APCA-API-SECRET-KEY": os.environ.get("APCA_API_SECRET_KEY", "x")}
SYMBOLS = ["SPY", "QQQ"]
N_DAYS = 60
END = date(2026, 11, 2)          # last complete session before run date
WARM_START = date(2026, 7, 1)    # indicator warm-up
STRIKE_BAND = 0.025              # fetch strikes within +-2.5% of the day's open
MIN_TRADES = 30

# costs
OPT_FEE = 0.65 + 0.03            # commission + ORF/OCC/FINRA per contract per side
def opt_half_spread(p): return max(0.01, 0.01 * p)   # per share, per leg, per side
SHARE_SLIP = 0.0001              # 1 bp per side
SHARE_QTY = 50                   # delta-matched to one ATM contract (~0.5 delta x 100)
CAPITAL = 10_000.0               # notional account for Sharpe / drawdown %

S = requests.Session()


def get(url, params):
    for i in range(6):
        r = S.get(url, params=params, headers=HDR, timeout=60)
        if r.status_code == 429:
            time.sleep(2 ** i); continue
        r.raise_for_status(); return r.json()
    raise RuntimeError("rate limited")


def bars(kind, syms, start, end, tf="5Min"):
    url = f"{DATA}/v2/stocks/bars" if kind == "stocks" else f"{DATA}/v1beta1/options/bars"
    p = dict(symbols=",".join(syms), timeframe=tf, start=start, end=end, limit=10000)
    if kind == "stocks": p.update(feed="sip", adjustment="raw")
    out, tok = defaultdict(list), None
    while True:
        body = get(url, {**p, **({"page_token": tok} if tok else {})})
        for s, rows in (body.get("bars") or {}).items(): out[s].extend(rows)
        tok = body.get("next_page_token")
        if not tok: return dict(out)


def cached(name, fn):
    path = CACHE / name
    if path.exists(): return json.loads(path.read_text())
    v = fn(); path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp"); tmp.write_text(json.dumps(v)); tmp.replace(path); return v


def ts(s): return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(NY)


# ---------- underlying + indicators ----------
def ema(prev, x, n): return x if prev is None else prev + 2 / (n + 1) * (x - prev)


def underlying(sym):
    raw = cached(f"{sym}-5m.json", lambda: bars("stocks", [sym], f"{WARM_START}T00:00:00Z",
                                                  f"{END + timedelta(days=1)}T00:00:00Z")[sym])
    days = defaultdict(list)
    for r in raw:
        t = ts(r["t"]); m = t.hour * 60 + t.minute
        if 570 <= m < 960:
            days[t.date().isoformat()].append(dict(t=t, hm=t.strftime("%H:%M"), o=r["o"], h=r["h"], l=r["l"],
                                                   c=r["c"], v=r["v"], vw=r.get("vw", r["c"])))
    e9 = e21 = None; gain = loss = None; g2 = l2 = None; prev = None
    for d in sorted(days):
        pv = vv = 0.0
        for b in days[d]:
            c = b["c"]; e9, e21 = ema(e9, c, 9), ema(e21, c, 21)
            pv += b["vw"] * b["v"]; vv += b["v"]
            if prev is not None:
                ch = c - prev; up, dn = max(ch, 0), max(-ch, 0)
                gain = up if gain is None else (gain * 13 + up) / 14; loss = dn if loss is None else (loss * 13 + dn) / 14
                g2 = up if g2 is None else (g2 + up) / 2; l2 = dn if l2 is None else (l2 + dn) / 2
            prev = c
            rsi = lambda g, l: None if g is None else (100.0 if l == 0 else 100 - 100 / (1 + g / l))
            b.update(e9=e9, e21=e21, vwap=pv / vv if vv else c, rsi14=rsi(gain, loss), rsi2=rsi(g2, l2))
    return days


# ---------- option symbols / bars ----------
def occ(sym, exp, right, strike): return f"{sym}{exp:%y%m%d}{right}{int(round(strike * 1000)):08d}"


def option_day(sym, day, exps, open_px):
    """5-min trade bars for all $1 strikes within the band, both rights, given expiries, on `day`."""
    def fetch():
        lo, hi = math.floor(open_px * (1 - STRIKE_BAND)), math.ceil(open_px * (1 + STRIKE_BAND))
        syms = [occ(sym, e, r, k) for e in exps for r in "CP" for k in range(lo, hi + 1)]
        out = {}
        for i in range(0, len(syms), 100):
            out.update(bars("options", syms[i:i + 100], f"{day}T13:00:00Z", f"{day}T21:00:00Z"))
        return {s: {ts(r["t"]).strftime("%H:%M"): r for r in rows} for s, rows in out.items()}
    return cached(f"opt/{sym}-{day}.json", fetch)


class Book:
    def __init__(self, tape): self.tape = tape
    def price(self, sym, hm, lookahead=3):
        """VWAP of the first option bar at/after hm within `lookahead` 5-min bars; None if no prints."""
        bs = self.tape.get(sym)
        if not bs: return None
        h, m = map(int, hm.split(":"))
        for k in range(lookahead):
            mm = h * 60 + m + 5 * k
            r = bs.get(f"{mm // 60:02d}:{mm % 60:02d}")
            if r: return float(r.get("vw") or r["c"])
        return None


def leg_cost(px, qty): return abs(qty) * (opt_half_spread(px) * 100 + OPT_FEE)


# ---------- structural strategies (1 structure / day / underlying) ----------
def structure(name, book, sym, exp, spot, legs_spec, entry_hm, settle_px=None, exit_hm=None, next_book=None):
    """legs_spec: [(right, strike_offset_frac, qty)] qty>0 long. Returns pnl $ or None."""
    legs = []
    for right, off, qty in legs_spec:
        k = round(spot * (1 + off)); s = occ(sym, exp, right, k)
        p = book.price(s, entry_hm)
        if p is None: return None
        legs.append((s, right, k, qty, p))
    pnl = cost = 0.0
    for s, right, k, qty, p in legs:
        pnl -= qty * p * 100 + leg_cost(p, qty); cost += leg_cost(p, qty)
        if settle_px is not None:
            iv = max(0.0, settle_px - k) if right == "C" else max(0.0, k - settle_px)
            pnl += qty * iv * 100          # expiry: intrinsic, no exit commission/spread
        else:
            x = (next_book or book).price(s, exit_hm)
            if x is None: return None
            pnl += qty * x * 100 - leg_cost(x, qty); cost += leg_cost(x, qty)
    return pnl, cost


STRUCTURAL = {
    "0DTE iron condor (short +-0.5%, wings +-1.0%)":
        [("P", -0.010, 1), ("P", -0.005, -1), ("C", 0.005, -1), ("C", 0.010, 1)],
    "0DTE iron butterfly (short ATM, wings +-1.0%)":
        [("P", -0.010, 1), ("P", 0.0, -1), ("C", 0.0, -1), ("C", 0.010, 1)],
    "0DTE bull put spread (short -0.3%, long -0.8%)":
        [("P", -0.003, -1), ("P", -0.008, 1)],
    "0DTE long straddle 09:45 -> 15:30":
        [("C", 0.0, 1), ("P", 0.0, 1)],
    "Overnight 1DTE long straddle 15:50 -> 09:45":
        [("C", 0.0, 1), ("P", 0.0, 1)],
}


# ---------- indicator signals: return +1 / -1 entry, exit predicate ----------
def sig_ema(b, p, pos):
    if p is None: return 0, False
    up, dn = p["e9"] <= p["e21"] and b["e9"] > b["e21"], p["e9"] >= p["e21"] and b["e9"] < b["e21"]
    return (1 if up else -1 if dn else 0), (pos == 1 and dn) or (pos == -1 and up)


def sig_vwap(b, p, pos):
    if p is None: return 0, False
    up, dn = p["c"] <= p["vwap"] and b["c"] > b["vwap"], p["c"] >= p["vwap"] and b["c"] < b["vwap"]
    return (1 if up else -1 if dn else 0), (pos == 1 and dn) or (pos == -1 and up)


def sig_rsi2(b, p, pos):
    r = b["rsi2"]
    if r is None: return 0, False
    return (1 if r < 10 else -1 if r > 90 else 0), (pos == 1 and r > 50) or (pos == -1 and r < 50)


def sig_ema_vwap_pullback(b, p, pos):
    if p is None: return 0, False
    lng = b["c"] > b["vwap"] and b["e9"] > b["e21"] and b["l"] <= b["e9"] < b["c"]
    sht = b["c"] < b["vwap"] and b["e9"] < b["e21"] and b["h"] >= b["e9"] > b["c"]
    ex = (pos == 1 and b["c"] < b["e21"]) or (pos == -1 and b["c"] > b["e21"])
    return (1 if lng else -1 if sht else 0), ex


def sig_rsi_vwap(b, p, pos):
    if p is None or p["rsi14"] is None: return 0, False
    up = p["rsi14"] <= 50 < b["rsi14"] and b["c"] > b["vwap"]
    dn = p["rsi14"] >= 50 > b["rsi14"] and b["c"] < b["vwap"]
    ex = (pos == 1 and (b["rsi14"] < 45 or b["c"] < b["vwap"])) or (pos == -1 and (b["rsi14"] > 55 or b["c"] > b["vwap"]))
    return (1 if up else -1 if dn else 0), ex


INDICATOR = {
    "EMA 9/21 cross": sig_ema,
    "VWAP cross": sig_vwap,
    "RSI(2) 10/90 reversion": sig_rsi2,
    "EMA9 pullback w/ VWAP+EMA21 trend": sig_ema_vwap_pullback,
    "RSI(14) 50-cross w/ VWAP filter": sig_rsi_vwap,
}
LAST_ENTRY, FLAT_AT = "15:30", "15:50"


def signal_trades(day_bars, fn):
    """Intraday trades [(side, entry_idx, exit_idx)]; fills at bar idx+1 (next bar VWAP); flat by close."""
    out, pos, ent, side = [], 0, None, 0
    flat_i = next(i for i, b in enumerate(day_bars) if b["hm"] >= FLAT_AT) if day_bars[-1]["hm"] >= FLAT_AT else len(day_bars) - 2
    for i, b in enumerate(day_bars[:flat_i + 1]):
        p = day_bars[i - 1] if i else None
        e, x = fn(b, p, pos)
        if pos and (x or i == flat_i or (e and e != pos)):
            out.append((pos, ent, i)); pos = 0
        if not pos and e and b["hm"] < LAST_ENTRY and i < flat_i:
            pos, ent = e, i
    return out


# ---------- metrics ----------
def metrics(trades, days):
    pnl = [t["pnl"] for t in trades]
    n = len(pnl)
    if not n: return dict(trades=0)
    daily = defaultdict(float)
    for t in trades: daily[t["day"]] += t["pnl"]
    series = [daily.get(d, 0.0) for d in days]
    eq, peak, mdd = 0.0, 0.0, 0.0
    for x in series:
        eq += x; peak = max(peak, eq); mdd = min(mdd, eq - peak)
    r = [x / CAPITAL for x in series]; mu = sum(r) / len(r)
    sd = math.sqrt(sum((x - mu) ** 2 for x in r) / (len(r) - 1)) if len(r) > 1 else 0
    return dict(trades=n, win=sum(x > 0 for x in pnl) / n, exp=sum(pnl) / n, total=sum(pnl), mdd=mdd,
                sharpe=(mu / sd * math.sqrt(252)) if sd else 0.0, costs=sum(t["cost"] for t in trades))


def main():
    und = {s: underlying(s) for s in SYMBOLS}
    all_days = sorted(set.intersection(*(set(d) for d in und.values())))
    all_days = [d for d in all_days if date.fromisoformat(d) <= END]
    days = all_days[-N_DAYS:]
    nxt = {d: all_days[i + 1] if i + 1 < len(all_days) else None for i, d in enumerate(all_days)}
    nxt[END.isoformat()] = (END + timedelta(days=1)).isoformat()     # Nov 3 2026 session exists (run date)
    results, trades = {}, defaultdict(list)
    skipped = defaultdict(int)

    for sym in SYMBOLS:
        for d in days:
            bs = und[sym][d]
            if len(bs) < 70: skipped["short-session"] += 1; continue
            e0, e1 = date.fromisoformat(d), date.fromisoformat(nxt[d])
            book = Book(option_day(sym, d, [e0, e1], bs[0]["o"]))
            by = {b["hm"]: b for b in bs}
            close = bs[-1]["c"]

            # structural
            for name, spec in STRUCTURAL.items():
                if name.startswith("Overnight"):
                    if d == days[-1]: continue
                    nb = und[sym][nxt[d]]
                    nbook = Book(option_day(sym, nxt[d], [e1, date.fromisoformat(nxt.get(nxt[d]) or nxt[d])], nb[0]["o"]))
                    spot = by["15:45"]["c"]
                    pnl = structure(name, book, sym, e1, spot, spec, "15:50", exit_hm="09:45", next_book=nbook)
                elif "straddle" in name:
                    pnl = structure(name, book, sym, e0, by["09:40"]["c"], spec, "09:45", exit_hm="15:30")
                else:
                    pnl = structure(name, book, sym, e0, by["09:55"]["c"], spec, "10:00", settle_px=close)
                if pnl is None: skipped[name] += 1; continue
                trades[name].append(dict(day=d, sym=sym, pnl=pnl[0], cost=pnl[1]))

            # indicator: options (ATM, next-day expiry) vs shares
            for name, fn in INDICATOR.items():
                for side, i, j in signal_trades(bs, fn):
                    eb, xb = bs[i + 1], bs[j + 1]
                    # shares
                    sp = side * (xb["vw"] - eb["vw"]) * SHARE_QTY
                    sc = SHARE_SLIP * (eb["vw"] + xb["vw"]) * SHARE_QTY
                    trades[name + " | shares"].append(dict(day=d, sym=sym, pnl=sp - sc, cost=sc))
                    # option: ATM at signal close, nearest expiry >= 1 day
                    right = "C" if side == 1 else "P"
                    s = occ(sym, e1, right, round(bs[i]["c"]))
                    pe, px = book.price(s, eb["hm"], 2), book.price(s, xb["hm"], 2)
                    if pe is None or px is None: skipped[name + " | options"] += 1; continue
                    c = leg_cost(pe, 1) + leg_cost(px, 1)
                    trades[name + " | options"].append(dict(day=d, sym=sym, pnl=(px - pe) * 100 - c, cost=c))

    rows = []
    order = list(STRUCTURAL) + [f"{n} | {k}" for n in INDICATOR for k in ("options", "shares")]
    for name in order:
        m = metrics(trades[name], days)
        m.update(name=name, status="OK" if m["trades"] >= MIN_TRADES else f"REJECTED (<{MIN_TRADES})",
                 skipped=skipped.get(name, 0))
        rows.append(m)
    report(rows, days, trades)


def report(rows, days, trades):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "results.json").write_text(json.dumps(rows, indent=1))
    with open(OUT / "trades.csv", "w") as f:
        f.write("strategy,day,symbol,pnl,cost\n")
        for name, ts_ in trades.items():
            for t in ts_: f.write(f"\"{name}\",{t['day']},{t['sym']},{t['pnl']:.2f},{t['cost']:.2f}\n")
    L = [f"# Options vs shares, {days[0]} to {days[-1]} ({len(days)} sessions), {', '.join(SYMBOLS)}", "",
         "| Strategy | Trades | Win % | Expectancy $/trade | Total $ | Max DD $ | Sharpe | Costs $ | Status |",
         "|---|---:|---:|---:|---:|---:|---:|---:|---|"]
    for r in rows:
        if not r["trades"]:
            L.append(f"| {r['name']} | 0 | | | | | | | {r['status']} |"); continue
        L.append(f"| {r['name']} | {r['trades']} | {r['win']*100:.1f} | {r['exp']:.2f} | {r['total']:.0f} | "
                 f"{r['mdd']:.0f} | {r['sharpe']:.2f} | {r['costs']:.0f} | {r['status']} |")
    (OUT / "README.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
