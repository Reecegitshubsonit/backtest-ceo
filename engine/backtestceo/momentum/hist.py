"""Full-history data pipeline (2016-01 .. 2026-11) for the momentum parameter search. Resumable: every stage writes
per-chunk / per-day files under ~/.cache/backtest-ceo/momentum/hist and skips what exists.

Stages
  universe  symbols = news on every 5th trading day + all corporate-action symbols (splits, name changes,
            mergers, worthless removals). Alpaca's asset list (which includes delisted names) is not reachable
            from here, so coverage is measured and reported as survivorship bias.
  daily     raw + split-adjusted daily bars -> per-day eligible table (prev close $0.5-25, 20d ADV >= 50k)
  scan      regular-session gappers (daily high >= +10%) plus premarket runners (5-min bars 04:00-09:29,
            high >= +10%): daily bars are regular-session only, so premarket needs its own scan
  minute    1-min bars 04:00-12:00 for candidates, compact .npz per day
  news      headlines for candidates, prev 16:00 -> 12:00, one symbol-filtered query per day
  quotes    NBBO samples to fit the spread model

    python -m backtestceo.momentum.hist all
"""
import json
import sys
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, time as dtime, timedelta, timezone
from pathlib import Path

import numpy as np
import requests

from .backtest import tradable_symbol
from .data import CACHE, ET, iso, parse_t

ROOT = CACHE / "hist"
START, END = date(2016, 1, 4), date(2026, 11, 3)
DATA = "https://data.alpaca.markets"
H = {"APCA-API-KEY-ID": "placeholder", "APCA-API-SECRET-KEY": "placeholder"}


class Limiter:
    def __init__(self, per_min=190):
        self.gap, self.lock, self.next = 60.0 / per_min, threading.Lock(), 0.0

    def wait(self):
        with self.lock:
            now = time.time()
            t = max(now, self.next)
            self.next = t + self.gap
        if t > now:
            time.sleep(t - now)


LIM = Limiter()
_tl = threading.local()


def get(path, params, tries=10):
    s = getattr(_tl, "s", None) or requests.Session()
    _tl.s = s
    for a in range(tries):
        LIM.wait()
        try:
            r = s.get(DATA + path, params=params, headers=H, timeout=90)
        except requests.RequestException:
            time.sleep(2 * (a + 1)); continue
        if r.status_code == 200:
            return r.json()
        if r.status_code == 429 or r.status_code >= 500:
            time.sleep(5 * (a + 1)); continue
        raise RuntimeError(f"{path} {r.status_code} {r.text[:200]}")
    raise RuntimeError(f"{path}: retries exhausted")


def paged(path, params, key):
    tok = None
    while True:
        b = get(path, {**params, **({"page_token": tok} if tok else {})})
        yield b.get(key) or {}
        tok = b.get("next_page_token")
        if not tok:
            return


def log(*a):
    print(datetime.now().strftime("%H:%M:%S"), *a, flush=True)


def et(d, hh, mm):
    return datetime.combine(d, dtime(hh, mm), ET)


def jload(p):
    return json.loads(Path(p).read_text())


def jsave(p, obj):
    p = Path(p); p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp"); tmp.write_text(json.dumps(obj)); tmp.replace(p)


# ------------------------------------------------------------------ calendar
def sessions():
    p = ROOT / "sessions.json"
    if p.exists():
        return [date.fromisoformat(x) for x in jload(p)]
    rows = []
    for page in paged("/v2/stocks/bars", {"symbols": "SPY", "timeframe": "1Day", "start": "2015-11-01", "end": f"{END}",
                                          "limit": 10000, "feed": "sip", "adjustment": "raw"}, "bars"):
        rows += page.get("SPY", [])
    days = [parse_t(b["t"]).astimezone(ET).date() for b in rows]
    jsave(p, [str(x) for x in days])
    return days


# ------------------------------------------------------------------ universe
def stage_universe():
    p = ROOT / "universe.json"
    if p.exists():
        return jload(p)
    days = [d for d in sessions() if d >= START]
    sample = days[::5]

    def news_day(d):
        f = ROOT / "news_sample" / f"{d}.json"
        if f.exists():
            return jload(f)
        syms = set()
        for page in paged("/v1beta1/news", {"start": iso(et(d, 0, 0)), "end": iso(et(d, 23, 59)), "limit": 50,
                                             "include_content": "false"}, "news"):
            for n in page:
                syms |= set(n.get("symbols") or [])
        jsave(f, sorted(syms))
        return sorted(syms)

    syms = set()
    with ThreadPoolExecutor(4) as ex:
        for k, s in enumerate(ex.map(news_day, sample)):
            syms |= set(s)
            if k % 50 == 0:
                log(f"news sample {k}/{len(sample)}: {len(syms)} symbols")
    ca = set()
    m = date(2016, 1, 1)
    while m <= END:
        f = ROOT / "corp" / f"{m:%Y-%m}.json"
        if f.exists():
            got = jload(f)
        else:
            nxt = (m.replace(day=28) + timedelta(days=4)).replace(day=1)
            got = set()
            for page in paged("/v1beta1/corporate-actions", {"start": str(m), "end": str(min(nxt - timedelta(days=1), END)),
                                                             "limit": 1000}, "corporate_actions"):
                for rows in page.values():
                    for r in rows:
                        for k_, v in r.items():
                            if k_.endswith("symbol") and isinstance(v, str):
                                got.add(v)
            got = sorted(got); jsave(f, got)
        ca |= set(got)
        m = (m.replace(day=28) + timedelta(days=4)).replace(day=1)
    log(f"corporate-action symbols: {len(ca)}")
    allsyms = sorted(s for s in syms | ca if tradable_symbol(s))
    jsave(p, {"symbols": allsyms, "news_sample_days": len(sample), "news_symbols": len(syms), "corp_symbols": len(ca)})
    log(f"universe: {len(allsyms)} symbols")
    return jload(p)


# ------------------------------------------------------------------ daily -> eligible
def stage_daily(chunk=300):
    syms = stage_universe()["symbols"]
    days = sessions()
    didx = {d: i for i, d in enumerate(days)}
    out = ROOT / "daily"
    out.mkdir(parents=True, exist_ok=True)

    def one(ci):
        f = out / f"{ci:04d}.npz"
        if f.exists():
            return
        part = syms[ci * chunk:(ci + 1) * chunk]
        raw, adj = defaultdict(list), defaultdict(list)
        for store, a in ((raw, "raw"), (adj, "split")):
            for page in paged("/v2/stocks/bars", {"symbols": ",".join(part), "timeframe": "1Day", "start": "2015-11-01",
                                                  "end": f"{END}", "limit": 10000, "feed": "sip", "adjustment": a}, "bars"):
                for s, rows in page.items():
                    store[s] += rows
        cols = defaultdict(list)
        for s in part:
            r = {parse_t(b["t"]).astimezone(ET).date(): b for b in raw.get(s, [])}
            A = [(parse_t(b["t"]).astimezone(ET).date(), b) for b in adj.get(s, [])]
            for k in range(10, len(A)):
                d, b = A[k]
                if d < START or d not in r or d not in didx or didx[d] == 0 or A[k - 1][0] != days[didx[d] - 1]:
                    continue
                if not b["c"]:
                    continue
                f_ = r[d]["c"] / b["c"]
                hist = A[max(0, k - 20):k]
                pc = hist[-1][1]["c"] * f_
                adv = sum(x["v"] for _, x in hist) / len(hist) / f_
                if not (0.5 <= pc <= 25) or adv < 50_000:
                    continue
                trs = [max(x["h"] - x["l"], abs(x["h"] - y["c"]), abs(x["l"] - y["c"])) for (_, y), (_, x) in zip(hist[-15:-1], hist[-14:])]
                cols["day"].append(didx[d]); cols["sym"].append(s); cols["pc"].append(pc); cols["adv"].append(adv)
                cols["atr"].append(sum(trs) / len(trs) * f_ if trs else 0.0)
                cols["o"].append(r[d]["o"]); cols["h"].append(r[d]["h"]); cols["l"].append(r[d]["l"])
        np.savez(f, day=np.array(cols["day"], np.int32), sym=np.array(cols["sym"], dtype="U5"),
                 **{k: np.array(cols[k], np.float64) for k in ("pc", "adv", "atr", "o", "h", "l")})

    n = (len(syms) + chunk - 1) // chunk
    with ThreadPoolExecutor(3) as ex:
        for k, _ in enumerate(ex.map(one, range(n))):
            if k % 5 == 0:
                log(f"daily chunk {k + 1}/{n}")


def eligible():
    """Concatenate the daily chunks -> dict of arrays."""
    p = ROOT / "eligible.npz"
    if p.exists():
        z = np.load(p); return {k: z[k] for k in z.files}
    parts = [np.load(f) for f in sorted((ROOT / "daily").glob("*.npz"))]
    out = {k: np.concatenate([z[k] for z in parts]) for k in parts[0].files}
    np.savez(p, **out)
    return out


# ------------------------------------------------------------------ candidate scan
GAP = 10.0


def stage_scan():
    days = sessions()
    E = eligible()
    order = np.argsort(E["day"], kind="stable")
    bounds = np.searchsorted(E["day"][order], np.arange(len(days) + 1))
    out = ROOT / "cands"

    def one(di):
        d = days[di]
        f = out / f"{d}.json"
        if d < START or f.exists():
            return
        idx = order[bounds[di]:bounds[di + 1]]
        if len(idx) == 0:
            jsave(f, []); return
        pc = {E["sym"][i]: (E["pc"][i], E["adv"][i], E["atr"][i]) for i in idx}
        reg = {E["sym"][i] for i in idx if E["h"][i] >= E["pc"][i] * (1 + GAP / 100) and E["l"][i] <= 20 and E["h"][i] >= 1}
        pm = set()
        syms = sorted(pc)
        for c in range(0, len(syms), 4000):  # one request carries all ~3,300 eligible symbols
            part = syms[c:c + 4000]
            for page in paged("/v2/stocks/bars", {"symbols": ",".join(part), "timeframe": "1Hour", "start": iso(et(d, 4, 0)),
                                                  "end": iso(et(d, 9, 29)), "limit": 10000, "feed": "sip", "adjustment": "raw"}, "bars"):
                for s, rows in page.items():
                    if s in pc and max(r["h"] for r in rows) >= pc[s][0] * (1 + GAP / 100) and min(r["l"] for r in rows) <= 25:
                        pm.add(s)
        jsave(f, [{"sym": s, "pc": pc[s][0], "adv": pc[s][1], "atr": pc[s][2], "reg": s in reg, "pm": s in pm}
                  for s in sorted(reg | pm)])

    todo = [i for i, d in enumerate(days) if d >= START and not (out / f"{d}.json").exists()]
    with ThreadPoolExecutor(10) as ex:
        for k, _ in enumerate(ex.map(one, todo)):
            if k % 100 == 0:
                log(f"scan {k}/{len(todo)}")


# ------------------------------------------------------------------ minute bars
def stage_minute(only_scanned=False, workers=8):
    days = [d for d in sessions() if d >= START]
    if only_scanned:
        days = [d for d in days if (ROOT / "cands" / f"{d}.json").exists()]
    out = ROOT / "min"

    def one(d):
        f = out / f"{d}.npz"
        if f.exists():
            return
        cands = jload(ROOT / "cands" / f"{d}.json")
        syms = [c["sym"] for c in cands]
        bars = defaultdict(list)
        for c in range(0, len(syms), 200):
            for page in paged("/v2/stocks/bars", {"symbols": ",".join(syms[c:c + 200]), "timeframe": "1Min",
                                                  "start": iso(et(d, 4, 0)), "end": iso(et(d, 11, 59)), "limit": 10000,
                                                  "feed": "sip", "adjustment": "raw"}, "bars"):
                for s, rows in page.items():
                    bars[s] += rows
        S, off, M, O, Hh, L, C, V = [], [0], [], [], [], [], [], []
        for s in syms:
            rows = bars.get(s, [])
            for r in rows:
                t = parse_t(r["t"]).astimezone(ET)
                M.append(t.hour * 60 + t.minute); O.append(r["o"]); Hh.append(r["h"]); L.append(r["l"]); C.append(r["c"]); V.append(r["v"])
            S.append(s); off.append(len(M))
        out.mkdir(parents=True, exist_ok=True)
        tmp = out / f"{d}.tmp.npz"
        np.savez(tmp, sym=np.array(S, dtype="U5"), off=np.array(off, np.int64), m=np.array(M, np.int16),
                 o=np.array(O, np.float32), h=np.array(Hh, np.float32), l=np.array(L, np.float32),
                 c=np.array(C, np.float32), v=np.array(V, np.float32))
        tmp.replace(f)

    todo = [d for d in days if not (out / f"{d}.npz").exists()]
    with ThreadPoolExecutor(workers) as ex:
        for k, _ in enumerate(ex.map(one, todo)):
            if k % 100 == 0:
                log(f"minute {k}/{len(todo)}")


# ------------------------------------------------------------------ news for candidates
def stage_news():
    days = sessions()
    out = ROOT / "news"

    def one(di):
        d = days[di]
        f = out / f"{d}.json"
        if d < START or f.exists():
            return
        syms = [c["sym"] for c in jload(ROOT / "cands" / f"{d}.json")]
        rows = []
        for c in range(0, len(syms), 100):
            part = syms[c:c + 100]
            if not part:
                continue
            for page in paged("/v1beta1/news", {"symbols": ",".join(part), "start": iso(et(days[di - 1], 16, 0)),
                                                 "end": iso(et(d, 12, 0)), "limit": 50, "include_content": "false"}, "news"):
                for n in page:
                    t = parse_t(n["created_at"]).astimezone(ET)
                    mins = (t.date() - d).days * 1440 + t.hour * 60 + t.minute  # minutes relative to d 00:00 ET
                    for s in n.get("symbols") or []:
                        if s in part:
                            rows.append([s, mins, n.get("headline", ""), len(n.get("symbols") or [])])
        jsave(f, rows)

    todo = [i for i, d in enumerate(days) if d >= START and not (out / f"{d}.json").exists()]
    with ThreadPoolExecutor(8) as ex:
        for k, _ in enumerate(ex.map(one, todo)):
            if k % 200 == 0:
                log(f"news {k}/{len(todo)}")


# ------------------------------------------------------------------ quotes for the spread model
def stage_quotes(n=1500, seed=7):
    f = ROOT / "quotes.json"
    if f.exists():
        return jload(f)
    rng = np.random.default_rng(seed)
    files = sorted((ROOT / "min").glob("*.npz"))
    picks = []
    while len(picks) < n:
        fp = files[rng.integers(len(files))]
        z = np.load(fp)
        if len(z["sym"]) == 0:
            continue
        j = int(rng.integers(len(z["sym"])))
        a, b = int(z["off"][j]), int(z["off"][j + 1])
        if b - a < 5:
            continue
        k = int(rng.integers(a, b))
        picks.append((date.fromisoformat(fp.stem), str(z["sym"][j]), int(z["m"][k]), float(z["c"][k]), float(z["v"][k])))

    def one(p):
        d, s, m, c, v = p
        t0 = et(d, m // 60, m % 60)
        try:
            b = get("/v2/stocks/quotes", {"symbols": s, "start": iso(t0), "end": iso(t0 + timedelta(minutes=1)), "limit": 200, "feed": "sip"})
        except RuntimeError:
            return None
        qs = (b.get("quotes") or {}).get(s) or []
        sp = [(q["ap"] - q["bp"]) / ((q["ap"] + q["bp"]) / 2) for q in qs if q.get("ap") and q.get("bp") and q["ap"] >= q["bp"] > 0]
        if not sp:
            return None
        return {"date": str(d), "sym": s, "m": m, "price": c, "bar_dollar_vol": c * v, "spread_pct": float(np.median(sp)) * 100}

    with ThreadPoolExecutor(4) as ex:
        res = [r for r in ex.map(one, picks) if r]
    jsave(f, res)
    log(f"quotes: {len(res)} samples")
    return res


def main(argv):
    stages = {"universe": stage_universe, "daily": stage_daily, "scan": stage_scan, "minute": stage_minute,
              "news": stage_news, "quotes": stage_quotes}
    run = list(stages) if argv[:1] == ["all"] else argv
    for s in run:
        log("stage", s); stages[s](); log("stage", s, "done")


if __name__ == "__main__":
    main(sys.argv[1:])
