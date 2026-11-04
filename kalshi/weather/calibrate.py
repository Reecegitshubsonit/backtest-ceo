"""Measure forecast error per station against Kalshi's own settled values.

Truth: `expiration_value` on settled Kalshi temperature markets (the exact settlement number).
Forecast: Open-Meteo Previous Runs API (what the models said 1 and 2 days ahead), climate-day max/min.
Output per station and lead: n, bias (truth - forecast), sd and MAE, used by model.distribution.
"""
from __future__ import annotations

import json
import math
import time
from datetime import date, timedelta
from pathlib import Path

from kalshibot.client import KalshiClient, KalshiError

from . import forecast as fc
from .stations import DEFAULT_SERIES, STATIONS, kind_from_rules, station_from_rules
from .trader import event_date


def settled_truth(client: KalshiClient, series: str, days: int) -> tuple[str | None, str | None, dict[date, float]]:
    now = int(time.time())
    truth, code, kind = {}, None, None
    for endpoint in ("/markets", "/historical/markets"):
        try:
            ms = client.paginate(endpoint, "markets", {"series_ticker": series, "status": "settled",
                                                       "min_close_ts": now - days * 86400, "limit": 1000}, max_pages=20)
            for m in ms:
                code = code or station_from_rules(m.get("rules_primary", ""))
                kind = kind or kind_from_rules(m.get("rules_primary", ""))
                d, v = event_date(m.get("event_ticker", "")), m.get("expiration_value")
                try:
                    if d and v not in (None, ""):
                        truth[d] = float(v)
                except ValueError:
                    pass
        except KalshiError:
            continue
        if len(truth) >= days * 0.6:
            break
    return code, kind, truth


def stats(errs: list[float]) -> dict:
    n = len(errs)
    if n < 2:
        return {"n": n}
    m = sum(errs) / n
    sd = math.sqrt(sum((e - m) ** 2 for e in errs) / (n - 1))
    return {"n": n, "bias": round(m, 2), "sd": round(sd, 2), "mae": round(sum(abs(e) for e in errs) / n, 2)}


def run(client: KalshiClient, series_list: list[str] | None, days: int, out: Path, log=print, session=None) -> dict:
    res: dict = json.loads(out.read_text()) if out.exists() else {}
    res.setdefault("stations", {})
    for series in series_list or DEFAULT_SERIES:
        code, kind, truth = settled_truth(client, series, days)
        if not (code and kind and truth):
            log(f"{series}: no settled data")
            continue
        _, lat, lon, std, name = STATIONS[code]
        start, end = min(truth), max(truth)
        entry = res["stations"].setdefault(code, {})
        for lead in (1, 2):
            try:
                f = fc.previous_run_extremes(lat, lon, start, end, std, kind, lead, session=session)
            except Exception as e:
                log(f"{series} lead {lead}: forecast fetch failed: {e}")
                continue
            errs = [truth[d] - f[d] for d in truth if d in f]
            entry[f"{kind}_lead{lead}"] = {**stats(errs), "models": list(fc.DET_MODELS)}
            log(f"{series:14} {code} {kind:4} lead{lead}: {entry[f'{kind}_lead{lead}']}")
    res["updated"] = date.today().isoformat()
    res["days"] = days
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, indent=1))
    return res
