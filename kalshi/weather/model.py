"""Bracket probabilities for Kalshi temperature markets.

The reported value is a whole degree F. Kalshi strike types (from the market object):
  greater  floor_strike=f      YES if T > f    (T >= f+1)
  less     cap_strike=c        YES if T < c    (T <= c-1)
  between  floor=f, cap=c      YES if f <= T <= c
With X continuous and T = round(X): greater -> X >= f+0.5; less -> X < c-0.5; between -> f-0.5 <= X < c+0.5.

Forecast distribution: Normal(mu, sd) with mu = ensemble mean + bias and
sd = max(ensemble sd * inflate, calibrated floor for the lead time). Ensembles are under-dispersed and the
hourly grid misses the peak between hours, which is what the bias and floor absorb.
If part of the day is already observed, the final high is max(X, observed so far) (min for lows).
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path


def ncdf(x: float, mu: float, sd: float) -> float:
    return 0.5 * (1 + math.erf((x - mu) / (sd * math.sqrt(2))))


def p_below(t: float, mu: float, sd: float, obs: float | None, kind: str) -> float:
    """P(final value < t)."""
    if obs is not None:
        if kind == "high" and obs >= t:
            return 0.0  # the high is already at or above t
        if kind == "low" and obs < t:
            return 1.0  # the low is already below t
    return ncdf(t, mu, sd)


def bracket_prob(strike_type: str, floor: float | None, cap: float | None, mu: float, sd: float,
                 obs: float | None = None, kind: str = "high") -> float | None:
    if strike_type == "greater" and floor is not None:
        return 1 - p_below(floor + 0.5, mu, sd, obs, kind)
    if strike_type == "less" and cap is not None:
        return p_below(cap - 0.5, mu, sd, obs, kind)
    if strike_type == "between" and floor is not None and cap is not None:
        return max(0.0, p_below(cap + 0.5, mu, sd, obs, kind) - p_below(floor - 0.5, mu, sd, obs, kind))
    return None


@dataclass
class WxConfig:
    series: list[str] = field(default_factory=list)       # empty = stations.DEFAULT_SERIES
    bias: float = 0.8            # F added to the model high when uncalibrated (hourly grid misses the peak)
    inflate: float = 1.3         # ensemble spread multiplier
    sd_floor: dict = field(default_factory=lambda: {"0": 1.6, "1": 2.3, "2": 3.0, "3": 3.6})
    min_lead_days: int = 1       # same-day is not calibrated yet: trade tomorrow only by default
    max_lead_days: int = 1
    min_hours_left: float = 1.0  # stop trading a market this close to its close
    min_edge: float = 0.06       # blended prob minus all-in cost, per $1 contract
    max_edge: float = 0.20       # bigger "edges" on liquid markets are model error: skip and log
    model_weight: float = 0.5    # blended prob = w * model + (1 - w) * market mid
    nws_weight: float = 0.0      # highs: centre = w * NWS point forecast + (1 - w) * models (not backtestable)
    min_price: float = 0.10      # longshots are where the favorite-longshot bias bites
    max_price: float = 0.92
    min_volume_24h: float = 300
    usd_per_bet: float = 2.0
    max_per_market: float = 2.0
    max_per_event: float = 4.0   # one city-day
    max_total_exposure: float = 8.0
    taker_fee_rate: float = 0.07
    live: bool = False
    kill_file: str = "data/STOP"
    calibration_path: str = "data/weather_calibration.json"
    starting_cash: float = 100.0

    @classmethod
    def load(cls, path: str | None) -> "WxConfig":
        if path and Path(path).exists():
            return cls(**json.loads(Path(path).read_text()))
        return cls()

    def calibration(self) -> dict:
        p = Path(self.calibration_path)
        return json.loads(p.read_text()).get("stations", {}) if p.exists() else {}


def distribution(members: list[float], lead: int, kind: str, cfg: WxConfig, cal: dict | None = None) -> tuple[float, float]:
    from .forecast import DET_MODELS, mean_sd

    m, sd = mean_sd(members)
    bias = cfg.bias if kind == "high" else -cfg.bias
    floor = float(cfg.sd_floor.get(str(min(lead, 3)), 3.0))
    if cal:  # per-station measured bias and error spread at this lead
        c = cal.get(f"{kind}_lead{max(1, min(lead, 2))}")
        if c and c.get("n", 0) >= 20 and c.get("models") == list(DET_MODELS):
            bias, floor = c["bias"], max(c["sd"], 1.0)
    return m + bias, max(sd * cfg.inflate, floor)
