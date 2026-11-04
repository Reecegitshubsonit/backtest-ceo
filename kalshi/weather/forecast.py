"""Forecast inputs: Open-Meteo ensembles (GFS 31 + ECMWF 51 members) and NWS observations so far today."""
from __future__ import annotations

import math
from datetime import date, datetime, timedelta, timezone

import requests

ENSEMBLE_URL = "https://ensemble-api.open-meteo.com/v1/ensemble"
PREVIOUS_RUNS_URL = "https://previous-runs-api.open-meteo.com/v1/forecast"
NWS = "https://api.weather.gov"
UA = {"User-Agent": "kalshibot-weather (personal research script)", "Accept": "application/geo+json"}
MODELS = "gfs025,ecmwf_ifs025"


def climate_window(day: date, std_utc: int) -> tuple[datetime, datetime]:
    """UTC bounds of the NWS climate day: local-standard midnight to midnight."""
    start = datetime(day.year, day.month, day.day, tzinfo=timezone.utc) - timedelta(hours=std_utc)
    return start, start + timedelta(hours=24)


def ensemble_members(lat: float, lon: float, session=None, models: str = MODELS) -> tuple[list[datetime], dict[str, list]]:
    s = session or requests
    r = s.get(ENSEMBLE_URL, params={"latitude": lat, "longitude": lon, "hourly": "temperature_2m", "models": models,
                                     "temperature_unit": "fahrenheit", "timezone": "GMT", "forecast_days": 4,
                                     "past_days": 1}, timeout=30)
    r.raise_for_status()
    h = r.json()["hourly"]
    times = [datetime.fromisoformat(t).replace(tzinfo=timezone.utc) for t in h["time"]]
    members = {k: v for k, v in h.items() if k.startswith("temperature_2m")}
    return times, members


def member_extremes(times: list[datetime], members: dict[str, list], day: date, std_utc: int, kind: str) -> list[float]:
    """Daily max (or min) of each member over the climate day; members missing hours are dropped."""
    a, b = climate_window(day, std_utc)
    idx = [i for i, t in enumerate(times) if a <= t < b]
    out = []
    for vals in members.values():
        xs = [vals[i] for i in idx if i < len(vals) and vals[i] is not None]
        if len(xs) >= 20:
            out.append(max(xs) if kind == "high" else min(xs))
    return out


def observed_extreme(icao: str, day: date, std_utc: int, kind: str, now: datetime | None = None,
                     session=None) -> float | None:
    """Max/min temperature (F) observed so far in the climate day, from NWS station observations."""
    s = session or requests
    a, b = climate_window(day, std_utc)
    now = now or datetime.now(timezone.utc)
    if now <= a:
        return None
    r = s.get(f"{NWS}/stations/{icao}/observations", headers=UA, timeout=30,
              params={"start": a.isoformat(), "end": min(b, now).isoformat()})
    r.raise_for_status()
    vals = []
    for f in r.json().get("features", []):
        c = ((f.get("properties") or {}).get("temperature") or {}).get("value")
        if c is not None:
            vals.append(c * 9 / 5 + 32)
    if not vals:
        return None
    return max(vals) if kind == "high" else min(vals)


def previous_run_extremes(lat: float, lon: float, start: date, end: date, std_utc: int, kind: str,
                          lead_days: int = 1, session=None) -> dict[date, float]:
    """Day-ahead forecast extremes for past days (Open-Meteo Previous Runs API), for calibration."""
    s = session or requests
    var = f"temperature_2m_previous_day{lead_days}"
    r = s.get(PREVIOUS_RUNS_URL, params={"latitude": lat, "longitude": lon, "hourly": var,
                                         "temperature_unit": "fahrenheit", "timezone": "GMT",
                                         "start_date": (start - timedelta(days=1)).isoformat(),
                                         "end_date": (end + timedelta(days=1)).isoformat()}, timeout=60)
    r.raise_for_status()
    h = r.json()["hourly"]
    times = [datetime.fromisoformat(t).replace(tzinfo=timezone.utc) for t in h["time"]]
    out, d = {}, start
    while d <= end:
        xs = member_extremes(times, {var: h[var]}, d, std_utc, kind)
        if xs:
            out[d] = xs[0]
        d += timedelta(days=1)
    return out


def mean_sd(xs: list[float]) -> tuple[float, float]:
    m = sum(xs) / len(xs)
    sd = math.sqrt(sum((x - m) ** 2 for x in xs) / max(1, len(xs) - 1))
    return m, sd
