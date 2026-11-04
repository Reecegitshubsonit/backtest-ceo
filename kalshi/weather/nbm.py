"""National Blend of Models (NBM) station forecasts: the NWS's calibrated blend at the exact climate stations.

NBS bulletin fields (via Iowa Environmental Mesonet, which archives every 00/06/12/18Z run):
  txn  max temp (valid 00Z next day; max over 12Z-06Z) or min temp (valid 12Z; min over 00Z-18Z), whole F
  xnd  NBM's own standard deviation of that max/min, F
Forecast for day D:  high -> row with ftime = D+1 00Z;  low -> row with ftime = D 12Z,
taken from the latest run published before the decision time.
"""
from __future__ import annotations

import csv
import io
import math
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests

IEM = "https://mesonet.agron.iastate.edu"
UA = {"User-Agent": "kalshibot-weather (personal research script)"}
PUBLISH_LAG_H = 2  # an NBS run is usually on IEM within ~1.5h of its cycle time


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _t(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("T", " ").split(".")[0].rstrip("Z")).replace(tzinfo=timezone.utc)


def history(icao: str, start: date, end: date, cache_dir: Path | None = None, session=None) -> list[dict]:
    """All archived NBS rows for a station between two dates (one request; cached on disk)."""
    f = cache_dir / f"{icao}_{start}_{end}.csv" if cache_dir else None
    if f and f.exists():
        text = f.read_text()
    else:
        s = session or requests
        for attempt in range(5):
            r = s.get(f"{IEM}/cgi-bin/request/mos.py", headers=UA, timeout=120,
                      params={"station": icao, "model": "NBS", "sts": f"{start}T00:00Z", "ets": f"{end}T23:59Z",
                              "format": "csv"})
            if r.status_code == 200 and not r.text.startswith("Too many"):
                break
            time.sleep(15 * (attempt + 1))
        text = r.text
        time.sleep(3)  # be polite to IEM
        if f:
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(text)
    return [{"runtime": _t(x["runtime"]), "ftime": _t(x["ftime"]), "txn": _f(x.get("txn")), "xnd": _f(x.get("xnd"))}
            for x in csv.DictReader(io.StringIO(text)) if x.get("runtime")]


def latest(icao: str, session=None) -> list[dict]:
    """Rows of the most recent NBS run (live trading)."""
    s = session or requests
    r = s.get(f"{IEM}/api/1/mos.json", params={"station": icao, "model": "NBS"}, headers=UA, timeout=30)
    r.raise_for_status()
    return [{"runtime": _t(x["runtime_utc"]), "ftime": _t(x["ftime_utc"]), "txn": _f(x.get("txn")),
             "xnd": _f(x.get("xnd"))} for x in r.json().get("data", [])]


def target_ftime(day: date, kind: str) -> datetime:
    d0 = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
    return d0 + timedelta(days=1) if kind == "high" else d0 + timedelta(hours=12)


def extreme(rows: list[dict], day: date, kind: str, before: datetime | None = None) -> tuple[float, float, datetime] | None:
    """(txn, xnd, runtime) for day/kind from the newest run published before `before`."""
    ft = target_ftime(day, kind)
    best = None
    for r in rows:
        if r["ftime"] != ft or r["txn"] is None:
            continue
        if before is not None and r["runtime"] + timedelta(hours=PUBLISH_LAG_H) >= before:
            continue
        if r["runtime"] >= ft:  # never use a run issued after the period started
            continue
        if best is None or r["runtime"] > best[2]:
            best = (r["txn"], r["xnd"] or 2.0, r["runtime"])
    return best


def fit(errs: list[tuple[float, float]]) -> dict | None:
    """errs: (truth - txn, xnd). Bias, constant sd, and the multiplier on NBM's own xnd."""
    if len(errs) < 20:
        return None
    n = len(errs)
    bias = sum(e for e, _ in errs) / n
    sd = math.sqrt(sum((e - bias) ** 2 for e, _ in errs) / (n - 1))
    k = math.sqrt(sum(((e - bias) / max(x, 1.0)) ** 2 for e, x in errs) / (n - 1))
    return {"n": n, "bias": round(bias, 3), "sd": round(max(sd, 1.0), 3), "k": round(k, 3)}


def sigma(f: dict, xnd: float, mode: str) -> float:
    return max(1.0, f["sd"] if mode == "const" else f["k"] * max(xnd, 1.0))
