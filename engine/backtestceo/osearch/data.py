"""Data layer for the options strategy search.

All Alpaca options history (bars start 2024-02; first expiries we use: 2024-02-01) for SPY QQQ IWM NVDA TSLA AAPL.
Contract listing is not reachable from this environment, so OCC symbols are constructed from expiry calendars
and strike grids; symbols that never existed simply return no bars.

    python3 -m backtestceo.osearch.data          # resumable; prints a progress summary every 5%

Layout under data/osearch/:
  und/{SYM}-30m.json      30-min SIP bars, raw prices (strike matching)    und/{SYM}-30m-adj.json split-adjusted
  und/{SYM}-1d.json       daily SIP bars, split-adjusted (indicators)      und/{SYM}-1d-raw.json raw
  opt/{SYM}/{YYYY-MM-DD}.json.gz   {occ: [[epoch_min, o, h, l, c, v, vw], ...]} 30-min bars for one expiry
"""
import gzip, json, math, os, sys, threading, time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

ROOT = Path(__file__).resolve().parents[3]
DIR = ROOT / "data/osearch"
NY = ZoneInfo("America/New_York")
DATA = "https://data.alpaca.markets"
HDR = {"APCA-API-KEY-ID": os.environ.get("APCA_API_KEY_ID", "x"),
       "APCA-API-SECRET-KEY": os.environ.get("APCA_API_SECRET_KEY", "x")}

SYMBOLS = ["SPY", "QQQ", "IWM", "NVDA", "TSLA", "AAPL"]
INDEX = {"SPY", "QQQ", "IWM"}                 # daily expiries (where they existed)
FIRST_EXP, LAST_DAY = date(2024, 2, 1), date(2026, 11, 2)
BUCKETS = {0: (0, 0), 1: (1, 4), 7: (5, 11), 30: (21, 50)}     # DTE bucket -> calendar-day window
BMIN = {0: 0.015, 1: 0.02, 7: 0.04, 30: 0.08}                  # min strike band (index); singles x2
RATE = 170                                                     # requests / minute (plan limit 200)

_lock = threading.Lock(); _next = [0.0]; _S = threading.local()


def _sess():
    if not hasattr(_S, "s"): _S.s = requests.Session()
    return _S.s


def get(url, params):
    for i in range(20):
        with _lock:
            wait = _next[0] - time.time()
            _next[0] = max(_next[0], time.time()) + 60.0 / RATE
        if wait > 0: time.sleep(wait)
        try:
            r = _sess().get(url, params=params, headers=HDR, timeout=90)
        except requests.RequestException:
            time.sleep(min(2 ** i, 30)); continue
        if r.status_code == 429 or r.status_code >= 500:
            time.sleep(min(2 ** i, 30)); continue
        r.raise_for_status(); return r.json()
    raise RuntimeError(f"giving up on {url}")


def bars(kind, syms, start, end, tf, adjustment="raw"):
    url = f"{DATA}/v2/stocks/bars" if kind == "stocks" else f"{DATA}/v1beta1/options/bars"
    p = dict(symbols=",".join(syms), timeframe=tf, start=start, end=end, limit=10000)
    if kind == "stocks": p.update(feed="sip", adjustment=adjustment)
    out, tok = defaultdict(list), None
    while True:
        body = get(url, {**p, **({"page_token": tok} if tok else {})})
        for s, rows in (body.get("bars") or {}).items(): out[s].extend(rows)
        tok = body.get("next_page_token")
        if not tok: return dict(out)


def ts(s): return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(NY)


def _save(path, obj, gz=False):
    path.parent.mkdir(parents=True, exist_ok=True); tmp = path.with_name(path.name + ".tmp")
    data = json.dumps(obj, separators=(",", ":")).encode()
    tmp.write_bytes(gzip.compress(data, 5) if gz else data); tmp.replace(path)


def load_json(path):
    b = path.read_bytes()
    return json.loads(gzip.decompress(b) if path.suffix == ".gz" else b)


def underlying(sym):
    """Fetch (cached) 30-min raw + adjusted and daily adjusted + raw bars."""
    out = {}
    for name, tf, adj in (("30m", "30Min", "raw"), ("30m-adj", "30Min", "split"), ("1d", "1Day", "split"),
                          ("1d-raw", "1Day", "raw")):
        path = DIR / f"und/{sym}-{name}.json"
        if not path.exists():
            _save(path, bars("stocks", [sym], "2023-01-01T00:00:00Z", f"{LAST_DAY + timedelta(days=1)}T00:00:00Z",
                             tf, adj)[sym])
        out[name] = load_json(path)
    return out


# ---------------------------------------------------------------- calendars
def trading_days():
    rows = underlying("SPY")["1d"]
    return [ts(r["t"]).date() for r in rows]


def expiries(sym, tdays):
    """Candidate expiries: every trading day for index ETFs, Friday (or Thursday before a Friday holiday) else."""
    tset = set(tdays); out = []
    for d in tdays:
        if d < FIRST_EXP: continue
        if sym in INDEX: out.append(d); continue
        if d.weekday() == 4 or (d.weekday() == 3 and (d + timedelta(days=1)) not in tset): out.append(d)
    return out


def is_monthly(e):
    """Third Friday (or the Thursday before it on a holiday)."""
    f = e if e.weekday() == 4 else e + timedelta(days=1)
    return f.weekday() == 4 and 15 <= f.day <= 21


def bucket_expiry(sym, d, bucket, exps_sorted, tdays_idx):
    """Expiry used for an entry on day d in DTE bucket, or None."""
    lo, hi = BUCKETS[bucket]
    best = None
    for e in exps_sorted:
        dte = (e - d).days
        if dte < lo: continue
        if dte > hi: break
        if bucket == 1:
            if tdays_idx.get(e, -9) - tdays_idx.get(d, -99) != 1: continue
        if bucket == 7 and sym in INDEX and e.weekday() != 4 and not (e.weekday() == 3 and is_monthly(e)): continue
        if bucket == 30 and not is_monthly(e): continue
        target = {0: 0, 1: 1, 7: 7, 30: 30}[bucket]
        if best is None or abs(dte - target) < abs((best - d).days - target): best = e
    return best


def strike_grid(sym, lo, hi, near_lo, near_hi):
    """Strikes in [lo, hi]: fine grid near the money, coarse ($5) outside."""
    fine = {"SPY": 1, "QQQ": 1, "IWM": 1, "NVDA": 1, "TSLA": 2.5, "AAPL": 2.5}[sym]
    ks = set()
    k = math.floor(near_lo / fine) * fine
    while k <= near_hi: ks.add(round(k, 2)); k += fine
    k = math.floor(lo / 5) * 5
    while k <= hi: ks.add(float(k)); k += 5
    return sorted(x for x in ks if x > 0)


def occ(sym, e, right, k): return f"{sym}{e:%y%m%d}{right}{int(round(k * 1000)):08d}"


def plan(sym):
    """[(expiry, window_start, [occ symbols])] for every expiry any bucket uses."""
    u = underlying(sym)
    daily = {ts(r["t"]).date(): r for r in u["1d-raw"]}
    adj = [(ts(r["t"]).date(), r["c"]) for r in u["1d"]]
    vol = {}
    for i in range(21, len(adj)):
        rets = [math.log(adj[j][1] / adj[j - 1][1]) for j in range(i - 20, i)]
        m = sum(rets) / 20; vol[adj[i][0]] = math.sqrt(sum((x - m) ** 2 for x in rets) / 19 * 252)
    tdays = [d for d in sorted(daily) if FIRST_EXP <= d <= LAST_DAY]
    tidx = {d: i for i, d in enumerate(sorted(daily))}
    exps = expiries(sym, sorted(daily))
    need = defaultdict(lambda: dict(days=set(), band=0.0, near=0.0))
    for d in tdays:
        for b in BUCKETS:
            e = bucket_expiry(sym, d, b, exps, tidx)
            if e is None or e > LAST_DAY: continue
            sig = min(vol.get(d, 0.3), 1.2)
            mult = 1 if sym in INDEX else 2
            band = max(BMIN[b] * mult, 2.5 * sig * math.sqrt(((e - d).days + 1) / 365))
            n = need[e]; n["days"].add(d); n["band"] = max(n["band"], band)
            n["near"] = max(n["near"], min(band, 0.05 if sym in INDEX else 0.10))
    out = []
    for e, n in sorted(need.items()):
        start = min(n["days"]); window = [d for d in tdays if start <= d <= e]
        hi_px = max(daily[d]["h"] for d in window); lo_px = min(daily[d]["l"] for d in window)
        ks = strike_grid(sym, lo_px * (1 - n["band"]), hi_px * (1 + n["band"]),
                         lo_px * (1 - n["near"]), hi_px * (1 + n["near"]))
        out.append((e, start, [occ(sym, e, r, k) for k in ks for r in "CP"]))
    return out


def fetch_expiry(sym, e, start, syms):
    path = DIR / f"opt/{sym}/{e}.json.gz"
    if path.exists(): return 0
    res = {}
    for i in range(0, len(syms), 100):
        got = bars("options", syms[i:i + 100], f"{start}T13:00:00Z", f"{e}T21:30:00Z", "30Min")
        for s, rows in got.items():
            res[s] = [[int(ts(r["t"]).timestamp() // 60), r["o"], r["h"], r["l"], r["c"], r["v"], r.get("vw", r["c"])]
                      for r in rows]
    _save(path, res, gz=True)
    return 1


def main():
    jobs = []
    for s in SYMBOLS:
        p = plan(s)
        jobs += [(s, e, st, syms) for e, st, syms in p]
        print(f"{s}: {len(p)} expiries, {sum(len(x[2]) for x in p):,} contract symbols", flush=True)
    todo = [j for j in jobs if not (DIR / f"opt/{j[0]}/{j[1]}.json.gz").exists()]
    print(f"{len(jobs)} expiries total, {len(todo)} to fetch", flush=True)
    t0 = time.time(); done = 0; step = max(1, len(todo) // 20)
    with ThreadPoolExecutor(24) as ex:
        futs = [ex.submit(fetch_expiry, *j) for j in todo]
        for f in as_completed(futs):
            f.result(); done += 1
            if done % step == 0 or done == len(todo):
                el = time.time() - t0
                print(f"fetched {done}/{len(todo)} expiries, {el/60:.1f} min, eta {el/done*(len(todo)-done)/60:.0f} min",
                      flush=True)


if __name__ == "__main__":
    main()
