"""Walk-forward backtest with NBM station forecasts, scored against the market (same rules as backtest.py)."""
from __future__ import annotations

import json
import time
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from kalshibot.client import KalshiClient, KalshiError

from . import nbm
from .backtest import decision_ts, quotes_at, settled_events, simulate, summarize
from .model import WxConfig, bracket_prob
from .stations import DEFAULT_SERIES, STATIONS


def brier(xs):
    return round(sum(xs) / len(xs), 4) if xs else None


def run(client: KalshiClient, cfg: WxConfig, series_list, days: int, out: Path, cache: Path, log=print) -> dict:
    rows_by_mode = {"const": [], "scaled": []}
    b = {"const": [], "scaled": [], "market": []}
    cal_out = {}
    for series in series_list or DEFAULT_SERIES:
        for attempt in range(4):
            try:
                code, kind, events = settled_events(client, series, days, cache / f"kalshi_{series}_{days}.json")
                break
            except KalshiError as e:
                log(f"{series}: {e} (retrying)")
                time.sleep(30 * (attempt + 1))
        else:
            continue
        if not (code and kind and events):
            continue
        icao = STATIONS[code][0]
        hist = nbm.history(icao, min(events).fromordinal(min(events).toordinal() - 2), max(events), cache)
        fc = {}
        for d in events:
            x = nbm.extreme(hist, d, kind, before=datetime.fromtimestamp(decision_ts(d), timezone.utc))
            if x:
                fc[d] = x
        errs = {d: (e["truth"] - fc[d][0], fc[d][1]) for d, e in events.items() if d in fc}
        allfit = nbm.fit(list(errs.values()))
        if allfit:
            cal_out.setdefault(code, {})[f"{kind}_nbm"] = allfit
        q = quotes_at(client, {m["ticker"]: decision_ts(d) for d, e in events.items() if d in fc for m in e["markets"]},
                      cache / f"quotes_{series}_{days}.json")
        used = 0
        for d, e in events.items():
            if d not in fc:
                continue
            f = nbm.fit([v for k, v in errs.items() if k != d])  # leave-one-out
            if not f:
                continue
            txn, xnd, _ = fc[d]
            for m in e["markets"]:
                if m["ticker"] not in q:
                    continue
                bid, ask = q[m["ticker"]]
                y = 1.0 if m["result"] == "yes" else 0.0
                b["market"].append(((bid + ask) / 2 - y) ** 2)
                for mode in ("const", "scaled"):
                    p = bracket_prob(m.get("strike_type", ""), m.get("floor_strike"), m.get("cap_strike"),
                                     txn + f["bias"], nbm.sigma(f, xnd, mode), None, kind)
                    if p is None:
                        continue
                    b[mode].append((p - y) ** 2)
                    rows_by_mode[mode].append({"station": code, "event": m["event_ticker"], "ticker": m["ticker"],
                                               "p_model": p, "bid": bid, "ask": ask, "result": m["result"]})
                used += 1
        log(f"{series:14} {code} {kind:4} days={len(events)} nbm={len(fc)} brackets={used} fit={allfit}")
    best_mode = min(("const", "scaled"), key=lambda m: brier(b[m]) or 9)
    res = {"days": days, "brier": {k: brier(v) for k, v in b.items()}, "best_mode": best_mode, "variants": {}}
    rows = rows_by_mode[best_mode]
    for w in (1.0, 0.5):
        for me in (0.03, 0.06, 0.10):
            v = simulate(rows, replace(cfg, model_weight=w, min_edge=me))
            res["variants"][f"w{w}_edge{me}"] = {k: v[k] for k in v if k != "list"}
    base = simulate(rows, cfg)
    res["config_result"] = {k: base[k] for k in base if k != "list"}
    per = {}
    for x in base.get("list", []):
        per.setdefault(x["station"], []).append(x)
    res["by_station"] = {s: {k: v for k, v in summarize(xs).items() if k != "list"} for s, xs in sorted(per.items())}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({**res, "calibration": cal_out, "bets": base.get("list", [])}, indent=1))
    return res
