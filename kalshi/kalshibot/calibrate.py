"""Measure the favorite-longshot bias on recently settled Kalshi markets.

For each settled binary market: last traded YES price `hours_before` before close, and the result.
Bucket by longshot price q = min(p, 1-p); ratio = realized longshot win rate / mean q.
Writes a ratio table the strategy loads via Config.calibration_path.
One market per event (the most traded) to limit correlated samples.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from .client import KalshiClient
from .model import count, fee, parse_time, price

BINS = [0.0, 0.03, 0.06, 0.10, 0.15, 0.20, 0.30, 0.40, 0.50]


def price_before(client: KalshiClient, ticker: str, ts: int) -> float | None:
    trades = client.trades(ticker=ticker, max_ts=ts, max_pages=1)
    if not trades:
        return None
    t = max(trades, key=lambda t: t.get("created_time", ""))
    return price(t, "yes_price")


def bucketize(rows: list[tuple[float, bool]]) -> list[dict]:
    """rows: (longshot price q, longshot won)."""
    b = defaultdict(list)
    for q, won in rows:
        for lo, hi in zip(BINS, BINS[1:]):
            if lo < q <= hi:
                b[(lo, hi)].append((q, won))
                break
    out = []
    for (lo, hi), xs in sorted(b.items()):
        n = len(xs)
        mq = sum(q for q, _ in xs) / n
        wr = sum(w for _, w in xs) / n
        fav = 1 - mq
        out.append({
            "bin": f"{lo:.2f}-{hi:.2f}", "n": n, "mean_longshot_price": round(mq, 4),
            "longshot_win_rate": round(wr, 4), "ratio": round(wr / mq, 3) if mq else None,
            # $/contract buying the favorite at mid as a maker (fee'd series) vs taker
            "fav_edge_maker": round((1 - wr) - fav - fee(100, fav, 0.0175) / 100, 4),
            "fav_edge_taker": round((1 - wr) - fav - fee(100, fav, 0.07) / 100, 4),
        })
    return out


def ratio_table(buckets: list[dict], min_n: int = 30) -> list[list[float]]:
    rows = [[b["mean_longshot_price"], min(1.0, b["ratio"])] for b in buckets if b["n"] >= min_n and b["ratio"] is not None]
    return rows + [[0.5, 1.0]] if rows else []


def run(client: KalshiClient, days: int, hours_before: float, min_volume: float, max_markets: int,
        out: Path) -> dict:
    import time

    now = int(time.time())
    markets = client.markets(status="settled", min_close_ts=now - days * 86400, max_close_ts=now)
    best: dict[str, dict] = {}
    for m in markets:
        if (m.get("result") or "") not in ("yes", "no") or count(m, "volume") < min_volume:
            continue
        if m.get("ticker", "").startswith("KXMVE"):
            continue
        e = m.get("event_ticker", m["ticker"])
        if e not in best or count(m, "volume") > count(best[e], "volume"):
            best[e] = m
    rows = []
    for m in list(best.values())[:max_markets]:
        ct = parse_time(m.get("close_time"))
        if not ct:
            continue
        p = price_before(client, m["ticker"], int(ct.timestamp() - hours_before * 3600))
        if p is None or not 0 < p < 1:
            continue
        longshot_is_yes = p < 0.5
        q = p if longshot_is_yes else 1 - p
        won = (m["result"] == "yes") == longshot_is_yes
        rows.append((q, won))
    buckets = bucketize(rows)
    res = {"days": days, "hours_before": hours_before, "markets": len(rows), "buckets": buckets,
           "ratio_table": ratio_table(buckets)}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, indent=1))
    return res
