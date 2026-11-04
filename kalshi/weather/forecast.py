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
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
DET_MODELS = ("gfs_global", "ecmwf_ifs025")  # traded, calibrated and backtested on the same models
MIN_HOURS = 8  # some models are 3-hourly


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
        if len(xs) >= MIN_HOURS:
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


def _hourly(url: str, params: dict, session=None) -> tuple[list[datetime], dict]:
    s = session or requests
    r = s.get(url, params=params, timeout=60)
    r.raise_for_status()
    h = r.json()["hourly"]
    return [datetime.fromisoformat(t).replace(tzinfo=timezone.utc) for t in h["time"]], h


def model_extremes(lat: float, lon: float, day: date, std_utc: int, kind: str, session=None,
                   models=DET_MODELS) -> dict[str, float]:
    """Current-run climate-day max/min per deterministic model (what the bot trades on)."""
    out = {}
    for m in models:
        try:
            times, h = _hourly(FORECAST_URL, {"latitude": lat, "longitude": lon, "hourly": "temperature_2m",
                                              "models": m, "temperature_unit": "fahrenheit", "timezone": "GMT",
                                              "forecast_days": 4, "past_days": 1}, session)
        except Exception:
            continue
        xs = member_extremes(times, {k: v for k, v in h.items() if k.startswith("temperature_2m")}, day, std_utc, kind)
        if xs:
            out[m] = xs[0]
    return out


def previous_run_extremes(lat: float, lon: float, start: date, end: date, std_utc: int, kind: str,
                          lead_days: int = 1, session=None, models=DET_MODELS) -> dict[date, float]:
    """What the models said `lead_days` ahead, for past days (Open-Meteo Previous Runs API).
    Averaged over the models that answer, exactly like the live forecast."""
    var = f"temperature_2m_previous_day{lead_days}"
    per_model: list[dict[date, float]] = []
    for m in models:
        try:
            times, h = _hourly(PREVIOUS_RUNS_URL, {"latitude": lat, "longitude": lon, "hourly": var, "models": m,
                                                   "temperature_unit": "fahrenheit", "timezone": "GMT",
                                                   "start_date": (start - timedelta(days=1)).isoformat(),
                                                   "end_date": (end + timedelta(days=1)).isoformat()}, session)
        except Exception:
            continue
        series = {k: v for k, v in h.items() if k.startswith(var)}
        got, d = {}, start
        while d <= end:
            xs = member_extremes(times, series, d, std_utc, kind)
            if xs:
                got[d] = xs[0]
            d += timedelta(days=1)
        if got:
            per_model.append(got)
    out = {}
    for d in set().union(*per_model) if per_model else []:
        vals = [pm[d] for pm in per_model if d in pm]
        if len(vals) == len(per_model):  # require every model, so live and history match
            out[d] = sum(vals) / len(vals)
    return out


def mean_sd(xs: list[float]) -> tuple[float, float]:
    m = sum(xs) / len(xs)
    sd = math.sqrt(sum((x - m) ** 2 for x in xs) / max(1, len(xs) - 1))
    return m, sd


def nws_forecast_high(lat: float, lon: float, day: date, session=None, cache: dict | None = None) -> float | None:
    """NWS point forecast high (F) for `day` (local date of the daytime period), or None."""
    s = session or requests
    key = (round(lat, 4), round(lon, 4))
    if cache is not None and key in cache:
        url = cache[key]
    else:
        r = s.get(f"{NWS}/points/{lat:.4f},{lon:.4f}", headers=UA, timeout=30)
        r.raise_for_status()
        url = r.json()["properties"]["forecast"]
        if cache is not None:
            cache[key] = url
    r = s.get(url, headers=UA, timeout=30)
    r.raise_for_status()
    for p in r.json()["properties"]["periods"]:
        if p.get("isDaytime") and p.get("startTime", "")[:10] == day.isoformat():
            t = float(p["temperature"])
            return t if p.get("temperatureUnit", "F") == "F" else t * 9 / 5 + 32
    return None
