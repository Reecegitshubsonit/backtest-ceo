"""Walk-forward backtest of the weather strategy on Kalshi's real prices.

For every settled city-day in the last N days (Kalshi keeps ~60 days outside its historical archive):
  decision time   20:00 UTC the day before (after the 12z model runs)
  price           last hourly candle at or before then: real YES bid/ask from Kalshi
  forecast        GFS + ECMWF day-ahead climate-day extreme (Open-Meteo Previous Runs), same as live
  bias/spread     measured on the station's OTHER days only (leave-one-out, no peeking)
  rule            identical to live: blend with market mid, min/max edge, price band, $ caps, taker fee
Also scores the model against the market itself (Brier: lower is better) on every quoted bracket.
"""
from __future__ import annotations

import json
import math
import time
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from kalshibot.client import KalshiClient, KalshiError
from kalshibot.model import fee, r2

from . import forecast as fc
from .model import WxConfig, bracket_prob
from .stations import DEFAULT_SERIES, STATIONS, kind_from_rules, station_from_rules
from .trader import event_date


def settled_events(client: KalshiClient, series: str, days: int) -> tuple[str | None, str | None, dict]:
    now = int(time.time())
    code = kind = None
    events: dict[date, dict] = {}
    for m in client.paginate("/markets", "markets", {"series_ticker": series, "status": "settled",
                                                     "min_close_ts": now - days * 86400, "limit": 1000}, max_pages=20):
        code = code or station_from_rules(m.get("rules_primary", ""))
        kind = kind or kind_from_rules(m.get("rules_primary", ""))
        d = event_date(m.get("event_ticker", ""))
        if not d or m.get("result") not in ("yes", "no"):
            continue
        e = events.setdefault(d, {"markets": [], "truth": None})
        e["markets"].append(m)
        try:
            e["truth"] = float(m["expiration_value"])
        except (KeyError, TypeError, ValueError):
            pass
    return code, kind, {d: e for d, e in events.items() if e["truth"] is not None}


def decision_ts(day: date) -> int:
    return int(datetime(day.year, day.month, day.day, 20, tzinfo=timezone.utc).timestamp()) - 86400


def quotes_at(client: KalshiClient, tickers_ts: dict[str, int]) -> dict[str, tuple[float, float]]:
    """(yes_bid, yes_ask) from the last hourly candle at or before each ticker's decision time."""
    groups: dict[int, list[str]] = {}
    for t, ts in tickers_ts.items():  # one short window per decision time keeps under the 10,000-candle cap
        groups.setdefault(ts, []).append(t)
    out = {}
    for ts, ticks in groups.items():
        for i in range(0, len(ticks), 100):
            chunk = ticks[i:i + 100]
            data = client.get("/markets/candlesticks", {"market_tickers": ",".join(chunk), "start_ts": ts - 6 * 3600,
                                                        "end_ts": ts, "period_interval": 60,
                                                        "include_latest_before_start": "true"})
            for mk in data.get("markets", []):
                best = None
                for c in mk.get("candlesticks", []):
                    if c.get("end_period_ts", 0) > ts:
                        continue
                    b = (c.get("yes_bid") or {}).get("close_dollars")
                    a = (c.get("yes_ask") or {}).get("close_dollars")
                    if b is not None and a is not None and 0 < float(b) < float(a) < 1:
                        best = (float(b), float(a))
                if best:
                    out[mk.get("market_ticker")] = best
    return out


def loo(errs: dict[date, float], d: date) -> tuple[float, float] | None:
    xs = [e for k, e in errs.items() if k != d]
    if len(xs) < 20:
        return None
    m = sum(xs) / len(xs)
    return m, max(1.0, math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1)))


def simulate(rows: list[dict], cfg: WxConfig) -> dict:
    """rows: one per quoted market with p_model, bid, ask, result, event, station."""
    by_event: dict[str, list] = {}
    for r in rows:
        p = cfg.model_weight * r["p_model"] + (1 - cfg.model_weight) * (r["bid"] + r["ask"]) / 2
        best = None
        for side, ps, ask in (("yes", p, r["ask"]), ("no", 1 - p, r2(1 - r["bid"]))):
            if not cfg.min_price <= ask <= cfg.max_price:
                continue
            edge = ps - ask - fee(100, ask, cfg.taker_fee_rate) / 100
            if cfg.min_edge <= edge <= cfg.max_edge and (best is None or edge > best[2]):
                best = (side, ask, edge)
        if best:
            by_event.setdefault(r["event"], []).append((best, r))
    bets = []
    for ev, cands in by_event.items():
        room = cfg.max_per_event
        for (side, ask, edge), r in sorted(cands, key=lambda x: -x[0][2]):
            unit = ask + fee(100, ask, cfg.taker_fee_rate) / 100
            n = int(min(cfg.usd_per_bet, cfg.max_per_market, room) / unit)
            if n < 1:
                continue
            cost = n * ask + fee(n, ask, cfg.taker_fee_rate)
            pnl = (n if r["result"] == side else 0) - cost
            room -= cost
            bets.append({"station": r["station"], "event": ev, "ticker": r["ticker"], "side": side, "ask": ask,
                         "edge": round(edge, 4), "cost": round(cost, 4), "pnl": round(pnl, 4), "won": pnl > 0})
    return summarize(bets)


def summarize(bets: list[dict]) -> dict:
    n = len(bets)
    if not n:
        return {"bets": 0}
    rets = [b["pnl"] / b["cost"] for b in bets]
    m = sum(rets) / n
    sd = math.sqrt(sum((x - m) ** 2 for x in rets) / max(1, n - 1)) or 1e-9
    staked, pnl = sum(b["cost"] for b in bets), sum(b["pnl"] for b in bets)
    return {"bets": n, "win_rate": round(sum(b["won"] for b in bets) / n, 3), "staked": round(staked, 2),
            "pnl": round(pnl, 2), "roi": round(pnl / staked, 4), "t": round(m / sd * math.sqrt(n), 2),
            "list": bets}


def run(client: KalshiClient, cfg: WxConfig, series_list: list[str] | None, days: int, out: Path,
        log=print, session=None) -> dict:
    rows, brier_model, brier_mkt = [], [], []
    for series in series_list or DEFAULT_SERIES:
        try:
            code, kind, events = settled_events(client, series, days)
        except KalshiError as e:
            log(f"{series}: {e}")
            continue
        if not (code and kind and events):
            log(f"{series}: no settled data")
            continue
        _, lat, lon, std, _ = STATIONS[code]
        f = fc.previous_run_extremes(lat, lon, min(events), max(events), std, kind, 1, session=session)
        errs = {d: e["truth"] - f[d] for d, e in events.items() if d in f}
        tickers = {m["ticker"]: decision_ts(d) for d, e in events.items() for m in e["markets"]}
        q = quotes_at(client, tickers)
        used = 0
        for d, e in events.items():
            bs = loo(errs, d)
            if d not in f or not bs:
                continue
            mu, sd = f[d] + bs[0], bs[1]
            for m in e["markets"]:
                if m["ticker"] not in q:
                    continue
                p = bracket_prob(m.get("strike_type", ""), m.get("floor_strike"), m.get("cap_strike"), mu, sd, None, kind)
                if p is None:
                    continue
                bid, ask = q[m["ticker"]]
                y = 1.0 if m["result"] == "yes" else 0.0
                brier_model.append((p - y) ** 2)
                brier_mkt.append(((bid + ask) / 2 - y) ** 2)
                rows.append({"station": code, "event": m["event_ticker"], "ticker": m["ticker"], "p_model": p,
                             "bid": bid, "ask": ask, "result": m["result"]})
                used += 1
        log(f"{series:14} {code} {kind:4} days={len(events)} forecast={len(f)} quoted brackets={used}")
    res = {"days": days, "brackets": len(rows),
           "brier_model": round(sum(brier_model) / len(brier_model), 4) if brier_model else None,
           "brier_market": round(sum(brier_mkt) / len(brier_mkt), 4) if brier_mkt else None,
           "variants": {}}
    for w in (1.0, 0.5):
        for me in (0.03, 0.06, 0.10):
            v = simulate(rows, replace(cfg, model_weight=w, min_edge=me))
            res["variants"][f"w{w}_edge{me}"] = {k: v[k] for k in v if k != "list"}
    base = simulate(rows, cfg)
    res["config_result"] = {k: base[k] for k in base if k != "list"}
    per = {}
    for b in base.get("list", []):
        per.setdefault(b["station"], []).append(b)
    res["by_station"] = {s: {k: v for k, v in summarize(bs).items() if k != "list"} for s, bs in sorted(per.items())}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({**res, "bets": base.get("list", [])}, indent=1))
    return res
